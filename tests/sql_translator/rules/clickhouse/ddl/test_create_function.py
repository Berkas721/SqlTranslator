"""Правила pg→ch для CreateFunctionStmt.

Источник правил: ``src/sql_translator/ast/rules/clickhouse/ddl/create_function.py``.
"""
from __future__ import annotations

from sql_translator.ast.metadata import Kind
from sql_translator.ast.nodes import CreateFunctionStmt, TableRef


def _fn(make, **kwargs):
    return make(CreateFunctionStmt, name=make(TableRef), **kwargs)


class TestCreateFunctionStmt:
    def test_plain_function_only_kindA_no_annotation(
        self, make, apply, kinds
    ):
        n = _fn(make)
        r = apply(n)
        assert kinds(r) == []

    def test_or_replace_triggers_kindC(self, make, apply, rule_ids, kinds):
        n = _fn(make, or_replace=True)
        r = apply(n)
        assert "pg_ch_create_function_or_replace" in rule_ids(r)
        assert Kind.C in kinds(r)

    def test_body_triggers_kindD(self, make, apply, rule_ids, kinds):
        n = _fn(make, body="SELECT 1")
        r = apply(n)
        assert "pg_ch_create_function_body" in rule_ids(r)
        assert Kind.D in kinds(r)

    def test_language_triggers_kindD_even_without_body(
        self, make, apply, rule_ids
    ):
        n = _fn(make, language="sql")
        r = apply(n)
        assert "pg_ch_create_function_body" in rule_ids(r)

    def test_body_and_language_trigger_rule_once(
        self, make, apply, rule_ids
    ):
        n = _fn(make, body="SELECT 1", language="sql")
        r = apply(n)
        ids = rule_ids(r)
        # ``when`` срабатывает по дизъюнкции — само правило одно, регистрируется один раз.
        assert ids.count("pg_ch_create_function_body") == 1

    def test_or_replace_and_body_yield_C_and_D(self, make, apply, kinds):
        n = _fn(make, or_replace=True, body="SELECT 1", language="sql")
        r = apply(n)
        ks = kinds(n)
        assert Kind.C in ks
        assert Kind.D in ks

    def test_no_body_no_language_does_not_trigger(self, make, apply, rule_ids):
        n = _fn(make, body=None, language=None)
        r = apply(n)
        assert "pg_ch_create_function_body" not in rule_ids(r)
