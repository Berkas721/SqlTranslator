"""Правила pg→ch для строковых операторов (POSIX, LIKE, SIMILAR TO).

Источник правил: ``src/sql_translator/ast/rules/clickhouse/operators/string_ops.py``.
"""
from __future__ import annotations

import pytest

from sql_translator.ast.metadata import Kind
from sql_translator.ast.nodes import (
    BinaryOp,
    FunctionCall,
    Identifier,
    LikeExpr,
    Literal,
    SimilarToExpr,
    UnaryOp,
)


def _str_lit(make, value="abc"):
    return make(Literal, value=value, literal_kind="string", raw=repr(value))


def _ident(make, name):
    return make(Identifier, name=name)


def _binop(make, op, left=None, right=None):
    left = left if left is not None else _ident(make, "s")
    right = right if right is not None else _str_lit(make, "^a")
    return make(BinaryOp, op=op, left=left, right=right)


class TestPosixMatch:
    def test_tilde_rewrites_to_match(self, make, apply):
        s, pat = _ident(make, "s"), _str_lit(make, "^a")
        n = _binop(make, "~", left=s, right=pat)
        r = apply(n)
        assert isinstance(r, FunctionCall)
        assert r.name.name == "match"
        assert r.args == [s, pat]


class TestPosixNotMatch:
    def test_bang_tilde_rewrites_to_NOT_match(self, make, apply):
        n = _binop(make, "!~")
        r = apply(n)
        # NOT(match(...))
        assert isinstance(r, UnaryOp)
        assert r.op == "NOT"
        inner = r.operand
        assert isinstance(inner, FunctionCall)
        assert inner.name.name == "match"


class TestPosixIMatch:
    def test_tilde_star_rewrites_to_match_with_ci_prefix(self, make, apply):
        s, pat = _ident(make, "s"), _str_lit(make, "^a")
        n = _binop(make, "~*", left=s, right=pat)
        r = apply(n)
        assert isinstance(r, FunctionCall)
        assert r.name.name == "match"
        # Второй аргумент — concat('(?i)', pattern).
        concat = r.args[1]
        assert isinstance(concat, FunctionCall)
        assert concat.name.name == "concat"
        assert isinstance(concat.args[0], Literal)
        assert concat.args[0].value == "(?i)"


class TestPosixNotIMatch:
    def test_bang_tilde_star_rewrites_to_NOT_match_with_ci(self, make, apply):
        n = _binop(make, "!~*")
        r = apply(n)
        assert isinstance(r, UnaryOp) and r.op == "NOT"
        inner = r.operand
        assert isinstance(inner, FunctionCall) and inner.name.name == "match"
        concat = inner.args[1]
        assert isinstance(concat, FunctionCall) and concat.name.name == "concat"


class TestPosixIsolation:
    def test_eq_does_not_become_match(self, make, apply):
        n = _binop(make, "=")
        r = apply(n)
        assert isinstance(r, BinaryOp)


class TestLikeBase:
    def test_plain_like_no_fallback_no_escape_rule(
        self, make, apply, rule_ids
    ):
        n = make(LikeExpr,
                 string=_ident(make, "s"),
                 pattern=_str_lit(make, "abc%"))
        r = apply(n)
        ids = rule_ids(r)
        assert "pg_ch.fallback" not in ids
        assert "pg_ch_like_escape" not in ids


class TestLikeEscape:
    def test_escape_triggers_kindC(self, make, apply, rule_ids, kinds):
        n = make(LikeExpr,
                 string=_ident(make, "s"),
                 pattern=_str_lit(make, "abc%"),
                 escape=_str_lit(make, "\\"))
        r = apply(n)
        assert "pg_ch_like_escape" in rule_ids(r)
        assert Kind.C in kinds(r)

    def test_ilike_with_escape_also_triggers(self, make, apply, rule_ids):
        n = make(LikeExpr,
                 string=_ident(make, "s"),
                 pattern=_str_lit(make, "abc%"),
                 escape=_str_lit(make, "\\"),
                 case_insensitive=True)
        r = apply(n)
        assert "pg_ch_like_escape" in rule_ids(r)

    def test_negated_with_escape_also_triggers(self, make, apply, rule_ids):
        n = make(LikeExpr,
                 string=_ident(make, "s"),
                 pattern=_str_lit(make, "abc%"),
                 escape=_str_lit(make, "\\"),
                 negated=True)
        r = apply(n)
        assert "pg_ch_like_escape" in rule_ids(r)


class TestSimilarToLiteral:
    def test_similar_to_string_literal_rewrites_to_match(self, make, apply):
        s = _ident(make, "s")
        pat = _str_lit(make, "a%_b")
        n = make(SimilarToExpr, string=s, pattern=pat)
        r = apply(n)
        assert isinstance(r, FunctionCall)
        assert r.name.name == "match"
        # Паттерн конвертирован: % → .*, _ → ., обёрнут в ^(?:...)$.
        new_pat = r.args[1]
        assert isinstance(new_pat, Literal)
        assert new_pat.value == "^(?:a.*.b)$"

    def test_similar_to_non_literal_keeps_pattern_unchanged(
        self, make, apply
    ):
        s = _ident(make, "s")
        pat = _ident(make, "pattern_col")
        n = make(SimilarToExpr, string=s, pattern=pat)
        r = apply(n)
        assert isinstance(r, FunctionCall) and r.name.name == "match"
        # Паттерн — Identifier, не конвертирован.
        assert r.args[1] is pat

    def test_similar_to_negated_wraps_in_NOT(self, make, apply):
        s = _ident(make, "s")
        pat = _str_lit(make, "a%")
        n = make(SimilarToExpr, string=s, pattern=pat, negated=True)
        r = apply(n)
        assert isinstance(r, UnaryOp) and r.op == "NOT"
        inner = r.operand
        assert isinstance(inner, FunctionCall) and inner.name.name == "match"

    def test_similar_to_underscore_only(self, make, apply):
        s = _ident(make, "s")
        pat = _str_lit(make, "___")
        n = make(SimilarToExpr, string=s, pattern=pat)
        r = apply(n)
        assert r.args[1].value == "^(?:...)$"

    def test_similar_to_no_metacharacters(self, make, apply):
        s = _ident(make, "s")
        pat = _str_lit(make, "abc")
        n = make(SimilarToExpr, string=s, pattern=pat)
        r = apply(n)
        assert r.args[1].value == "^(?:abc)$"


class TestSimilarToBase:
    def test_similar_to_base_no_fallback(self, make, apply, rule_ids):
        n = make(SimilarToExpr,
                 string=_ident(make, "s"),
                 pattern=_str_lit(make, "x"))
        r = apply(n)
        # После rewrite результат — FunctionCall, а не SimilarToExpr.
        assert isinstance(r, FunctionCall)
