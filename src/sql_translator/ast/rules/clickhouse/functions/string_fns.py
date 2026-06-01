"""Правила преобразования строковых функций: PostgreSQL → ClickHouse.
"""
from __future__ import annotations

from src.ast.metadata import Dialect, Kind
from src.ast.nodes import FunctionCall, Identifier
from src.ast.registry import Rule, TranslateContext, default_translator


def _fn_name(n) -> str:
    if isinstance(n, FunctionCall) and n.name is not None:
        return n.name.name.lower()
    return ""


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


def _rewrite_rename(new_name: str):
    def _rewrite(n, ctx: TranslateContext):
        n.name.name = new_name
        return n
    _rewrite.__name__ = f"_rewrite_to_{new_name}"
    return _rewrite


_STRING_FN_RULES: list[Rule] = [
    Rule(
        rule_id="pg_ch_fn_char_length",
        title="char_length(s) → lengthUTF8(s) (тип B)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.B,
        when=lambda n: _fn_name(n) in ("char_length", "character_length"),
        rewrite=_rewrite_rename("lengthUTF8"),
        message=None,
    ),
    Rule(
        rule_id="pg_ch_fn_length_bytes",
        title="length(s) — байты vs символы (тип C)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.C,
        when=lambda n: _fn_name(n) == "length",
        rewrite=None,
        message=(
            "length(s) в PGSQL возвращает число символов (code points); "
            "в CH — число байт в UTF-8 строке. "
            "Для числа символов используйте lengthUTF8(s)."
        ),
    ),
    Rule(
        rule_id="pg_ch_fn_upper_locale",
        title="upper(s) — локаль vs ASCII (тип C)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.C,
        when=lambda n: _fn_name(n) == "upper",
        rewrite=None,
        message=(
            "upper(s) в PGSQL учитывает локаль базы данных; "
            "в CH применяется только к ASCII-символам (A–Z). "
            "Для Unicode используйте upperUTF8(s)."
        ),
    ),
    Rule(
        rule_id="pg_ch_fn_lower_locale",
        title="lower(s) — локаль vs ASCII (тип C)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.C,
        when=lambda n: _fn_name(n) == "lower",
        rewrite=None,
        message=(
            "lower(s) в PGSQL учитывает локаль базы данных; "
            "в CH применяется только к ASCII-символам (a–z). "
            "Для Unicode используйте lowerUTF8(s)."
        ),
    ),
    Rule(
        rule_id="pg_ch_fn_trim_forms",
        title="TRIM/ltrim/rtrim/btrim — ограниченный набор форм (тип C)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.C,
        when=lambda n: _fn_name(n) in ("ltrim", "rtrim", "btrim", "trim"),
        rewrite=None,
        message=(
            "Семантика совпадает в базовом случае (пробелы), но набор форм ограничен: "
            "PGSQL поддерживает TRIM(LEADING|TRAILING|BOTH chars FROM s); "
            "CH — trimLeft(s, chars) / trimRight(s, chars) / trimBoth(s, chars). "
            "Форма с ключевыми словами в CH не поддерживается."
        ),
    ),
    Rule(
        rule_id="pg_ch_fn_quote_ident",
        title="quote_ident/quote_literal/quote_nullable (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.E,
        when=lambda n: _fn_name(n) in (
            "quote_ident", "quote_literal", "quote_nullable"
        ),
        rewrite=None,
        message=(
            "нет аналога в ClickHouse. "
            "Функции экранирования идентификаторов и литералов специфичны для PGSQL; "
            "в CH генерация динамического SQL не предусмотрена."
        ),
    ),
    Rule(
        rule_id="pg_ch_fn_tsvector",
        title="to_tsvector / to_tsquery / ts_rank / ts_headline (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.E,
        when=lambda n: _fn_name(n) in (
            "to_tsvector", "to_tsquery", "plainto_tsquery", "phraseto_tsquery",
            "websearch_to_tsquery", "ts_rank", "ts_rank_cd", "ts_headline",
            "ts_rewrite", "tsvector_to_array", "array_to_tsvector",
        ),
        rewrite=None,
        message=(
            "нет аналога в ClickHouse. "
            "Полнотекстовый поиск в CH реализован через движок токенов "
            "(full-text index, hasToken()), но синтаксически несовместим с GIN/tsvector PGSQL."
        ),
    ),
    Rule(
        rule_id="pg_ch_fn_convert_encoding",
        title="convert / convert_from / convert_to (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.E,
        when=lambda n: _fn_name(n) in (
            "convert", "convert_from", "convert_to"
        ),
        rewrite=None,
        message=(
            "нет аналога в ClickHouse. "
            "В CH кодировка строк фиксирована UTF-8; "
            "явная перекодировка на уровне SQL не поддерживается."
        ),
    ),
]

for _rule in _STRING_FN_RULES:
    default_translator.register(_rule)
