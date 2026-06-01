"""Правила преобразования CREATE INDEX: PostgreSQL → ClickHouse.

Узел: CreateIndexStmt.
Источник: глава 2.1.2.3 «Различия postgresql и clickhouse.docx».

В CH нет самостоятельных объектов-индексов: эквивалент — data-skipping индексы,
объявляемые внутри ALTER TABLE table ADD INDEX name expr TYPE type GRANULARITY n.
"""
from __future__ import annotations

from src.ast.metadata import Dialect, Kind
from src.ast.registry import Rule, default_translator

_E_MSG = "нет аналога в ClickHouse"

_CREATE_INDEX_RULES: list[Rule] = [
    Rule(
        rule_id="pg_ch_create_index_base",
        title="CreateIndexStmt (базовый проход, тип A)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CreateIndexStmt",
        kind=Kind.A,
        when=lambda n: True,
        rewrite=None,
        message=None,
    ),

    Rule(
        rule_id="pg_ch_create_index_general",
        title="CREATE INDEX → ALTER TABLE ... ADD INDEX ... TYPE type (тип D)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CreateIndexStmt",
        kind=Kind.D,
        when=lambda n: True,
        rewrite=None,
        message=(
            "CH: индекс не самостоятельный объект, тип data-skipping-индекса обязателен. "
            "Ускоряет пропуск гранул, а не доступ к строке."
        ),
    ),
    Rule(
        rule_id="pg_ch_create_index_using",
        title="USING method (btree|hash|gist|...) → TYPE {minmax|set|ngrambf_v1|...} (тип D)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CreateIndexStmt",
        kind=Kind.D,
        when=lambda n: bool(n.using_method),
        rewrite=None,
        message=(
            "Методы PGSQL и типы CH не пересекаются по реализации и области применения."
        ),
    ),

    Rule(
        rule_id="pg_ch_create_index_unique",
        title="UNIQUE INDEX (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CreateIndexStmt",
        kind=Kind.E,
        when=lambda n: n.unique,
        rewrite=None,
        message=_E_MSG,
    ),
    Rule(
        rule_id="pg_ch_create_index_concurrently",
        title="CONCURRENTLY (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CreateIndexStmt",
        kind=Kind.E,
        when=lambda n: n.concurrently,
        rewrite=None,
        message=_E_MSG,
    ),
    Rule(
        rule_id="pg_ch_create_index_where",
        title="WHERE predicate (partial index) (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CreateIndexStmt",
        kind=Kind.E,
        when=lambda n: n.where is not None,
        rewrite=None,
        message=_E_MSG,
    ),
    Rule(
        rule_id="pg_ch_create_index_include",
        title="INCLUDE (col [...]) (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CreateIndexStmt",
        kind=Kind.E,
        when=lambda n: bool(n.include),
        rewrite=None,
        message=_E_MSG,
    ),
    Rule(
        rule_id="pg_ch_create_index_nulls_distinct",
        title="NULLS [NOT] DISTINCT (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CreateIndexStmt",
        kind=Kind.E,
        when=lambda n: n.nulls_distinct is not None,
        rewrite=None,
        message=_E_MSG,
    ),
]

for _rule in _CREATE_INDEX_RULES:
    default_translator.register(_rule)
