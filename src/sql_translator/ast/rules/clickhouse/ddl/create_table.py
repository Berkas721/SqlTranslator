"""Правила преобразования CREATE TABLE-конструкций: PostgreSQL → ClickHouse.

Узлы: ColumnConstraint, TableConstraint, ColumnDef, LikeClause, CreateTableStmt.
Источник: глава 2.1.2.1 «Различия postgresql и clickhouse.docx».

Порядок регистрации:
  1. Catch-all Kind.A-правило (предотвращает F-fallback на «чистых» узлах).
  2. Специфичные C/D/E/B правила (по полям / kind).
"""
from __future__ import annotations

from src.ast.metadata import Dialect, Kind
from src.ast.nodes import FunctionCall, Identifier
from src.ast.registry import Rule, TranslateContext, default_translator

_E_MSG = "нет аналога в ClickHouse"

# Известные kind-значения, обрабатываемые специальными правилами / эмиттером.
_KNOWN_COL_CONSTRAINT_KINDS = frozenset({
    "not_null", "null", "default", "check", "primary_key", "unique",
    "references", "generated_identity", "generated_stored", "generated_virtual",
})
_KNOWN_TBL_CONSTRAINT_KINDS = frozenset({
    "primary_key", "unique", "check", "foreign_key",
})


_COL_CONSTRAINT_RULES: list[Rule] = [
    Rule(
        rule_id="pg_ch_col_constraint_base",
        title="ColumnConstraint (базовый проход, тип A)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="ColumnConstraint",
        kind=Kind.A,
        when=lambda n: True,
        rewrite=None,
        message=None,
    ),

    Rule(
        rule_id="pg_ch_col_primary_key",
        title="PRIMARY KEY на столбце (тип C)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="ColumnConstraint",
        kind=Kind.C,
        when=lambda n: n.kind == "primary_key",
        rewrite=None,
        message=(
            "В PGSQL — ограничение уникальности с автоматическим индексом; "
            "в CH — разрежённый первичный индекс, задающий порядок данных в партах, "
            "уникальность не проверяется."
        ),
    ),
    Rule(
        rule_id="pg_ch_col_null",
        title="NULL / NOT NULL на столбце (тип C)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="ColumnConstraint",
        kind=Kind.C,
        when=lambda n: n.kind in ("null", "not_null"),
        rewrite=None,
        message=(
            "В CH NULL-значение требует обёртки типа в Nullable(T); "
            "без Nullable декларация NULL не обеспечивает хранения NULL-маркеров."
        ),
    ),
    Rule(
        rule_id="pg_ch_col_check",
        title="CHECK на столбце (тип C)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="ColumnConstraint",
        kind=Kind.C,
        when=lambda n: n.kind == "check",
        rewrite=None,
        message=(
            "В CH CHECK проверяется только на INSERT; "
            "UPDATE и ATTACH PARTITION проверку не вызывают."
        ),
    ),

    Rule(
        rule_id="pg_ch_col_generated_identity",
        title="GENERATED ... AS IDENTITY → DEFAULT generateUUIDv4() / rowNumberInBlock() (тип D)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="ColumnConstraint",
        kind=Kind.D,
        when=lambda n: n.kind == "generated_identity",
        rewrite=None,
        message=(
            "CH не гарантирует ни монотонности, ни уникальности; "
            "значения не синхронизируются между репликами."
        ),
    ),
    Rule(
        rule_id="pg_ch_col_generated_stored",
        title="GENERATED ALWAYS AS (...) STORED → MATERIALIZED expr (тип D)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="ColumnConstraint",
        kind=Kind.D,
        when=lambda n: n.kind == "generated_stored",
        rewrite=None,
        message=(
            "В CH MATERIALIZED-столбец не допускается в списке колонок INSERT; "
            "вычисляется автоматически."
        ),
    ),
    Rule(
        rule_id="pg_ch_col_generated_virtual",
        title="GENERATED ALWAYS AS (...) VIRTUAL → ALIAS expr (тип D)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="ColumnConstraint",
        kind=Kind.D,
        when=lambda n: n.kind == "generated_virtual",
        rewrite=None,
        message=(
            "ALIAS не может участвовать в ключах таблицы; "
            "VIRTUAL в PGSQL вычисляется при каждом чтении."
        ),
    ),

    Rule(
        rule_id="pg_ch_col_unique",
        title="UNIQUE на столбце (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="ColumnConstraint",
        kind=Kind.E,
        when=lambda n: n.kind == "unique",
        rewrite=None,
        message=_E_MSG,
    ),
    Rule(
        rule_id="pg_ch_col_references",
        title="REFERENCES / FOREIGN KEY на столбце (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="ColumnConstraint",
        kind=Kind.E,
        when=lambda n: n.kind == "references",
        rewrite=None,
        message=_E_MSG,
    ),
    Rule(
        rule_id="pg_ch_col_constraint_unknown",
        title="ColumnConstraint неизвестного kind (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="ColumnConstraint",
        kind=Kind.E,
        when=lambda n: n.kind not in _KNOWN_COL_CONSTRAINT_KINDS,
        rewrite=None,
        message=_E_MSG,
    ),
]


_TABLE_CONSTRAINT_RULES: list[Rule] = [
    Rule(
        rule_id="pg_ch_tbl_constraint_base",
        title="TableConstraint (базовый проход, тип A)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="TableConstraint",
        kind=Kind.A,
        when=lambda n: True,
        rewrite=None,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_tbl_primary_key",
        title="PRIMARY KEY на таблице (тип C)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="TableConstraint",
        kind=Kind.C,
        when=lambda n: n.kind == "primary_key",
        rewrite=None,
        message=(
            "В PGSQL — ограничение уникальности с автоматическим индексом; "
            "в CH — разрежённый первичный индекс, задающий порядок данных в партах, "
            "уникальность не проверяется."
        ),
    ),
    Rule(
        rule_id="pg_ch_tbl_check",
        title="CHECK на таблице (тип C)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="TableConstraint",
        kind=Kind.C,
        when=lambda n: n.kind == "check",
        rewrite=None,
        message=(
            "В CH CHECK проверяется только на INSERT; "
            "UPDATE и ATTACH PARTITION проверку не вызывают."
        ),
    ),
    Rule(
        rule_id="pg_ch_tbl_unique",
        title="UNIQUE-ограничение на таблице (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="TableConstraint",
        kind=Kind.E,
        when=lambda n: n.kind == "unique",
        rewrite=None,
        message=_E_MSG,
    ),
    Rule(
        rule_id="pg_ch_tbl_foreign_key",
        title="FOREIGN KEY на таблице (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="TableConstraint",
        kind=Kind.E,
        when=lambda n: n.kind == "foreign_key",
        rewrite=None,
        message=_E_MSG,
    ),
    Rule(
        rule_id="pg_ch_tbl_constraint_unknown",
        title="TableConstraint неизвестного kind (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="TableConstraint",
        kind=Kind.E,
        when=lambda n: n.kind not in _KNOWN_TBL_CONSTRAINT_KINDS,
        rewrite=None,
        message=_E_MSG,
    ),
]


# Маппинг PG-метода сжатия → CH-кодек (тип B)
_COMPRESSION_TO_CODEC: dict[str, str] = {
    "lz4":  "LZ4",
    "pglz": "LZ4HC",
}


def _rewrite_compression(n, ctx: TranslateContext):
    """Перенести PG compression в CH codec-список и очистить поле compression."""
    pg_method = (n.compression or "").lower()
    codec_name = _COMPRESSION_TO_CODEC.get(pg_method, "LZ4")
    # Создать FunctionCall-узел для кодека (CODEC(LZ4) / CODEC(LZ4HC))
    fc = FunctionCall(
        name=Identifier(name=codec_name, quoted=False),
    )
    fc.node_kind = "FunctionCall"
    fc.name.node_kind = "Identifier"
    fc.dialect = Dialect.CLICKHOUSE
    fc.name.dialect = Dialect.CLICKHOUSE
    n.codec = [fc]
    n.compression = None
    return n


_COLUMN_DEF_RULES: list[Rule] = [
    Rule(
        rule_id="pg_ch_col_def_base",
        title="ColumnDef (базовый проход, тип A)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="ColumnDef",
        kind=Kind.A,
        when=lambda n: True,
        rewrite=None,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_col_compression",
        title="COMPRESSION method → CODEC(...) (тип B)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="ColumnDef",
        kind=Kind.B,
        when=lambda n: bool(n.compression),
        rewrite=_rewrite_compression,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_col_collation",
        title="COLLATE collation на столбце (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="ColumnDef",
        kind=Kind.E,
        when=lambda n: bool(n.collation),
        rewrite=None,
        message=_E_MSG,
    ),
    Rule(
        rule_id="pg_ch_col_storage",
        title="STORAGE {PLAIN|EXTERNAL|EXTENDED|MAIN} (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="ColumnDef",
        kind=Kind.E,
        when=lambda n: bool(n.storage),
        rewrite=None,
        message=_E_MSG,
    ),
]


def _rewrite_like_clause(n, ctx: TranslateContext):
    """Убрать INCLUDING/EXCLUDING опции — в CH они не поддерживаются."""
    n.including = []
    n.excluding = []
    return n


_LIKE_CLAUSE_RULES: list[Rule] = [
    Rule(
        rule_id="pg_ch_like_clause",
        title="LIKE source_table [INCLUDING/EXCLUDING ...] → AS source_table (тип B)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="LikeClause",
        kind=Kind.B,
        when=lambda n: True,
        rewrite=_rewrite_like_clause,
        message=None,
    ),
]


_CREATE_TABLE_RULES: list[Rule] = [
    Rule(
        rule_id="pg_ch_create_table_base",
        title="CreateTableStmt (базовый проход, тип A)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CreateTableStmt",
        kind=Kind.A,
        when=lambda n: True,
        rewrite=None,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_create_table_partition_by",
        title="PARTITION BY { RANGE | LIST | HASH } → PARTITION BY expr (тип D)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CreateTableStmt",
        kind=Kind.D,
        # Срабатывает если задан partition_by (может быть установлен при расширении парсера)
        when=lambda n: n.partition_by is not None,
        rewrite=None,
        message=(
            "В CH метод не указывается, задаётся только выражение. "
            "Партиции создаются автоматически, "
            "отдельного CREATE TABLE ... PARTITION OF нет."
        ),
    ),
    Rule(
        rule_id="pg_ch_create_table_unlogged",
        title="UNLOGGED таблица (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CreateTableStmt",
        kind=Kind.E,
        when=lambda n: n.unlogged,
        rewrite=None,
        message=_E_MSG,
    ),
    Rule(
        rule_id="pg_ch_create_table_inherits",
        title="INHERITS (parent_table [...]) (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CreateTableStmt",
        kind=Kind.E,
        when=lambda n: bool(n.inherits),
        rewrite=None,
        message=_E_MSG,
    ),
    Rule(
        rule_id="pg_ch_create_table_tablespace",
        title="TABLESPACE tablespace_name (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CreateTableStmt",
        kind=Kind.E,
        when=lambda n: bool(n.tablespace),
        rewrite=None,
        message=_E_MSG,
    ),
    Rule(
        rule_id="pg_ch_create_table_on_commit",
        title="ON COMMIT {PRESERVE ROWS|DELETE ROWS|DROP} (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CreateTableStmt",
        kind=Kind.E,
        when=lambda n: bool(n.on_commit),
        rewrite=None,
        message=_E_MSG,
    ),
    Rule(
        rule_id="pg_ch_create_table_using",
        title="USING method (access method) (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CreateTableStmt",
        kind=Kind.E,
        when=lambda n: bool(n.using_method),
        rewrite=None,
        message=_E_MSG,
    ),
]


for _rule in (
    _COL_CONSTRAINT_RULES
    + _TABLE_CONSTRAINT_RULES
    + _COLUMN_DEF_RULES
    + _LIKE_CLAUSE_RULES
    + _CREATE_TABLE_RULES
):
    default_translator.register(_rule)
