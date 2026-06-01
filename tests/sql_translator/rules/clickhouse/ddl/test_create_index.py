"""Правила pg→ch для CreateIndexStmt.

Источник правил: ``src/sql_translator/ast/rules/clickhouse/ddl/create_index.py``.
"""
from __future__ import annotations

from sql_translator.ast.metadata import Kind
from sql_translator.ast.nodes import (
    CreateIndexStmt,
    Identifier,
    Literal,
    TableRef,
)


def _idx(make, **kwargs):
    return make(
        CreateIndexStmt,
        name=make(Identifier, name="i"),
        table=make(TableRef),
        **kwargs,
    )


class TestCreateIndexStmt:

    def test_plain_index_always_gets_general_kindD(
        self, make, apply, rule_ids, kinds
    ):
        # Catch-all A и общий D-rule (when=True) всегда срабатывают.
        n = _idx(make)
        r = apply(n)
        ids = rule_ids(r)
        assert "pg_ch_create_index_general" in ids
        assert Kind.D in kinds(r)

    def test_kindA_base_rule_does_not_create_annotation(
        self, make, apply, rule_ids
    ):
        # Catch-all A без message — аннотации нет, но F-fallback заблокирован.
        n = _idx(make)
        r = apply(n)
        ids = rule_ids(r)
        assert "pg_ch_create_index_base" not in ids
        # Никакого F-fallback.
        assert "pg_ch.fallback" not in ids


    def test_using_method_adds_extra_D_rule(self, make, apply, rule_ids):
        n = _idx(make, using_method="btree")
        r = apply(n)
        ids = rule_ids(r)
        assert "pg_ch_create_index_using" in ids
        assert "pg_ch_create_index_general" in ids

    def test_no_using_method_no_using_rule(self, make, apply, rule_ids):
        n = _idx(make, using_method=None)
        r = apply(n)
        assert "pg_ch_create_index_using" not in rule_ids(r)


    def test_unique_triggers_kindE(self, make, apply, rule_ids, kinds):
        n = _idx(make, unique=True)
        r = apply(n)
        assert "pg_ch_create_index_unique" in rule_ids(r)
        assert Kind.E in kinds(r)

    def test_concurrently_triggers_kindE(self, make, apply, rule_ids):
        n = _idx(make, concurrently=True)
        r = apply(n)
        assert "pg_ch_create_index_concurrently" in rule_ids(r)

    def test_where_predicate_triggers_kindE(self, make, apply, rule_ids):
        where = make(Literal, value=True, literal_kind="bool")
        n = _idx(make, where=where)
        r = apply(n)
        assert "pg_ch_create_index_where" in rule_ids(r)

    def test_include_triggers_kindE(self, make, apply, rule_ids):
        col = make(Identifier, name="c")
        n = _idx(make, include=[col])
        r = apply(n)
        assert "pg_ch_create_index_include" in rule_ids(r)

    def test_empty_include_does_not_trigger(self, make, apply, rule_ids):
        n = _idx(make, include=[])
        r = apply(n)
        assert "pg_ch_create_index_include" not in rule_ids(r)

    def test_nulls_distinct_triggers_kindE(self, make, apply, rule_ids):
        n = _idx(make, nulls_distinct=True)
        r = apply(n)
        assert "pg_ch_create_index_nulls_distinct" in rule_ids(r)

    def test_nulls_not_distinct_triggers_kindE(self, make, apply, rule_ids):
        n = _idx(make, nulls_distinct=False)
        r = apply(n)
        assert "pg_ch_create_index_nulls_distinct" in rule_ids(r)

    def test_nulls_distinct_none_does_not_trigger(
        self, make, apply, rule_ids
    ):
        n = _idx(make, nulls_distinct=None)
        r = apply(n)
        assert "pg_ch_create_index_nulls_distinct" not in rule_ids(r)


    def test_unique_concurrent_partial_index_aggregates_E(
        self, make, apply, rule_ids, kinds
    ):
        where = make(Literal, value=True, literal_kind="bool")
        n = _idx(
            make,
            unique=True,
            concurrently=True,
            where=where,
            using_method="gin",
        )
        r = apply(n)
        ids = rule_ids(r)
        assert "pg_ch_create_index_unique" in ids
        assert "pg_ch_create_index_concurrently" in ids
        assert "pg_ch_create_index_where" in ids
        assert "pg_ch_create_index_using" in ids
        assert "pg_ch_create_index_general" in ids
        # E-аннотаций должно быть как минимум три.
        assert kinds(r).count(Kind.E) >= 3
