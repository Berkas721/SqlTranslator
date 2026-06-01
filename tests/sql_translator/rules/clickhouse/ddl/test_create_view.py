"""Правила pg→ch для CreateViewStmt.

Источник правил: ``src/sql_translator/ast/rules/clickhouse/ddl/create_view.py``.
"""
from __future__ import annotations

from sql_translator.ast.metadata import Kind
from sql_translator.ast.nodes import (
    CreateViewStmt,
    Identifier,
    TableRef,
)


def _view(make, **kwargs):
    name = make(TableRef)
    return make(CreateViewStmt, name=name, **kwargs)


class TestCreateViewStmt:

    def test_plain_view_only_kindA_no_annotation(self, make, apply, kinds):
        n = _view(make)
        r = apply(n)
        assert kinds(r) == []


    def test_materialized_view_triggers_kindC(
        self, make, apply, rule_ids, kinds
    ):
        n = _view(make, is_materialized=True)
        r = apply(n)
        assert "pg_ch_create_view_materialized" in rule_ids(r)
        assert Kind.C in kinds(r)


    def test_column_names_triggers_kindD(self, make, apply, rule_ids, kinds):
        col = make(Identifier, name="a")
        n = _view(make, column_names=[col])
        r = apply(n)
        assert "pg_ch_create_view_column_names" in rule_ids(r)
        assert Kind.D in kinds(r)

    def test_security_barrier_triggers_kindD(self, make, apply, rule_ids):
        n = _view(make, security_barrier=True)
        r = apply(n)
        assert "pg_ch_create_view_security" in rule_ids(r)

    def test_security_invoker_triggers_kindD(self, make, apply, rule_ids):
        n = _view(make, security_invoker=True)
        r = apply(n)
        assert "pg_ch_create_view_security" in rule_ids(r)

    def test_with_data_true_triggers_kindD(self, make, apply, rule_ids):
        n = _view(make, with_data=True)
        r = apply(n)
        assert "pg_ch_create_view_with_data" in rule_ids(r)

    def test_with_data_false_triggers_kindD(self, make, apply, rule_ids):
        # WITH NO DATA — поле = False (а не None), правило тоже срабатывает.
        n = _view(make, with_data=False)
        r = apply(n)
        assert "pg_ch_create_view_with_data" in rule_ids(r)

    def test_with_data_none_does_not_trigger(self, make, apply, rule_ids):
        n = _view(make, with_data=None)
        r = apply(n)
        assert "pg_ch_create_view_with_data" not in rule_ids(r)

    def test_materialized_with_no_data_triggers_refresh_rule(
        self, make, apply, rule_ids
    ):
        n = _view(make, is_materialized=True, with_data=False)
        r = apply(n)
        ids = rule_ids(r)
        assert "pg_ch_create_view_materialized" in ids
        assert "pg_ch_create_view_refresh" in ids
        assert "pg_ch_create_view_with_data" in ids

    def test_materialized_with_data_does_not_trigger_refresh(
        self, make, apply, rule_ids
    ):
        n = _view(make, is_materialized=True, with_data=True)
        r = apply(n)
        assert "pg_ch_create_view_refresh" not in rule_ids(r)

    def test_non_materialized_with_no_data_does_not_trigger_refresh(
        self, make, apply, rule_ids
    ):
        n = _view(make, is_materialized=False, with_data=False)
        r = apply(n)
        assert "pg_ch_create_view_refresh" not in rule_ids(r)


    def test_temporary_triggers_kindE(self, make, apply, rule_ids, kinds):
        n = _view(make, temporary=True)
        r = apply(n)
        assert "pg_ch_create_view_temporary" in rule_ids(r)
        assert Kind.E in kinds(r)

    def test_recursive_triggers_kindE(self, make, apply, rule_ids):
        n = _view(make, recursive=True)
        r = apply(n)
        assert "pg_ch_create_view_recursive" in rule_ids(r)

    def test_check_option_triggers_kindE(self, make, apply, rule_ids):
        n = _view(make, check_option="CASCADED")
        r = apply(n)
        assert "pg_ch_create_view_check_option" in rule_ids(r)

    def test_check_option_none_does_not_trigger(self, make, apply, rule_ids):
        n = _view(make, check_option=None)
        r = apply(n)
        assert "pg_ch_create_view_check_option" not in rule_ids(r)


    def test_rules_do_not_mutate_fields(self, make, apply):
        n = _view(make, is_materialized=True, temporary=True, recursive=True)
        r = apply(n)
        assert r.is_materialized is True
        assert r.temporary is True
        assert r.recursive is True
