"""Правила pg→ch для CREATE TABLE-конструкций.

Источник правил: ``src/sql_translator/ast/rules/clickhouse/ddl/create_table.py``.
"""
from __future__ import annotations

import pytest

from sql_translator.ast.metadata import Dialect, Kind
from sql_translator.ast.nodes import (
    ColumnConstraint,
    ColumnDef,
    CreateTableStmt,
    Identifier,
    LikeClause,
    Literal,
    TableConstraint,
    TableRef,
    TypeRef,
)


class TestColumnConstraint:
    @pytest.mark.parametrize("kind_value", ["not_null", "default", "primary_key"])
    def test_known_kinds_do_not_trigger_unknown_fallback(
        self, make, apply, rule_ids, kind_value
    ):
        n = make(ColumnConstraint, kind=kind_value)
        apply(n)
        assert "pg_ch_col_constraint_unknown" not in rule_ids(n)

    def test_primary_key_triggers_kindC(self, make, apply, rule_ids, kinds):
        n = make(ColumnConstraint, kind="primary_key")
        r = apply(n)
        assert "pg_ch_col_primary_key" in rule_ids(r)
        assert Kind.C in kinds(r)

    @pytest.mark.parametrize("kind_value", ["null", "not_null"])
    def test_null_and_not_null_trigger_kindC(
        self, make, apply, rule_ids, kind_value
    ):
        n = make(ColumnConstraint, kind=kind_value)
        r = apply(n)
        assert "pg_ch_col_null" in rule_ids(r)

    def test_check_triggers_kindC(self, make, apply, rule_ids):
        n = make(ColumnConstraint, kind="check")
        r = apply(n)
        assert "pg_ch_col_check" in rule_ids(r)

    @pytest.mark.parametrize("kind_value,rule_id", [
        ("generated_identity", "pg_ch_col_generated_identity"),
        ("generated_stored",   "pg_ch_col_generated_stored"),
        ("generated_virtual",  "pg_ch_col_generated_virtual"),
    ])
    def test_generated_kinds_trigger_kindD(
        self, make, apply, rule_ids, kinds, kind_value, rule_id
    ):
        n = make(ColumnConstraint, kind=kind_value)
        r = apply(n)
        assert rule_id in rule_ids(r)
        assert Kind.D in kinds(r)

    @pytest.mark.parametrize("kind_value,rule_id", [
        ("unique",     "pg_ch_col_unique"),
        ("references", "pg_ch_col_references"),
    ])
    def test_unique_and_references_trigger_kindE(
        self, make, apply, rule_ids, kinds, kind_value, rule_id
    ):
        n = make(ColumnConstraint, kind=kind_value)
        r = apply(n)
        assert rule_id in rule_ids(r)
        assert Kind.E in kinds(r)

    def test_unknown_kind_triggers_unknown_rule(
        self, make, apply, rule_ids, kinds
    ):
        n = make(ColumnConstraint, kind="exotic_kind_xyz")
        r = apply(n)
        assert "pg_ch_col_constraint_unknown" in rule_ids(r)
        assert Kind.E in kinds(r)

    def test_default_kind_only_catchall(self, make, apply, kinds):
        n = make(ColumnConstraint, kind="default")
        r = apply(n)
        # 'default' — известный kind, никаких C/D/E-правил не подходит.
        assert kinds(r) == []


class TestTableConstraint:
    def test_primary_key_triggers_kindC(self, make, apply, rule_ids, kinds):
        n = make(TableConstraint, kind="primary_key")
        r = apply(n)
        assert "pg_ch_tbl_primary_key" in rule_ids(r)
        assert Kind.C in kinds(r)

    def test_check_triggers_kindC(self, make, apply, rule_ids):
        n = make(TableConstraint, kind="check")
        r = apply(n)
        assert "pg_ch_tbl_check" in rule_ids(r)

    def test_unique_triggers_kindE(self, make, apply, rule_ids, kinds):
        n = make(TableConstraint, kind="unique")
        r = apply(n)
        assert "pg_ch_tbl_unique" in rule_ids(r)
        assert Kind.E in kinds(r)

    def test_foreign_key_triggers_kindE(self, make, apply, rule_ids):
        n = make(TableConstraint, kind="foreign_key")
        r = apply(n)
        assert "pg_ch_tbl_foreign_key" in rule_ids(r)

    def test_unknown_kind_triggers_unknown_rule(
        self, make, apply, rule_ids, kinds
    ):
        n = make(TableConstraint, kind="weird")
        r = apply(n)
        assert "pg_ch_tbl_constraint_unknown" in rule_ids(r)
        assert Kind.E in kinds(r)

    def test_known_kind_does_not_trigger_unknown(
        self, make, apply, rule_ids
    ):
        n = make(TableConstraint, kind="primary_key")
        r = apply(n)
        assert "pg_ch_tbl_constraint_unknown" not in rule_ids(r)


class TestColumnDef:
    def test_plain_column_def_only_kindA(self, make, apply, kinds):
        n = make(ColumnDef, name=make(Identifier, name="c"), type=make(TypeRef))
        r = apply(n)
        assert kinds(r) == []
        assert n.compression is None
        assert n.codec == []

    @pytest.mark.parametrize("pg_method,ch_codec", [
        ("lz4",  "LZ4"),
        ("pglz", "LZ4HC"),
    ])
    def test_compression_rewrites_to_codec(
        self, make, apply, pg_method, ch_codec
    ):
        n = make(
            ColumnDef,
            name=make(Identifier, name="c"),
            type=make(TypeRef),
            compression=pg_method,
        )
        r = apply(n)
        # rewrite: compression очищен, codec — список с одним FunctionCall.
        assert r.compression is None
        assert len(r.codec) == 1
        assert r.codec[0].node_kind == "FunctionCall"
        assert r.codec[0].name.name == ch_codec

    def test_unknown_compression_defaults_to_LZ4(self, make, apply):
        n = make(
            ColumnDef,
            name=make(Identifier, name="c"),
            type=make(TypeRef),
            compression="unknown_method",
        )
        r = apply(n)
        assert r.codec[0].name.name == "LZ4"
        assert r.compression is None

    def test_compression_is_kindB_without_annotation(
        self, make, apply, kinds
    ):
        n = make(
            ColumnDef,
            name=make(Identifier, name="c"),
            type=make(TypeRef),
            compression="lz4",
        )
        r = apply(n)
        # Правило B + message=None ⇒ аннотация не создаётся.
        assert kinds(r) == []

    def test_collation_triggers_kindE(self, make, apply, rule_ids, kinds):
        n = make(
            ColumnDef,
            name=make(Identifier, name="c"),
            type=make(TypeRef),
            collation="ru_RU",
        )
        r = apply(n)
        assert "pg_ch_col_collation" in rule_ids(r)
        assert Kind.E in kinds(r)

    def test_storage_triggers_kindE(self, make, apply, rule_ids):
        n = make(
            ColumnDef,
            name=make(Identifier, name="c"),
            type=make(TypeRef),
            storage="EXTERNAL",
        )
        r = apply(n)
        assert "pg_ch_col_storage" in rule_ids(r)


class TestLikeClause:
    def test_like_clause_strips_including_excluding(self, make, apply):
        n = make(
            LikeClause,
            source=make(TableRef),
            including=["DEFAULTS", "CONSTRAINTS"],
            excluding=["INDEXES"],
        )
        r = apply(n)
        # rewrite: списки очищены.
        assert r.including == []
        assert r.excluding == []

    def test_like_clause_is_kindB_without_annotation(
        self, make, apply, kinds
    ):
        n = make(LikeClause, source=make(TableRef))
        r = apply(n)
        assert kinds(r) == []


def _ct(make, **kwargs):
    return make(CreateTableStmt, table=make(TableRef), **kwargs)


class TestCreateTableStmt:
    def test_plain_table_only_kindA(self, make, apply, kinds):
        n = _ct(make)
        r = apply(n)
        assert kinds(r) == []

    def test_partition_by_triggers_kindD(
        self, make, apply, rule_ids, kinds
    ):
        expr = make(Literal, value=1, literal_kind="int", raw="1")
        n = _ct(make, partition_by=expr)
        r = apply(n)
        assert "pg_ch_create_table_partition_by" in rule_ids(r)
        assert Kind.D in kinds(r)

    def test_no_partition_by_does_not_trigger(self, make, apply, rule_ids):
        n = _ct(make, partition_by=None)
        r = apply(n)
        assert "pg_ch_create_table_partition_by" not in rule_ids(r)

    def test_unlogged_triggers_kindE(self, make, apply, rule_ids, kinds):
        n = _ct(make, unlogged=True)
        r = apply(n)
        assert "pg_ch_create_table_unlogged" in rule_ids(r)
        assert Kind.E in kinds(r)

    def test_inherits_triggers_kindE(self, make, apply, rule_ids):
        parent = make(TableRef)
        n = _ct(make, inherits=[parent])
        r = apply(n)
        assert "pg_ch_create_table_inherits" in rule_ids(r)

    def test_empty_inherits_does_not_trigger(self, make, apply, rule_ids):
        n = _ct(make, inherits=[])
        r = apply(n)
        assert "pg_ch_create_table_inherits" not in rule_ids(r)

    def test_tablespace_triggers_kindE(self, make, apply, rule_ids):
        n = _ct(make, tablespace="ts1")
        r = apply(n)
        assert "pg_ch_create_table_tablespace" in rule_ids(r)

    def test_on_commit_triggers_kindE(self, make, apply, rule_ids):
        n = _ct(make, on_commit="DROP")
        r = apply(n)
        assert "pg_ch_create_table_on_commit" in rule_ids(r)

    def test_using_method_triggers_kindE(self, make, apply, rule_ids):
        n = _ct(make, using_method="heap")
        r = apply(n)
        assert "pg_ch_create_table_using" in rule_ids(r)

    def test_multiple_E_features_aggregate(
        self, make, apply, rule_ids, kinds
    ):
        n = _ct(
            make,
            unlogged=True,
            tablespace="ts1",
            on_commit="DROP",
            using_method="heap",
        )
        r = apply(n)
        ids = rule_ids(r)
        assert "pg_ch_create_table_unlogged" in ids
        assert "pg_ch_create_table_tablespace" in ids
        assert "pg_ch_create_table_on_commit" in ids
        assert "pg_ch_create_table_using" in ids
        assert kinds(r).count(Kind.E) == 4

    def test_result_dialect_switched_to_clickhouse(self, make, apply):
        n = _ct(make)
        r = apply(n)
        assert r.dialect is Dialect.CLICKHOUSE
