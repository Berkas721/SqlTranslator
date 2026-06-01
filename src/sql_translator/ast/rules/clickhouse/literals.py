"""Правила преобразования Literal и ArrayConstructor: PostgreSQL → ClickHouse.
"""
from __future__ import annotations

from src.ast.metadata import Dialect, Kind
from src.ast.registry import Rule, TranslateContext, default_translator

_RULE_PLAIN_INT = Rule(
    rule_id="pg_ch_lit_plain_int",
    title="целочисленный литерал без преобразования (тип A)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="Literal",
    kind=Kind.A,
    when=lambda n: n.literal_kind == "int" and not (n.raw and "_" in n.raw),
    rewrite=None,
    message=None,
)

_RULE_PLAIN_FLOAT = Rule(
    rule_id="pg_ch_lit_plain_float",
    title="вещественный литерал без преобразования (тип A)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="Literal",
    kind=Kind.A,
    when=lambda n: n.literal_kind == "float" and not (n.raw and "_" in n.raw),
    rewrite=None,
    message=None,
)

_RULE_PLAIN_STRING = Rule(
    rule_id="pg_ch_lit_plain_string",
    title="строковый литерал в одинарных кавычках (тип A)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="Literal",
    kind=Kind.A,
    when=lambda n: n.literal_kind == "string" and (n.quote_style is None or n.quote_style == "single"),
    rewrite=None,
    message=None,
)

_RULE_NULL = Rule(
    rule_id="pg_ch_lit_null",
    title="NULL-литерал (тип A)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="Literal",
    kind=Kind.A,
    when=lambda n: n.literal_kind == "null",
    rewrite=None,
    message=None,
)

_RULE_PLAIN_DATE = Rule(
    rule_id="pg_ch_lit_plain_date",
    title="DATE-литерал без преобразования (тип A)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="Literal",
    kind=Kind.A,
    when=lambda n: n.literal_kind == "date",
    rewrite=None,
    message=None,
)

_RULE_PLAIN_TIMESTAMP = Rule(
    rule_id="pg_ch_lit_plain_timestamp",
    title="TIMESTAMP-литерал без преобразования (тип A)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="Literal",
    kind=Kind.A,
    when=lambda n: n.literal_kind == "timestamp",
    rewrite=None,
    message=None,
)

_RULE_PLAIN_UUID = Rule(
    rule_id="pg_ch_lit_plain_uuid",
    title="UUID-литерал без преобразования (тип A)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="Literal",
    kind=Kind.A,
    when=lambda n: n.literal_kind == "uuid",
    rewrite=None,
    message=None,
)

_RULE_PLAIN_BIT = Rule(
    rule_id="pg_ch_lit_plain_bit",
    title="битовый литерал B'...' (тип A)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="Literal",
    kind=Kind.A,
    when=lambda n: n.literal_kind == "bit",
    rewrite=None,
    message=None,
)

_RULE_PLAIN_HEX = Rule(
    rule_id="pg_ch_lit_plain_hex",
    title="шестнадцатеричный литерал X'...' (тип A)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="Literal",
    kind=Kind.A,
    when=lambda n: n.literal_kind == "hex",
    rewrite=None,
    message=None,
)


def _rewrite_strip_underscore(n, ctx: TranslateContext):
    """Убрать разделители-подчёркивания из числового литерала (42_000 → 42000)."""
    if n.raw:
        n.raw = n.raw.replace("_", "")
    return n


_RULE_NUMERIC_UNDERSCORE = Rule(
    rule_id="pg_ch_lit_numeric_underscore",
    title="числовой литерал с разделителем '_' (тип B)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="Literal",
    kind=Kind.B,
    when=lambda n: n.literal_kind in ("int", "float") and bool(n.raw) and "_" in n.raw,
    rewrite=_rewrite_strip_underscore,
    message=None,
)


def _rewrite_quote_to_single(n, ctx: TranslateContext):
    """Привести quote_style к 'single' (E-строка / dollar / U&)."""
    n.quote_style = "single"
    return n


_RULE_ESTRING = Rule(
    rule_id="pg_ch_lit_estring",
    title="E-строка E'...' → обычная строка в одинарных кавычках (тип B)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="Literal",
    kind=Kind.B,
    when=lambda n: n.literal_kind == "string" and n.quote_style == "E",
    rewrite=_rewrite_quote_to_single,
    message=None,
)

_RULE_DOLLAR = Rule(
    rule_id="pg_ch_lit_dollar",
    title="dollar-quoting $$...$$ → обычная строка в одинарных кавычках (тип B)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="Literal",
    kind=Kind.B,
    when=lambda n: n.literal_kind == "string" and n.quote_style == "dollar",
    rewrite=_rewrite_quote_to_single,
    message=None,
)

_RULE_UNICODE_ESC = Rule(
    rule_id="pg_ch_lit_unicode",
    title="Unicode-escape строка U&'...' → обычная строка в одинарных кавычках (тип B)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="Literal",
    kind=Kind.B,
    when=lambda n: n.literal_kind == "string" and n.quote_style == "U&",
    rewrite=_rewrite_quote_to_single,
    message=None,
)


def _rewrite_array_curly(n, ctx: TranslateContext):
    """'{1,2,3}'::type[] → [1,2,3] (bracket-синтаксис)."""
    n.syntax = "bracket"
    return n


_RULE_ARRAY_CURLY = Rule(
    rule_id="pg_ch_lit_array_curly",
    title="строковый литерал-массив '{...}'::type[] → [...] (тип B)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="ArrayConstructor",
    kind=Kind.B,
    when=lambda n: n.syntax == "curly_literal",
    rewrite=_rewrite_array_curly,
    message=None,
)


def _rewrite_array_kw_to_bracket(n, ctx: TranslateContext):
    """ARRAY[1,2,3] → [1,2,3] (bracket-синтаксис)."""
    n.syntax = "bracket"
    return n


_RULE_ARRAY_KW = Rule(
    rule_id="pg_ch_arr_array_kw",
    title="ARRAY[...] → [...] (тип B)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="ArrayConstructor",
    kind=Kind.B,
    when=lambda n: n.syntax == "array_kw",
    rewrite=_rewrite_array_kw_to_bracket,
    message=None,
)

_RULE_ARRAY_BRACKET = Rule(
    rule_id="pg_ch_arr_bracket",
    title="конструктор массива [...] (тип A)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="ArrayConstructor",
    kind=Kind.A,
    when=lambda n: n.syntax == "bracket",
    rewrite=None,
    message=None,
)


def _rewrite_bool_literal(n, ctx: TranslateContext):
    """Привести булев литерал к форме true/false, понятной CH."""
    n.raw = "true" if n.value else "false"
    return n


_RULE_BOOL_LITERAL = Rule(
    rule_id="pg_ch_lit_bool",
    title="булев литерал → true/false (тип C)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="Literal",
    kind=Kind.C,
    when=lambda n: n.literal_kind == "bool",
    rewrite=_rewrite_bool_literal,
    message=(
        "В PGSQL boolean — трёхзначный (TRUE/FALSE/NULL); "
        "в CH Bool соответствует UInt8 и NULL требует обёртки Nullable(Bool)."
    ),
)


_RULE_INTERVAL_LITERAL = Rule(
    rule_id="pg_ch_lit_interval",
    title="INTERVAL-литерал с составными единицами (тип D)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="Literal",
    kind=Kind.D,
    when=lambda n: n.literal_kind == "interval",
    rewrite=None,   # структурное разбиение на части выходит за рамки правила типа
    message=(
        "PGSQL допускает составные единицы в одном INTERVAL-литерале "
        "(INTERVAL '1 year 2 months'); CH принимает только одну единицу за раз "
        "и требует целого числа (INTERVAL 3 DAY). "
        "Составной интервал раскладывается на последовательные операции +/-."
    ),
)


_ALL_RULES = [
    # A — нейтральные формы (нужны, чтобы fallback Kind.F не срабатывал)
    _RULE_PLAIN_INT,
    _RULE_PLAIN_FLOAT,
    _RULE_PLAIN_STRING,
    _RULE_NULL,
    _RULE_PLAIN_DATE,
    _RULE_PLAIN_TIMESTAMP,
    _RULE_PLAIN_UUID,
    _RULE_PLAIN_BIT,
    _RULE_PLAIN_HEX,
    _RULE_ARRAY_BRACKET,
    # B
    _RULE_NUMERIC_UNDERSCORE,
    _RULE_ESTRING,
    _RULE_DOLLAR,
    _RULE_UNICODE_ESC,
    _RULE_ARRAY_CURLY,
    _RULE_ARRAY_KW,
    # C
    _RULE_BOOL_LITERAL,
    # D
    _RULE_INTERVAL_LITERAL,
]

for _rule in _ALL_RULES:
    default_translator.register(_rule)
