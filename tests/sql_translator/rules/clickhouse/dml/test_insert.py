"""Правила pg→ch для INSERT.
Источник правил: ``src/sql_translator/ast/rules/clickhouse/dml/insert.py``.
"""
from __future__ import annotations

import pytest

from sql_translator.ast.metadata import Kind
from sql_translator.ast.nodes import (
    DefaultValues,
    Identifier,
    InsertStmt,
    OnConflictClause,
    SelectStmt,
    SelectTarget,
    TableRef,
    ValuesClause,
    WithClause,
)


def _ins(make, **kwargs):
    return make(InsertStmt, target=make(TableRef), **kwargs)


class TestInsertStmtSource:
    def test_values_source_triggers_kindC(self, make, apply, rule_ids, kinds):
        n = _ins(make, source=make(ValuesClause))
        r = apply(n)
        assert "pg_ch_insert_values_txn" in rule_ids(r)
        assert Kind.C in kinds(r)

    def test_select_source_does_not_trigger_C(
        self, make, apply, rule_ids
    ):
        n = _ins(make, source=make(SelectStmt))
        r = apply(n)
        assert "pg_ch_insert_values_txn" not in rule_ids(r)

    def test_default_values_source_does_not_trigger_C(
        self, make, apply, rule_ids
    ):
        n = _ins(make, source=make(DefaultValues))
        r = apply(n)
        assert "pg_ch_insert_values_txn" not in rule_ids(r)


class TestInsertStmtWith:
    def test_with_non_recursive_triggers_kindD(
        self, make, apply, rule_ids, kinds
    ):
        n = _ins(make, with_clause=make(WithClause, recursive=False))
        r = apply(n)
        ids = rule_ids(r)
        assert "pg_ch_insert_with_clause" in ids
        assert "pg_ch_insert_with_recursive" not in ids
        assert Kind.D in kinds(r)

    def test_with_recursive_triggers_kindE_not_D(
        self, make, apply, rule_ids, kinds
    ):
        n = _ins(make, with_clause=make(WithClause, recursive=True))
        r = apply(n)
        ids = rule_ids(r)
        assert "pg_ch_insert_with_recursive" in ids
        assert "pg_ch_insert_with_clause" not in ids
        assert Kind.E in kinds(r)
        assert Kind.D not in kinds(r)

    def test_no_with_clause_does_not_trigger(self, make, apply, rule_ids):
        n = _ins(make)
        r = apply(n)
        ids = rule_ids(r)
        assert "pg_ch_insert_with_clause" not in ids
        assert "pg_ch_insert_with_recursive" not in ids


class TestInsertStmtOptionalFields:
    def test_alias_triggers_kindE(self, make, apply, rule_ids, kinds):
        n = _ins(make, alias=make(Identifier, name="t"))
        r = apply(n)
        assert "pg_ch_insert_alias" in rule_ids(r)
        assert Kind.E in kinds(r)

    @pytest.mark.parametrize("override_value", ["SYSTEM", "USER"])
    def test_overriding_triggers_kindE(
        self, make, apply, rule_ids, override_value
    ):
        n = _ins(make, overriding=override_value)
        r = apply(n)
        assert "pg_ch_insert_overriding" in rule_ids(r)

    def test_returning_triggers_kindE(self, make, apply, rule_ids):
        n = _ins(make, returning=[make(SelectTarget)])
        r = apply(n)
        assert "pg_ch_insert_returning" in rule_ids(r)

    def test_empty_returning_does_not_trigger(self, make, apply, rule_ids):
        n = _ins(make, returning=[])
        r = apply(n)
        assert "pg_ch_insert_returning" not in rule_ids(r)

    def test_combination_alias_overriding_returning(
        self, make, apply, rule_ids, kinds
    ):
        n = _ins(
            make,
            alias=make(Identifier, name="t"),
            overriding="USER",
            returning=[make(SelectTarget)],
        )
        r = apply(n)
        ids = rule_ids(r)
        assert "pg_ch_insert_alias" in ids
        assert "pg_ch_insert_overriding" in ids
        assert "pg_ch_insert_returning" in ids
        assert kinds(r).count(Kind.E) == 3


class TestInsertStmtBase:
    def test_plain_insert_no_annotations(self, make, apply, kinds):
        n = _ins(make)
        r = apply(n)
        assert kinds(r) == []


class TestOnConflictClause:
    def test_do_nothing_triggers_kindE(self, make, apply, rule_ids, kinds):
        n = make(OnConflictClause, action="nothing")
        r = apply(n)
        assert "pg_ch_on_conflict_nothing" in rule_ids(r)
        assert Kind.E in kinds(r)

    def test_do_update_triggers_kindE(self, make, apply, rule_ids, kinds):
        n = make(OnConflictClause, action="update")
        r = apply(n)
        assert "pg_ch_on_conflict_update" in rule_ids(r)
        assert Kind.E in kinds(r)

    def test_do_update_message_mentions_replacing_merge_tree(
        self, make, apply
    ):
        # Сообщение про функциональный суррогат должно упоминать ReplacingMergeTree.
        n = make(OnConflictClause, action="update")
        r = apply(n)
        update_anns = [
            a for a in r.annotations if a.rule_id == "pg_ch_on_conflict_update"
        ]
        assert len(update_anns) == 1
        assert "ReplacingMergeTree" in (update_anns[0].message or "")

    def test_nothing_and_update_are_mutually_exclusive(
        self, make, apply, rule_ids
    ):
        n = make(OnConflictClause, action="nothing")
        r = apply(n)
        ids = rule_ids(r)
        assert "pg_ch_on_conflict_nothing" in ids
        assert "pg_ch_on_conflict_update" not in ids
