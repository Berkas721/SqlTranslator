"""Правила преобразования строковых операторов и паттерн-матчинга: PostgreSQL → ClickHouse.
"""
from __future__ import annotations

from src.ast.metadata import Dialect, Kind
from src.ast.nodes import (
    BinaryOp, FunctionCall, Identifier, LikeExpr, Literal, SimilarToExpr, UnaryOp,
)
from src.ast.registry import Rule, TranslateContext, default_translator


def _make_fn(dialect: Dialect, name: str, *args) -> FunctionCall:
    fn = FunctionCall()
    fn.node_kind = "FunctionCall"
    fn.dialect = dialect
    ident = Identifier()
    ident.node_kind = "Identifier"
    ident.dialect = dialect
    ident.name = name
    fn.name = ident
    fn.args = list(args)
    return fn


def _make_not(dialect: Dialect, expr) -> UnaryOp:
    u = UnaryOp(op="NOT", position="prefix", operand=expr)
    u.node_kind = "UnaryOp"
    u.dialect = dialect
    return u


def _make_concat_ci(dialect: Dialect, pattern_expr) -> FunctionCall:
    """concat('(?i)', pattern) — добавляет флаг регистронезависимости."""
    prefix = Literal()
    prefix.node_kind = "Literal"
    prefix.dialect = dialect
    prefix.value = "(?i)"
    prefix.literal_kind = "string"
    prefix.raw = "'(?i)'"
    return _make_fn(dialect, "concat", prefix, pattern_expr)


def _convert_similar_pattern(pattern_str: str) -> str:
    """Конвертирует SQL SIMILAR TO паттерн в POSIX-регулярное выражение.

    Правила замены:
      %  → .*   (любая последовательность символов)
      _  → .    (один произвольный символ)
      |  → |    (чередование, сохраняется)
      () → ()   (группировка, сохраняется)
      Результат оборачивается в ^(?:...)$.
    """
    result = []
    for ch in pattern_str:
        if ch == "%":
            result.append(".*")
        elif ch == "_":
            result.append(".")
        else:
            result.append(ch)
    return "^(?:" + "".join(result) + ")$"


def _rewrite_posix(n, ctx: TranslateContext):
    """str ~ pattern → match(str, pattern)."""
    return _make_fn(n.dialect, "match", n.left, n.right)


def _rewrite_posix_neg(n, ctx: TranslateContext):
    """str !~ pattern → NOT match(str, pattern)."""
    return _make_not(n.dialect, _make_fn(n.dialect, "match", n.left, n.right))


def _rewrite_posix_ci(n, ctx: TranslateContext):
    """str ~* pattern → match(str, concat('(?i)', pattern))."""
    return _make_fn(n.dialect, "match", n.left, _make_concat_ci(n.dialect, n.right))


def _rewrite_posix_ci_neg(n, ctx: TranslateContext):
    """str !~* pattern → NOT match(str, concat('(?i)', pattern))."""
    return _make_not(
        n.dialect,
        _make_fn(n.dialect, "match", n.left, _make_concat_ci(n.dialect, n.right)),
    )


def _rewrite_similar_to(n, ctx: TranslateContext):
    """expr SIMILAR TO pattern → match(expr, posix_pattern).

    Если pattern — строковый литерал, выполняет конвертацию паттерна.
    Если pattern — выражение (параметр, столбец), match() создаётся без конвертации;
    паттерн нужно конвертировать вручную согласно аннотации D.
    """
    if isinstance(n.pattern, Literal) and n.pattern.literal_kind == "string":
        converted = _convert_similar_pattern(str(n.pattern.value))
        new_pat = Literal()
        new_pat.node_kind = "Literal"
        new_pat.dialect = n.dialect
        new_pat.value = converted
        new_pat.literal_kind = "string"
        new_pat.raw = repr(converted)
        pattern_node = new_pat
    else:
        pattern_node = n.pattern

    match_call = _make_fn(n.dialect, "match", n.string, pattern_node)
    if n.negated:
        return _make_not(n.dialect, match_call)
    return match_call

_STRING_OPS_RULES: list[Rule] = [
    Rule(
        rule_id="pg_ch_binop_posix_match",
        title="str ~ pattern → match(str, pattern) (тип B)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="BinaryOp",
        kind=Kind.B,
        when=lambda n: isinstance(n, BinaryOp) and n.op == "~",
        rewrite=_rewrite_posix,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_binop_posix_not_match",
        title="str !~ pattern → NOT match(str, pattern) (тип B)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="BinaryOp",
        kind=Kind.B,
        when=lambda n: isinstance(n, BinaryOp) and n.op == "!~",
        rewrite=_rewrite_posix_neg,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_binop_posix_imatch",
        title="str ~* pattern → match(str, concat('(?i)', pattern)) (тип B)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="BinaryOp",
        kind=Kind.B,
        when=lambda n: isinstance(n, BinaryOp) and n.op == "~*",
        rewrite=_rewrite_posix_ci,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_binop_posix_not_imatch",
        title="str !~* pattern → NOT match(str, concat('(?i)', pattern)) (тип B)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="BinaryOp",
        kind=Kind.B,
        when=lambda n: isinstance(n, BinaryOp) and n.op == "!~*",
        rewrite=_rewrite_posix_ci_neg,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_like_base",
        title="LikeExpr (базовый проход, тип A)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="LikeExpr",
        kind=Kind.A,
        when=lambda n: True,
        rewrite=None,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_like_escape",
        title="LIKE/ILIKE ESCAPE escape_char (тип C)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="LikeExpr",
        kind=Kind.C,
        when=lambda n: isinstance(n, LikeExpr) and n.escape is not None,
        rewrite=None,
        message=(
            "Клауза ESCAPE поддерживается в CH, но escape-символ не может быть "
            "произвольной строкой: в CH по умолчанию используется '\\'. "
            "Убедитесь, что escape_char совпадает со значением по умолчанию "
            "или используйте функцию like() с явным escape."
        ),
    ),
    Rule(
        rule_id="pg_ch_similar_to_base",
        title="SimilarToExpr (базовый проход, тип A)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="SimilarToExpr",
        kind=Kind.A,
        when=lambda n: True,
        rewrite=None,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_similar_to_rewrite",
        title="expr SIMILAR TO pattern → match(expr, posix_pattern) (тип D)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="SimilarToExpr",
        kind=Kind.D,
        when=lambda n: True,
        rewrite=_rewrite_similar_to,
        message=(
            "В CH нет оператора SIMILAR TO. "
            "Преобразовано в match(expr, pattern). "
            "Паттерн конвертирован: % → .*, _ → .; результат обёрнут в ^(?:...)$. "
            "Если паттерн не является строковым литералом, конвертацию нужно "
            "выполнить вручную."
        ),
    ),
]

for _rule in _STRING_OPS_RULES:
    default_translator.register(_rule)
