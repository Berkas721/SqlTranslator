"""Правила преобразования TCL-команд: PostgreSQL → ClickHouse.
"""
from __future__ import annotations

from src.ast.metadata import Dialect, Kind
from src.ast.nodes import (
    BeginStmt, CommitStmt, LockTableStmt,
    PrepareTransactionStmt, RollbackStmt, SavepointStmt,
    SetConstraintsStmt, SetTransactionStmt,
)
from src.ast.registry import Rule, TranslateContext, default_translator


def _rewrite_begin_style(n, ctx: TranslateContext):
    """START TRANSACTION → стиль 'begin' (эмиттер выводит BEGIN TRANSACTION)."""
    n.style = "begin"
    return n


def _rewrite_commit_style(n, ctx: TranslateContext):
    """END → стиль 'commit'."""
    n.style = "commit"
    return n


def _rewrite_rollback_style(n, ctx: TranslateContext):
    """ABORT → стиль 'rollback'."""
    n.style = "rollback"
    return n


_TCL_RULES: list[Rule] = [
    Rule(
        rule_id="pg_ch_begin_base",
        title="BeginStmt (базовый проход, тип A)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="BeginStmt",
        kind=Kind.A,
        when=lambda n: True,
        rewrite=None,
        message=None,
    ),

    Rule(
        rule_id="pg_ch_begin_start_transaction",
        title="START TRANSACTION → BEGIN TRANSACTION в CH (тип B)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="BeginStmt",
        kind=Kind.B,
        when=lambda n: isinstance(n, BeginStmt) and n.style == "start_transaction",
        rewrite=_rewrite_begin_style,
        message=None,
    ),

    Rule(
        rule_id="pg_ch_begin_semantics",
        title="BEGIN / START TRANSACTION — ограниченная семантика транзакций в CH (тип C)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="BeginStmt",
        kind=Kind.C,
        when=lambda n: True,
        rewrite=None,
        message=(
            "Транзакции в CH доступны только в экспериментальном режиме и узко ограничены: "
            "поддерживаются только INSERT и SELECT в пределах одного шарда одной таблицы. "
            "DDL внутри транзакции в общем случае не поддерживается; "
            "Replicated-таблицы имеют дополнительные ограничения."
        ),
    ),


    Rule(
        rule_id="pg_ch_commit_base",
        title="CommitStmt (базовый проход, тип A)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CommitStmt",
        kind=Kind.A,
        when=lambda n: True,
        rewrite=None,
        message=None,
    ),

    Rule(
        rule_id="pg_ch_commit_end_alias",
        title="END → COMMIT в CH (тип B)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CommitStmt",
        kind=Kind.B,
        when=lambda n: isinstance(n, CommitStmt) and n.style == "end",
        rewrite=_rewrite_commit_style,
        message=None,
    ),

    Rule(
        rule_id="pg_ch_commit_semantics",
        title="COMMIT — ограниченная семантика в CH (тип C)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CommitStmt",
        kind=Kind.C,
        when=lambda n: True,
        rewrite=None,
        message=(
            "В CH COMMIT работает только в экспериментальном режиме транзакций; "
            "фиксируются только неслитые парты MergeTree. "
            "После merge или репликации ROLLBACK будет невозможен и вернёт ошибку."
        ),
    ),


    Rule(
        rule_id="pg_ch_rollback_base",
        title="RollbackStmt (базовый проход, тип A)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="RollbackStmt",
        kind=Kind.A,
        when=lambda n: True,
        rewrite=None,
        message=None,
    ),


    Rule(
        rule_id="pg_ch_rollback_abort_alias",
        title="ABORT → ROLLBACK в CH (тип B)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="RollbackStmt",
        kind=Kind.B,
        when=lambda n: isinstance(n, RollbackStmt) and n.style == "abort",
        rewrite=_rewrite_rollback_style,
        message=None,
    ),


    Rule(
        rule_id="pg_ch_rollback_semantics",
        title="ROLLBACK — ограниченная семантика в CH (тип C)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="RollbackStmt",
        kind=Kind.C,
        when=lambda n: True,
        rewrite=None,
        message=(
            "В CH ROLLBACK отменяет только неслитые парты MergeTree; "
            "после merge или репликации откат невозможен — выдаётся ошибка. "
            "Семантика ROLLBACK в PGSQL полная (отмена любых изменений)."
        ),
    ),


    Rule(
        rule_id="pg_ch_savepoint_base",
        title="SavepointStmt (базовый проход, тип A)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="SavepointStmt",
        kind=Kind.A,
        when=lambda n: True,
        rewrite=None,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_savepoint_e",
        title="SAVEPOINT / RELEASE SAVEPOINT / ROLLBACK TO SAVEPOINT (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="SavepointStmt",
        kind=Kind.E,
        when=lambda n: True,
        rewrite=None,
        message=(
            "нет аналога в ClickHouse. "
            "CH не поддерживает подтранзакции (savepoints); "
            "вложенная изоляция изменений отсутствует."
        ),
    ),


    Rule(
        rule_id="pg_ch_set_transaction_base",
        title="SetTransactionStmt (базовый проход, тип A)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="SetTransactionStmt",
        kind=Kind.A,
        when=lambda n: True,
        rewrite=None,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_set_transaction_isolation",
        title="SET TRANSACTION ISOLATION LEVEL (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="SetTransactionStmt",
        kind=Kind.E,
        when=lambda n: isinstance(n, SetTransactionStmt) and n.isolation_level is not None,
        rewrite=None,
        message=(
            "нет аналога в ClickHouse. "
            "CH не поддерживает настройку уровня изоляции транзакции через SQL; "
            "уровень снимка близок к REPEATABLE READ и не настраивается."
        ),
    ),
    Rule(
        rule_id="pg_ch_set_transaction_readonly",
        title="SET TRANSACTION READ ONLY / READ WRITE (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="SetTransactionStmt",
        kind=Kind.E,
        when=lambda n: isinstance(n, SetTransactionStmt) and n.read_only is not None,
        rewrite=None,
        message=(
            "нет аналога в ClickHouse. "
            "READ ONLY на уровне транзакции не поддерживается; "
            "ограничение записи обеспечивается GRANT SELECT без GRANT INSERT."
        ),
    ),
    Rule(
        rule_id="pg_ch_set_transaction_deferrable",
        title="SET TRANSACTION DEFERRABLE / NOT DEFERRABLE (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="SetTransactionStmt",
        kind=Kind.E,
        when=lambda n: isinstance(n, SetTransactionStmt) and n.deferrable is not None,
        rewrite=None,
        message=(
            "нет аналога в ClickHouse. "
            "DEFERRABLE откладывает проверку SERIALIZABLE-конфликтов до COMMIT; "
            "CH не поддерживает данный режим."
        ),
    ),
    Rule(
        rule_id="pg_ch_set_transaction_session",
        title="SET SESSION CHARACTERISTICS AS TRANSACTION / SET LOCAL (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="SetTransactionStmt",
        kind=Kind.E,
        when=lambda n: isinstance(n, SetTransactionStmt) and n.scope in ("session", "local"),
        rewrite=None,
        message=(
            "нет аналога в ClickHouse. "
            "Настройка характеристик транзакции на уровне сессии (SET SESSION / SET LOCAL) "
            "не поддерживается."
        ),
    ),


    Rule(
        rule_id="pg_ch_set_constraints_e",
        title="SET CONSTRAINTS {ALL|name} {DEFERRED|IMMEDIATE} (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="SetConstraintsStmt",
        kind=Kind.E,
        when=lambda n: True,
        rewrite=None,
        message=(
            "нет аналога в ClickHouse. "
            "CH не поддерживает отложенные ограничения целостности (DEFERRED constraints)."
        ),
    ),


    Rule(
        rule_id="pg_ch_lock_table_e",
        title="LOCK TABLE ... IN ... MODE (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="LockTableStmt",
        kind=Kind.E,
        when=lambda n: True,
        rewrite=None,
        message=(
            "нет аналога в ClickHouse. "
            "Явные блокировки таблицы (LOCK TABLE) отсутствуют; "
            "административный суррогат — SYSTEM STOP MERGES / SYSTEM STOP FETCHES, "
            "но это не эквивалентные блокировки."
        ),
    ),


    Rule(
        rule_id="pg_ch_prepare_transaction_e",
        title="PREPARE TRANSACTION / COMMIT PREPARED / ROLLBACK PREPARED (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="PrepareTransactionStmt",
        kind=Kind.E,
        when=lambda n: True,
        rewrite=None,
        message=(
            "нет аналога в ClickHouse. "
            "Двухфазная фиксация (2PC: PREPARE TRANSACTION / COMMIT PREPARED / "
            "ROLLBACK PREPARED) не поддерживается."
        ),
    ),
]

for _rule in _TCL_RULES:
    default_translator.register(_rule)
