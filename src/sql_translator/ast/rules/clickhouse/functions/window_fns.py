"""Правила преобразования оконных функций и фреймов: PostgreSQL → ClickHouse.
"""
from __future__ import annotations

from src.ast.metadata import Dialect, Kind
from src.ast.nodes import FrameBound, FrameSpec, FunctionCall, Literal
from src.ast.registry import Rule, TranslateContext, default_translator

def _fn_name(n) -> str:
    if isinstance(n, FunctionCall) and n.name is not None:
        return n.name.name.lower()
    return ""


def _bound_has_interval(bound: FrameBound) -> bool:
    """Проверяет, является ли смещение кадра интервальным литералом."""
    if bound is None or bound.offset is None:
        return False
    off = bound.offset
    return (
        isinstance(off, Literal) and off.literal_kind == "interval"
        or (
            hasattr(off, "node_kind")
            and off.node_kind in ("Cast", "IntervalLiteral")
        )
    )

_WINDOW_FN_RULES: list[Rule] = [
    Rule(
        rule_id="pg_ch_frame_base",
        title="FrameSpec (базовый проход, тип A)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FrameSpec",
        kind=Kind.A,
        when=lambda n: True,
        rewrite=None,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_frame_groups",
        title="GROUPS BETWEEN n PRECEDING AND n FOLLOWING (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FrameSpec",
        kind=Kind.E,
        when=lambda n: isinstance(n, FrameSpec) and n.unit == "GROUPS",
        rewrite=None,
        message=(
            "нет аналога в ClickHouse. "
            "Оконный кадр GROUPS (по группам значений ORDER BY) не поддерживается; "
            "доступны только ROWS и RANGE."
        ),
    ),
    Rule(
        rule_id="pg_ch_frame_exclude",
        title="EXCLUDE CURRENT ROW / GROUP / TIES / NO OTHERS (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FrameSpec",
        kind=Kind.E,
        when=lambda n: isinstance(n, FrameSpec) and n.exclude is not None,
        rewrite=None,
        message=(
            "нет аналога в ClickHouse. "
            "Модификатор EXCLUDE (CURRENT ROW / GROUP / TIES / NO OTHERS) "
            "в оконных кадрах CH не поддерживается."
        ),
    ),
    Rule(
        rule_id="pg_ch_frame_range_interval",
        title="RANGE BETWEEN INTERVAL … PRECEDING AND … FOLLOWING (тип D)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FrameSpec",
        kind=Kind.D,
        when=lambda n: (
            isinstance(n, FrameSpec)
            and n.unit == "RANGE"
            and (
                _bound_has_interval(n.start)
                or _bound_has_interval(n.end)
            )
        ),
        rewrite=None,
        message=(
            "RANGE с интервальным смещением поддерживается в CH с ограничениями: "
            "составные интервалы ('1 year 2 months') не поддерживаются — "
            "используйте только одну единицу. "
            "Кавычки вокруг числа не нужны: INTERVAL 1 DAY (без кавычек)."
        ),
    ),
    Rule(
        rule_id="pg_ch_fn_ntile",
        title="ntile(n) OVER (...) — распределение «лишних» строк (тип C)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.C,
        when=lambda n: _fn_name(n) == "ntile",
        rewrite=None,
        message=(
            "Распределение «лишних» строк по корзинам различается: "
            "PGSQL добавляет лишние строки в первые корзины; "
            "CH до версии 23.x добавляет их в последние. "
            "Начиная с CH 23.x поведение совместимо с PGSQL."
        ),
    ),
    Rule(
        rule_id="pg_ch_fn_window_filter",
        title="fn() FILTER (WHERE cond) OVER (...) (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.E,
        when=lambda n: (
            isinstance(n, FunctionCall)
            and n.filter_where is not None
            and n.over is not None
        ),
        rewrite=None,
        message=(
            "нет аналога в ClickHouse. "
            "Клауза FILTER (WHERE ...) поверх оконной функции (OVER) не поддерживается. "
            "Рассмотрите предварительную фильтрацию данных через подзапрос."
        ),
    ),
]

for _rule in _WINDOW_FN_RULES:
    default_translator.register(_rule)
