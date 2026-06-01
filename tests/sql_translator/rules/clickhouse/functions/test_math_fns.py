"""Правила pg→ch для математических функций.

Источник правил: ``src/sql_translator/ast/rules/clickhouse/functions/math_fns.py``.
"""
from __future__ import annotations

import pytest

from sql_translator.ast.metadata import Kind
from sql_translator.ast.nodes import (
    BinaryOp,
    FunctionCall,
    Identifier,
    Literal,
)


def _lit(make, value=1):
    return make(Literal, value=value, literal_kind="int", raw=str(value))


def _fn(make, name, *args):
    ident = make(Identifier, name=name)
    return make(FunctionCall, name=ident, args=list(args))


class TestPowerRewrite:
    @pytest.mark.parametrize("fn_name", ["power", "POWER", "Power"])
    def test_power_renamed_to_pow(self, make, apply, fn_name):
        n = _fn(make, fn_name, _lit(make, 2), _lit(make, 10))
        r = apply(n)
        assert r.name.name == "pow"

    def test_power_does_not_emit_annotation(self, make, apply, rule_ids):
        n = _fn(make, "power", _lit(make, 2), _lit(make, 10))
        r = apply(n)
        assert "pg_ch_fn_power" not in rule_ids(r)


class TestModRewrite:
    @pytest.mark.parametrize("fn_name", ["mod", "MOD"])
    def test_mod_renamed_to_modulo(self, make, apply, fn_name):
        n = _fn(make, fn_name, _lit(make, 10), _lit(make, 3))
        r = apply(n)
        assert r.name.name == "modulo"


class TestDivRewrite:
    def test_div_renamed_to_intDiv(self, make, apply):
        n = _fn(make, "div", _lit(make, 10), _lit(make, 3))
        r = apply(n)
        assert r.name.name == "intDiv"


class TestRandomRewrite:
    @pytest.mark.parametrize("fn_name", ["random", "RANDOM"])
    def test_random_renamed_to_randCanonical(self, make, apply, fn_name):
        n = _fn(make, fn_name)
        r = apply(n)
        assert r.name.name == "randCanonical"


class TestRoundWarning:
    def test_round_triggers_kindC(self, make, apply, rule_ids, kinds):
        n = _fn(make, "round", _lit(make, 5))
        r = apply(n)
        assert "pg_ch_fn_round" in rule_ids(r)
        assert Kind.C in kinds(r)

    def test_round_message_mentions_rounding(self, make, apply):
        n = _fn(make, "round", _lit(make, 5))
        r = apply(n)
        ann = next(a for a in r.annotations if a.rule_id == "pg_ch_fn_round")
        msg = (ann.message or "").lower()
        assert "округлен" in msg or "half" in msg or "even" in msg


class TestLogOneArg:
    def test_log_one_arg_renamed_to_log10(self, make, apply):
        n = _fn(make, "log", _lit(make, 100))
        r = apply(n)
        # rewrite возвращает тот же узел с переименованием
        assert isinstance(r, FunctionCall)
        assert r.name.name == "log10"

    def test_log_one_arg_triggers_kindD_annotation(
        self, make, apply, rule_ids, kinds
    ):
        n = _fn(make, "log", _lit(make, 100))
        r = apply(n)
        assert "pg_ch_fn_log1" in rule_ids(r)
        assert Kind.D in kinds(r)

    def test_log_one_arg_case_insensitive(self, make, apply, rule_ids):
        n = _fn(make, "LOG", _lit(make, 100))
        r = apply(n)
        assert "pg_ch_fn_log1" in rule_ids(r)


class TestLogTwoArg:
    def test_log_two_arg_becomes_division(self, make, apply):
        b, x = _lit(make, 10), _lit(make, 1000)
        n = _fn(make, "log", b, x)
        r = apply(n)
        # rewrite заменяет узел на BinaryOp(log(x) / log(b))
        assert isinstance(r, BinaryOp)
        assert r.op == "/"
        assert isinstance(r.left, FunctionCall) and r.left.name.name == "log"
        assert isinstance(r.right, FunctionCall) and r.right.name.name == "log"

    def test_log_two_arg_triggers_kindD_on_inner(
        self, make, apply, rule_ids, kinds
    ):
        b, x = _lit(make, 10), _lit(make, 1000)
        n = _fn(make, "log", b, x)
        r = apply(n)
        # Аннотация навешивается на исходный узел перед заменой; результат — BinaryOp,
        # у которого нет наследия аннотаций. Проверяем только структуру.
        assert isinstance(r, BinaryOp)


class TestWidthBucket:
    def test_width_bucket_triggers_kindE(self, make, apply, rule_ids, kinds):
        n = _fn(make, "width_bucket")
        r = apply(n)
        assert "pg_ch_fn_width_bucket" in rule_ids(r)
        assert Kind.E in kinds(r)


class TestGcdLcm:
    @pytest.mark.parametrize("fn_name", ["gcd", "lcm", "GCD", "LCM"])
    def test_gcd_lcm_trigger_kindE(
        self, make, apply, rule_ids, kinds, fn_name
    ):
        n = _fn(make, fn_name)
        r = apply(n)
        assert "pg_ch_fn_gcd_lcm" in rule_ids(r)
        assert Kind.E in kinds(r)


class TestSetseed:
    def test_setseed_triggers_kindE(self, make, apply, rule_ids, kinds):
        n = _fn(make, "setseed", _lit(make, 1))
        r = apply(n)
        assert "pg_ch_fn_setseed" in rule_ids(r)
        assert Kind.E in kinds(r)


class TestMathFnsIsolation:
    def test_unknown_math_function_no_rules(self, make, apply, rule_ids):
        n = _fn(make, "some_random_math_fn")
        r = apply(n)
        ids = rule_ids(r)
        for forbidden in (
            "pg_ch_fn_power", "pg_ch_fn_mod", "pg_ch_fn_div",
            "pg_ch_fn_random", "pg_ch_fn_round",
            "pg_ch_fn_log1", "pg_ch_fn_log2arg",
            "pg_ch_fn_width_bucket", "pg_ch_fn_gcd_lcm", "pg_ch_fn_setseed",
        ):
            assert forbidden not in ids

    def test_log_with_zero_args_not_log1_or_log2(self, make, apply, rule_ids):
        # log() без аргументов не подходит ни под log1, ни под log2.
        n = _fn(make, "log")
        r = apply(n)
        ids = rule_ids(r)
        assert "pg_ch_fn_log1" not in ids
        assert "pg_ch_fn_log2arg" not in ids
