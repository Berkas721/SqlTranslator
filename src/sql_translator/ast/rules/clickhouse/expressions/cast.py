"""Правила преобразования TYPE CAST: PostgreSQL → ClickHouse.
"""
from __future__ import annotations

from src.ast.metadata import Dialect, Kind
from src.ast.nodes import Cast
from src.ast.registry import Rule, TranslateContext, default_translator

# Псевдотипы PostgreSQL, не имеющие аналогов в ClickHouse
_REG_TYPES: frozenset[str] = frozenset({
    "REGCLASS", "REGPROC", "REGPROCEDURE", "REGOPER", "REGOPERATOR",
    "REGTYPE", "REGCONFIG", "REGDICTIONARY", "REGNAMESPACE", "REGROLE",
})


def _rewrite_postfix_to_cast(n, ctx: TranslateContext):
    """expr::type → CAST(expr AS type)."""
    n.style = "cast"
    return n


_CAST_RULES: list[Rule] = [
    Rule(
        rule_id="pg_ch_cast_base",
        title="Cast (базовый проход, тип A)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="Cast",
        kind=Kind.A,
        when=lambda n: True,
        rewrite=None,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_cast_postfix",
        title="expr::type (постфиксный CAST PG) → CAST(expr AS type) в CH (тип B)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="Cast",
        kind=Kind.B,
        when=lambda n: isinstance(n, Cast) and n.style == "postfix",
        rewrite=_rewrite_postfix_to_cast,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_cast_overflow",
        title="CAST — семантика переполнения и совместимость типов (тип C)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="Cast",
        kind=Kind.C,
        when=lambda n: True,
        rewrite=None,
        message=(
            "Семантика CAST различается: "
            "PostgreSQL бросает ошибку при переполнении или несовместимых типах; "
            "ClickHouse при переполнении усекает значение без ошибки. "
            "Проверьте допустимый диапазон целевого типа."
        ),
    ),
    Rule(
        rule_id="pg_ch_cast_timezone",
        title="CAST(... AS TIMESTAMP WITH TIME ZONE / TIMETZ) (тип D)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="Cast",
        kind=Kind.D,
        when=lambda n: (
            isinstance(n, Cast)
            and n.target_type is not None
            and n.target_type.time_zone is not None
        ),
        rewrite=None,
        message=(
            "CAST с временной зоной: PGSQL конвертирует в zone сервера неявно; "
            "CH DateTime64 всегда требует явной временной зоны в определении типа. "
            "Используйте toDateTime64(expr, precision, 'timezone') или toTimeZone()."
        ),
    ),
    Rule(
        rule_id="pg_ch_cast_reg_type",
        title="CAST(... AS regXXX) — псевдотип OID PG (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="Cast",
        kind=Kind.E,
        when=lambda n: (
            isinstance(n, Cast)
            and n.target_type is not None
            and n.target_type.name.upper() in _REG_TYPES
        ),
        rewrite=None,
        message=(
            "нет аналога в ClickHouse. "
            "Псевдотипы regclass/regtype/regproc и т.д. — системные типы OID PostgreSQL; "
            "CH не имеет системного каталога с аналогичной типизацией."
        ),
    ),
]

for _rule in _CAST_RULES:
    default_translator.register(_rule)
