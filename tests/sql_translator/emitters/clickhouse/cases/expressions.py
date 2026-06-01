"""Кейсы для выражений: BinaryOp, UnaryOp, FunctionCall, Cast, Case,
SubqueryExpr (только EXISTS/NOT EXISTS), ParamRef, Between/Like/SimilarTo."""
from __future__ import annotations

import pytest

from sql_translator.ast.nodes import (
    BetweenExpr,
    BinaryOp,
    Cast,
    CaseExpr,
    FunctionCall,
    Identifier,
    LikeExpr,
    Literal,
    OrderByItem,
    ParamRef,
    SimilarToExpr,
    StarExpr,
    TypeRef,
    UnaryOp,
    WhenBranch,
)


def _ident(make, name, quoted=False):
    return make(Identifier, name=name, quoted=quoted)


def _lit(make, value=1, kind="int", raw=None):
    return make(Literal, value=value, literal_kind=kind,
                raw=raw if raw is not None else str(value))


def _str(make, s):
    return make(Literal, value=s, literal_kind="string", raw=s)


CASES: list = [
    # ── BinaryOp ─────────────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(BinaryOp, op="+", left=_lit(m, 1), right=_lit(m, 2)),
        "1 + 2",
        id="binop-add",
    ),
    pytest.param(
        lambda m: m(BinaryOp, op="*",
                    left=m(BinaryOp, op="+", left=_lit(m, 1), right=_lit(m, 2)),
                    right=_lit(m, 3)),
        "(1 + 2) * 3",
        id="binop-nested-left-parens",
    ),
    pytest.param(
        lambda m: m(BinaryOp, op="-",
                    left=_lit(m, 1),
                    right=m(BinaryOp, op="-", left=_lit(m, 2), right=_lit(m, 3))),
        "1 - (2 - 3)",
        id="binop-nested-right-parens",
    ),

    # ── UnaryOp ──────────────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(UnaryOp, op="-", position="prefix", operand=_lit(m, 1)),
        "-1",
        id="unary-prefix-minus",
    ),
    pytest.param(
        lambda m: m(UnaryOp, op="NOT", position="prefix", operand=_lit(m, True, "bool")),
        "NOT true",
        id="unary-prefix-alpha-not",
    ),
    pytest.param(
        lambda m: m(UnaryOp, op="IS NULL", position="postfix",
                    operand=_ident(m, "x")),
        "xIS NULL",
        id="unary-postfix",
    ),

    # ── FunctionCall ─────────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(FunctionCall, name=_ident(m, "count"), star=True),
        "count(*)",
        id="func-count-star",
    ),
    pytest.param(
        lambda m: m(FunctionCall, name=_ident(m, "abs"),
                    args=[_lit(m, -5)]),
        "abs(-5)",
        id="func-one-arg",
    ),
    pytest.param(
        lambda m: m(FunctionCall, name=_ident(m, "coalesce"),
                    args=[_ident(m, "a"), _ident(m, "b"), _lit(m, 0)]),
        "coalesce(a, b, 0)",
        id="func-multi-args",
    ),
    pytest.param(
        lambda m: m(FunctionCall, name=_ident(m, "count"),
                    distinct=True, args=[_ident(m, "x")]),
        "count(DISTINCT x)",
        id="func-distinct",
    ),
    pytest.param(
        lambda m: m(FunctionCall, name=_ident(m, "quantile"),
                    parameters=[_lit(m, 0.5, "float", "0.5")],
                    args=[_ident(m, "x")]),
        "quantile(0.5)(x)",
        id="func-parametric",
    ),
    pytest.param(
        lambda m: m(FunctionCall, name=_ident(m, "groupArray"),
                    args=[_ident(m, "x")],
                    order_by=[m(OrderByItem, expression=_ident(m, "x"),
                                direction="DESC")]),
        "groupArray(x ORDER BY x DESC)",
        id="func-with-order-by",
    ),

    # ── Cast ─────────────────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(Cast, style="cast", expression=_lit(m, 1),
                    target_type=m(TypeRef, name="String")),
        "CAST(1 AS String)",
        id="cast-cast",
    ),
    pytest.param(
        lambda m: m(Cast, style="postfix", expression=_lit(m, 1),
                    target_type=m(TypeRef, name="String")),
        "CAST(1 AS String)",
        id="cast-postfix-emits-cast",
    ),
    pytest.param(
        lambda m: m(Cast, style="typed_fn", expression=_lit(m, 1),
                    target_type=m(TypeRef, name="UInt32")),
        "UInt32(1)",
        id="cast-typed-fn",
    ),
    pytest.param(
        lambda m: m(Cast, style="typed_literal",
                    expression=_str(m, "2024-01-01"),
                    target_type=m(TypeRef, name="DATE")),
        "DATE '2024-01-01'",
        id="cast-typed-literal",
    ),

    # ── CaseExpr ─────────────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(CaseExpr, branches=[
            m(WhenBranch, condition=m(BinaryOp, op="=",
                                       left=_ident(m, "x"), right=_lit(m, 1)),
              result=_str(m, "one")),
        ], else_expr=_str(m, "other")),
        "CASE WHEN x = 1 THEN 'one' ELSE 'other' END",
        id="case-searched",
    ),
    pytest.param(
        lambda m: m(CaseExpr, arg=_ident(m, "x"), branches=[
            m(WhenBranch, condition=_lit(m, 1), result=_str(m, "one")),
            m(WhenBranch, condition=_lit(m, 2), result=_str(m, "two")),
        ]),
        "CASE x WHEN 1 THEN 'one' WHEN 2 THEN 'two' END",
        id="case-simple",
    ),

    # ── ParamRef ─────────────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(ParamRef, number=1),
        "$1",
        id="paramref-number",
    ),
    pytest.param(
        lambda m: m(ParamRef, name="user_id"),
        "{user_id}",
        id="paramref-name",
    ),
    pytest.param(
        lambda m: m(ParamRef),
        "?",
        id="paramref-anon",
    ),

    # ── BetweenExpr ──────────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(BetweenExpr, expr=_ident(m, "x"),
                    low=_lit(m, 1), high=_lit(m, 10)),
        "x BETWEEN 1 AND 10",
        id="between-plain",
    ),
    pytest.param(
        lambda m: m(BetweenExpr, expr=_ident(m, "x"),
                    low=_lit(m, 1), high=_lit(m, 10), negated=True),
        "x NOT BETWEEN 1 AND 10",
        id="between-negated",
    ),
    pytest.param(
        lambda m: m(BetweenExpr, expr=_ident(m, "x"),
                    low=_lit(m, 1), high=_lit(m, 10), symmetric=True),
        "x BETWEEN SYMMETRIC 1 AND 10",
        id="between-symmetric",
    ),

    # ── LikeExpr ─────────────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(LikeExpr, string=_ident(m, "x"), pattern=_str(m, "a%")),
        "x LIKE 'a%'",
        id="like-plain",
    ),
    pytest.param(
        lambda m: m(LikeExpr, string=_ident(m, "x"), pattern=_str(m, "a%"),
                    negated=True),
        "x NOT LIKE 'a%'",
        id="like-not",
    ),
    pytest.param(
        lambda m: m(LikeExpr, string=_ident(m, "x"), pattern=_str(m, "a%"),
                    case_insensitive=True),
        "x ILIKE 'a%'",
        id="like-ilike",
    ),
    pytest.param(
        lambda m: m(LikeExpr, string=_ident(m, "x"), pattern=_str(m, "a%"),
                    escape=_str(m, "\\")),
        "x LIKE 'a%' ESCAPE '\\\\'",
        id="like-escape",
    ),

    # ── SimilarToExpr ────────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(SimilarToExpr, string=_ident(m, "x"), pattern=_str(m, "a%")),
        "x SIMILAR TO 'a%'",
        id="similar-plain",
    ),
    pytest.param(
        lambda m: m(SimilarToExpr, string=_ident(m, "x"), pattern=_str(m, "a%"),
                    negated=True),
        "x NOT SIMILAR TO 'a%'",
        id="similar-negated",
    ),
]
