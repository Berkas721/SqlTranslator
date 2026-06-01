"""Правила pg→ch для арифметических, битовых, унарных операторов и BETWEEN.

Источник правил: ``src/sql_translator/ast/rules/clickhouse/operators/arithmetic.py``.
"""
from __future__ import annotations

import pytest

from sql_translator.ast.metadata import Kind
from sql_translator.ast.nodes import (
    BetweenExpr,
    BinaryOp,
    FunctionCall,
    Identifier,
    Literal,
    UnaryOp,
)


def _lit(make, value=1):
    return make(Literal, value=value, literal_kind="int", raw=str(value))


def _binop(make, op, left=None, right=None):
    left = left if left is not None else _lit(make, 1)
    right = right if right is not None else _lit(make, 2)
    return make(BinaryOp, op=op, left=left, right=right)


def _unaryop(make, op, operand=None, position="prefix"):
    operand = operand if operand is not None else _lit(make, 4)
    return make(UnaryOp, op=op, operand=operand, position=position)


class TestBinopBase:
    def test_plain_binop_does_not_get_fallback(self, make, apply, rule_ids):
        # Catch-all A блокирует F-fallback для неарифметических операторов.
        n = _binop(make, "=")
        r = apply(n)
        assert "pg_ch.fallback" not in rule_ids(r)


class TestArithmeticOverflow:
    @pytest.mark.parametrize("op,rule_id", [
        ("+", "pg_ch_binop_add"),
        ("-", "pg_ch_binop_sub"),
        ("*", "pg_ch_binop_mul"),
        ("/", "pg_ch_binop_div"),
        ("%", "pg_ch_binop_mod"),
    ])
    def test_arithmetic_ops_trigger_kindC(
        self, make, apply, rule_ids, kinds, op, rule_id
    ):
        n = _binop(make, op)
        r = apply(n)
        assert rule_id in rule_ids(r)
        assert Kind.C in kinds(r)

    def test_plus_does_not_trigger_other_arith_rules(
        self, make, apply, rule_ids
    ):
        n = _binop(make, "+")
        ids = rule_ids(apply(n))
        assert "pg_ch_binop_add" in ids
        for forbidden in (
            "pg_ch_binop_sub", "pg_ch_binop_mul",
            "pg_ch_binop_div", "pg_ch_binop_mod",
        ):
            assert forbidden not in ids

    def test_div_message_mentions_division(self, make, apply):
        n = _binop(make, "/")
        r = apply(n)
        ann = next(a for a in r.annotations if a.rule_id == "pg_ch_binop_div")
        msg = (ann.message or "").lower()
        assert "делени" in msg or "intdiv" in msg


class TestPowRewrite:
    def test_caret_rewrites_to_pow(self, make, apply):
        a, b = _lit(make, 2), _lit(make, 10)
        n = _binop(make, "^", left=a, right=b)
        r = apply(n)
        assert isinstance(r, FunctionCall)
        assert r.name.name == "pow"
        assert r.args == [a, b]

    def test_caret_does_not_become_xor(self, make, apply):
        n = _binop(make, "^")
        r = apply(n)
        assert isinstance(r, FunctionCall)
        assert r.name.name == "pow"

    def test_caret_kindD_annotated(self, make, apply, kinds):
        # Аннотация навешивается на исходный узел; результат — FunctionCall,
        # у которого собственных аннотаций может не быть. Проверяем только rewrite.
        n = _binop(make, "^")
        r = apply(n)
        assert isinstance(r, FunctionCall) and r.name.name == "pow"


class TestBitXorRewrite:
    def test_hash_rewrites_to_bitXor(self, make, apply):
        a, b = _lit(make, 5), _lit(make, 3)
        n = _binop(make, "#", left=a, right=b)
        r = apply(n)
        assert isinstance(r, FunctionCall)
        assert r.name.name == "bitXor"
        assert r.args == [a, b]


class TestIsDistinct:
    @pytest.mark.parametrize("op", [
        "IS DISTINCT FROM", "IS NOT DISTINCT FROM",
    ])
    def test_is_distinct_triggers_kindE(
        self, make, apply, rule_ids, kinds, op
    ):
        n = _binop(make, op)
        r = apply(n)
        assert "pg_ch_binop_is_distinct" in rule_ids(r)
        assert Kind.E in kinds(r)

    def test_equality_does_not_trigger_distinct(self, make, apply, rule_ids):
        n = _binop(make, "=")
        r = apply(n)
        assert "pg_ch_binop_is_distinct" not in rule_ids(r)


class TestUnarySqrt:
    def test_sqrt_op_rewrites_to_sqrt_fn(self, make, apply):
        x = _lit(make, 9)
        n = _unaryop(make, "|/", operand=x)
        r = apply(n)
        assert isinstance(r, FunctionCall)
        assert r.name.name == "sqrt"
        assert r.args == [x]


class TestUnaryCbrt:
    def test_cbrt_op_rewrites_to_cbrt_fn(self, make, apply):
        x = _lit(make, 27)
        n = _unaryop(make, "||/", operand=x)
        r = apply(n)
        assert isinstance(r, FunctionCall)
        assert r.name.name == "cbrt"


class TestUnaryFactorial:
    def test_postfix_bang_rewrites_to_factorial_fn(self, make, apply):
        x = _lit(make, 5)
        n = _unaryop(make, "!", operand=x, position="postfix")
        r = apply(n)
        assert isinstance(r, FunctionCall)
        assert r.name.name == "factorial"

    def test_prefix_bang_does_not_match(self, make, apply, rule_ids):
        # Префиксный ! — отрицание, не факториал.
        n = _unaryop(make, "!", position="prefix")
        r = apply(n)
        assert isinstance(r, UnaryOp)  # rewrite не сработал
        assert "pg_ch_unaryop_factorial" not in rule_ids(r)


class TestUnaryAbsAt:
    def test_at_triggers_kindE(self, make, apply, rule_ids, kinds):
        n = _unaryop(make, "@")
        r = apply(n)
        assert "pg_ch_unaryop_abs" in rule_ids(r)
        assert Kind.E in kinds(r)

    def test_at_is_not_rewritten(self, make, apply):
        n = _unaryop(make, "@")
        r = apply(n)
        # Только аннотация, нет автозамены на abs().
        assert isinstance(r, UnaryOp)


class TestUnaryBase:
    def test_minus_is_just_base_no_fallback(self, make, apply, rule_ids):
        n = _unaryop(make, "-")
        r = apply(n)
        assert "pg_ch.fallback" not in rule_ids(r)
        # Никаких специфичных операторных правил.
        for forbidden in (
            "pg_ch_unaryop_sqrt", "pg_ch_unaryop_cbrt",
            "pg_ch_unaryop_factorial", "pg_ch_unaryop_abs",
        ):
            assert forbidden not in rule_ids(r)


class TestBetween:
    def test_plain_between_no_fallback(self, make, apply, rule_ids):
        n = make(BetweenExpr,
                 expr=_lit(make, 5), low=_lit(make, 1), high=_lit(make, 10))
        r = apply(n)
        assert "pg_ch.fallback" not in rule_ids(r)
        assert "pg_ch_between_symmetric" not in rule_ids(r)

    def test_symmetric_triggers_kindE(self, make, apply, rule_ids, kinds):
        n = make(BetweenExpr,
                 expr=_lit(make, 5), low=_lit(make, 1), high=_lit(make, 10),
                 symmetric=True)
        r = apply(n)
        assert "pg_ch_between_symmetric" in rule_ids(r)
        assert Kind.E in kinds(r)

    def test_negated_alone_does_not_trigger_symmetric(
        self, make, apply, rule_ids
    ):
        n = make(BetweenExpr,
                 expr=_lit(make, 5), low=_lit(make, 1), high=_lit(make, 10),
                 negated=True, symmetric=False)
        r = apply(n)
        assert "pg_ch_between_symmetric" not in rule_ids(r)
