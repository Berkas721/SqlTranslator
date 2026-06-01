"""Правила pg→ch для условных выражений и функций.

Источник правил: ``src/sql_translator/ast/rules/clickhouse/expressions/conditionals.py``.
"""
from __future__ import annotations

import pytest

from sql_translator.ast.metadata import Kind
from sql_translator.ast.nodes import (
    CaseExpr,
    FunctionCall,
    Identifier,
    Literal,
    WhenBranch,
)


def _fn(make, name, **kwargs):
    ident = make(Identifier, name=name)
    return make(FunctionCall, name=ident, **kwargs)


class TestCaseExpr:
    def test_empty_case_gets_kindC(self, make, apply, rule_ids, kinds):
        n = make(CaseExpr)
        r = apply(n)
        assert "pg_ch_case_short_circuit" in rule_ids(r)
        assert Kind.C in kinds(r)

    def test_case_with_branches_still_kindC(
        self, make, apply, kinds
    ):
        cond = make(Literal, value=True, literal_kind="bool")
        res = make(Literal, value=1, literal_kind="int", raw="1")
        branch = make(WhenBranch, condition=cond, result=res)
        n = make(CaseExpr, branches=[branch])
        r = apply(n)
        assert Kind.C in kinds(r)

    def test_case_kindC_annotation_mentions_short_circuit(
        self, make, apply
    ):
        n = make(CaseExpr)
        r = apply(n)
        ann = next(
            a for a in r.annotations
            if a.rule_id == "pg_ch_case_short_circuit"
        )
        msg = (ann.message or "")
        # Ключевое: упоминается порядок вычисления / lazy/eager.
        assert "ленив" in msg or "eager" in msg or "WHEN" in msg

    def test_case_produces_single_annotation(self, make, apply):
        n = make(CaseExpr)
        r = apply(n)
        # Для CaseExpr нет catch-all A — только одно C-правило.
        assert len(r.annotations) == 1


class TestCoalesce:
    @pytest.mark.parametrize("name_value", ["coalesce", "COALESCE", "Coalesce"])
    def test_coalesce_case_insensitive_triggers_kindC(
        self, make, apply, rule_ids, kinds, name_value
    ):
        n = _fn(make, name_value)
        r = apply(n)
        assert "pg_ch_fn_coalesce" in rule_ids(r)
        assert Kind.C in kinds(r)

    def test_other_functions_do_not_trigger_coalesce_rule(
        self, make, apply, rule_ids
    ):
        n = _fn(make, "ifnull")
        r = apply(n)
        assert "pg_ch_fn_coalesce" not in rule_ids(r)


class TestGreatestLeast:
    @pytest.mark.parametrize("fn_name,rule_id", [
        ("greatest", "pg_ch_fn_greatest"),
        ("least",    "pg_ch_fn_least"),
        ("GREATEST", "pg_ch_fn_greatest"),
        ("Least",    "pg_ch_fn_least"),
    ])
    def test_greatest_least_trigger_kindD(
        self, make, apply, rule_ids, kinds, fn_name, rule_id
    ):
        n = _fn(make, fn_name)
        r = apply(n)
        assert rule_id in rule_ids(r)
        assert Kind.D in kinds(r)

    def test_greatest_does_not_trigger_least_rule(
        self, make, apply, rule_ids
    ):
        n = _fn(make, "greatest")
        r = apply(n)
        ids = rule_ids(r)
        assert "pg_ch_fn_greatest" in ids
        assert "pg_ch_fn_least" not in ids


class TestDecode:
    @pytest.mark.parametrize("name_value", ["decode", "DECODE", "Decode"])
    def test_decode_triggers_kindE(
        self, make, apply, rule_ids, kinds, name_value
    ):
        n = _fn(make, name_value)
        r = apply(n)
        assert "pg_ch_fn_decode" in rule_ids(r)
        assert Kind.E in kinds(r)


class TestPlainFunctionCall:
    def test_unknown_function_only_catchall(
        self, make, apply, rule_ids, kinds
    ):
        n = _fn(make, "some_random_fn")
        r = apply(n)
        # Catch-all A без аннотации, специфичных правил нет.
        ids = rule_ids(r)
        # Никакой F-fallback не появляется (catch-all блокирует).
        assert "pg_ch.fallback" not in ids
        # Ни одной из условных аннотаций.
        for forbidden in (
            "pg_ch_fn_coalesce", "pg_ch_fn_greatest",
            "pg_ch_fn_least", "pg_ch_fn_decode",
        ):
            assert forbidden not in ids

    def test_function_call_without_name_does_not_match_specific_rules(
        self, make, apply, rule_ids
    ):
        # _fn_name безопасно возвращает "" для name=None.
        n = make(FunctionCall, name=None)
        r = apply(n)
        ids = rule_ids(r)
        assert "pg_ch_fn_coalesce" not in ids
        assert "pg_ch_fn_decode" not in ids
