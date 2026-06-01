"""Правила преобразования INSERT: PostgreSQL → ClickHouse.
"""
from __future__ import annotations

from src.ast.metadata import Dialect, Kind
from src.ast.nodes import ValuesClause
from src.ast.registry import Rule, default_translator

_E_MSG = "нет аналога в ClickHouse"


_INSERT_RULES: list[Rule] = [
    Rule(
        rule_id="pg_ch_insert_base",
        title="InsertStmt (базовый проход, тип A)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="InsertStmt",
        kind=Kind.A,
        when=lambda n: True,
        rewrite=None,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_insert_values_txn",
        title="INSERT ... VALUES (...) (тип C)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="InsertStmt",
        kind=Kind.C,
        when=lambda n: isinstance(n.source, ValuesClause),
        rewrite=None,
        message=(
            "Транзакционная семантика различается: PGSQL — атомарная вставка, "
            "видна до COMMIT внутри сессии; CH — парт MergeTree, параллельные SELECT "
            "могут не видеть вставку до фиксации парта. "
            "Столбцы MATERIALIZED/ALIAS нельзя указывать в списке колонок INSERT."
        ),
    ),
    Rule(
        rule_id="pg_ch_insert_with_clause",
        title="WITH with_query INSERT INTO ... query → INSERT INTO ... (WITH внутри SELECT) (тип D)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="InsertStmt",
        kind=Kind.D,
        when=lambda n: (
            n.with_clause is not None
            and not n.with_clause.recursive
        ),
        rewrite=None,
        message=(
            "В CH WITH допустим внутри query-части после INSERT INTO ... SELECT, "
            "но не как внешняя секция самой команды INSERT."
        ),
    ),
    Rule(
        rule_id="pg_ch_insert_with_recursive",
        title="WITH RECURSIVE ... INSERT INTO ... (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="InsertStmt",
        kind=Kind.E,
        when=lambda n: (
            n.with_clause is not None
            and n.with_clause.recursive
        ),
        rewrite=None,
        message=_E_MSG,
    ),
    Rule(
        rule_id="pg_ch_insert_alias",
        title="INSERT INTO table_name AS alias (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="InsertStmt",
        kind=Kind.E,
        when=lambda n: n.alias is not None,
        rewrite=None,
        message=_E_MSG,
    ),
    Rule(
        rule_id="pg_ch_insert_overriding",
        title="OVERRIDING { SYSTEM | USER } VALUE (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="InsertStmt",
        kind=Kind.E,
        when=lambda n: n.overriding is not None,
        rewrite=None,
        message=_E_MSG,
    ),
    Rule(
        rule_id="pg_ch_insert_returning",
        title="RETURNING ... (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="InsertStmt",
        kind=Kind.E,
        when=lambda n: bool(n.returning),
        rewrite=None,
        message=_E_MSG,
    ),
]


_ON_CONFLICT_RULES: list[Rule] = [
    Rule(
        rule_id="pg_ch_on_conflict_nothing",
        title="ON CONFLICT (...) DO NOTHING (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="OnConflictClause",
        kind=Kind.E,
        when=lambda n: n.action == "nothing",
        rewrite=None,
        message=_E_MSG,
    ),
    Rule(
        rule_id="pg_ch_on_conflict_update",
        title="ON CONFLICT (...) DO UPDATE SET ... (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="OnConflictClause",
        kind=Kind.E,
        when=lambda n: n.action == "update",
        rewrite=None,
        message=(
            "Функциональный суррогат — движок ReplacingMergeTree "
            "с дедупликацией по ключу; не является синтаксически эквивалентным."
        ),
    ),
]


for _rule in _INSERT_RULES + _ON_CONFLICT_RULES:
    default_translator.register(_rule)
