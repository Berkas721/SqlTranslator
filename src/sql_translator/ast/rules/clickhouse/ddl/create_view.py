"""Правила преобразования CREATE [MATERIALIZED] VIEW: PostgreSQL → ClickHouse.

Узел: CreateViewStmt.
Источник: глава 2.1.2.2 «Различия postgresql и clickhouse.docx».
"""
from __future__ import annotations

from src.ast.metadata import Dialect, Kind
from src.ast.registry import Rule, default_translator

_E_MSG = "нет аналога в ClickHouse"

_CREATE_VIEW_RULES: list[Rule] = [
    Rule(
        rule_id="pg_ch_create_view_base",
        title="CreateViewStmt (базовый проход, тип A)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CreateViewStmt",
        kind=Kind.A,
        when=lambda n: True,
        rewrite=None,
        message=None,
    ),

    Rule(
        rule_id="pg_ch_create_view_materialized",
        title="CREATE MATERIALIZED VIEW (тип C)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CreateViewStmt",
        kind=Kind.C,
        when=lambda n: n.is_materialized,
        rewrite=None,
        message=(
            "В PGSQL — снимок данных, обновляемый REFRESH; в CH — триггер на INSERT: "
            "при каждой вставке в исходную таблицу результат SELECT переносится "
            "в целевую таблицу. Команды REFRESH для обычного MV нет."
        ),
    ),

    Rule(
        rule_id="pg_ch_create_view_column_names",
        title="CREATE VIEW name (col1, col2, ...) — явное объявление имён столбцов (тип D)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CreateViewStmt",
        kind=Kind.D,
        when=lambda n: bool(n.column_names),
        rewrite=None,
        message=(
            "Предварительное объявление имён колонок на уровне CREATE VIEW "
            "в CH не поддерживается; имена выводятся из AS-алиасов в SELECT."
        ),
    ),
    Rule(
        rule_id="pg_ch_create_view_security",
        title="WITH (security_barrier=..., security_invoker=...) (тип D)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CreateViewStmt",
        kind=Kind.D,
        when=lambda n: n.security_barrier or n.security_invoker,
        rewrite=None,
        message=(
            "Частично близкий механизм управления контекстом исполнения; "
            "правила применения RLS различны."
        ),
    ),
    Rule(
        rule_id="pg_ch_create_view_with_data",
        title="WITH [NO] DATA (тип D)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CreateViewStmt",
        kind=Kind.D,
        when=lambda n: n.with_data is not None,
        rewrite=None,
        message=(
            "CH с POPULATE может пропустить строки, поступающие во время заполнения; "
            "PGSQL снимок формирует атомарно."
        ),
    ),
    Rule(
        rule_id="pg_ch_create_view_refresh",
        title="REFRESH MATERIALIZED VIEW → REFRESHABLE MATERIALIZED VIEW ... REFRESH EVERY/AFTER (тип D)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CreateViewStmt",
        kind=Kind.D,
        # Применяется к материализованным представлениям без POPULATE (т.е. требующим ручного REFRESH)
        when=lambda n: n.is_materialized and n.with_data is False,
        rewrite=None,
        message=(
            "CH поддерживает только расписание; явной команды REFRESH по запросу "
            "для обычного MV нет. CONCURRENTLY аналога не имеет."
        ),
    ),

    Rule(
        rule_id="pg_ch_create_view_temporary",
        title="TEMPORARY / TEMP VIEW (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CreateViewStmt",
        kind=Kind.E,
        when=lambda n: n.temporary,
        rewrite=None,
        message=_E_MSG,
    ),
    Rule(
        rule_id="pg_ch_create_view_recursive",
        title="RECURSIVE VIEW (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CreateViewStmt",
        kind=Kind.E,
        when=lambda n: n.recursive,
        rewrite=None,
        message=_E_MSG,
    ),
    Rule(
        rule_id="pg_ch_create_view_check_option",
        title="WITH [LOCAL | CASCADED] CHECK OPTION (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CreateViewStmt",
        kind=Kind.E,
        when=lambda n: bool(n.check_option),
        rewrite=None,
        message=_E_MSG,
    ),
]

for _rule in _CREATE_VIEW_RULES:
    default_translator.register(_rule)
