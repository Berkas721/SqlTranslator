"""Правила преобразования CREATE FUNCTION: PostgreSQL → ClickHouse.

Узел: CreateFunctionStmt.
Источник: глава 2.1.2.4 «Различия postgresql и clickhouse.docx».

В CH функции — скалярные лямбда-выражения вида AS (args) -> expr;
полноценного процедурного языка нет.
"""
from __future__ import annotations

from src.ast.metadata import Dialect, Kind
from src.ast.registry import Rule, default_translator

_CREATE_FUNCTION_RULES: list[Rule] = [
    Rule(
        rule_id="pg_ch_create_function_base",
        title="CreateFunctionStmt (базовый проход, тип A)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CreateFunctionStmt",
        kind=Kind.A,
        when=lambda n: True,
        rewrite=None,
        message=None,
    ),

    Rule(
        rule_id="pg_ch_create_function_or_replace",
        title="CREATE OR REPLACE FUNCTION (тип C)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CreateFunctionStmt",
        kind=Kind.C,
        when=lambda n: n.or_replace,
        rewrite=None,
        message=(
            "В PGSQL сохраняет OID, права и зависимости; "
            "в CH замена идёт через удаление и создание, "
            "зависимости могут не сохраняться."
        ),
    ),

    Rule(
        rule_id="pg_ch_create_function_body",
        title="AS $$ body $$ LANGUAGE sql → AS (args) -> expr (тип D)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CreateFunctionStmt",
        kind=Kind.D,
        when=lambda n: bool(n.body) or bool(n.language),
        rewrite=None,
        message=(
            "В CH допустимо только одно скалярное выражение в записи лямбды; "
            "ни нескольких строк, ни промежуточных переменных, "
            "ни перегрузки, ни рекурсии."
        ),
    ),
]

for _rule in _CREATE_FUNCTION_RULES:
    default_translator.register(_rule)
