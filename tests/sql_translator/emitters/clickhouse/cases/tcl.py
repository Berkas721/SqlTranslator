"""Кейсы для TCL-операторов в эмиттере."""
from __future__ import annotations

import pytest

from sql_translator.ast.nodes import (
    BeginStmt,
    CommitStmt,
    LockTableStmt,
    PrepareTransactionStmt,
    RollbackStmt,
    SavepointStmt,
    SetConstraintsStmt,
    SetTransactionStmt,
)


CASES: list = [
    # ── BeginStmt / CommitStmt / RollbackStmt ────────────────────────────────
    pytest.param(
        lambda m: m(BeginStmt, style="begin"),
        "BEGIN TRANSACTION",
        id="begin",
    ),
    pytest.param(
        lambda m: m(CommitStmt, style="commit"),
        "COMMIT",
        id="commit",
    ),
    pytest.param(
        lambda m: m(RollbackStmt, style="rollback"),
        "ROLLBACK",
        id="rollback",
    ),

    # ── SavepointStmt ────────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(SavepointStmt, action="savepoint", name="sp1"),
        "SAVEPOINT sp1",
        id="savepoint-savepoint",
    ),
    pytest.param(
        lambda m: m(SavepointStmt, action="release", name="sp1"),
        "RELEASE SAVEPOINT sp1",
        id="savepoint-release",
    ),
    pytest.param(
        lambda m: m(SavepointStmt, action="rollback_to", name="sp1"),
        "ROLLBACK TO SAVEPOINT sp1",
        id="savepoint-rollback-to",
    ),

    # ── SetTransactionStmt ───────────────────────────────────────────────────
    pytest.param(
        lambda m: m(SetTransactionStmt, scope="transaction"),
        "SET TRANSACTION",
        id="set-transaction-bare",
    ),
    pytest.param(
        lambda m: m(SetTransactionStmt, scope="session"),
        "SET SESSION CHARACTERISTICS AS TRANSACTION",
        id="set-transaction-session",
    ),
    pytest.param(
        lambda m: m(SetTransactionStmt, scope="local"),
        "SET LOCAL TRANSACTION",
        id="set-transaction-local",
    ),
    pytest.param(
        lambda m: m(SetTransactionStmt, scope="transaction",
                    isolation_level="SERIALIZABLE"),
        "SET TRANSACTION ISOLATION LEVEL SERIALIZABLE",
        id="set-transaction-isolation",
    ),
    pytest.param(
        lambda m: m(SetTransactionStmt, scope="transaction", read_only=True),
        "SET TRANSACTION READ ONLY",
        id="set-transaction-read-only",
    ),
    pytest.param(
        lambda m: m(SetTransactionStmt, scope="transaction", read_only=False),
        "SET TRANSACTION READ WRITE",
        id="set-transaction-read-write",
    ),
    pytest.param(
        lambda m: m(SetTransactionStmt, scope="transaction", deferrable=True),
        "SET TRANSACTION DEFERRABLE",
        id="set-transaction-deferrable",
    ),
    pytest.param(
        lambda m: m(SetTransactionStmt, scope="transaction", deferrable=False),
        "SET TRANSACTION NOT DEFERRABLE",
        id="set-transaction-not-deferrable",
    ),
    pytest.param(
        lambda m: m(SetTransactionStmt, scope="transaction",
                    isolation_level="READ COMMITTED", read_only=True),
        "SET TRANSACTION ISOLATION LEVEL READ COMMITTED, READ ONLY",
        id="set-transaction-combined",
    ),

    # ── SetConstraintsStmt ───────────────────────────────────────────────────
    pytest.param(
        lambda m: m(SetConstraintsStmt, mode="DEFERRED"),
        "SET CONSTRAINTS ALL DEFERRED",
        id="set-constraints-deferred",
    ),
    pytest.param(
        lambda m: m(SetConstraintsStmt, mode="IMMEDIATE"),
        "SET CONSTRAINTS ALL IMMEDIATE",
        id="set-constraints-immediate",
    ),

    # ── LockTableStmt ────────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(LockTableStmt, mode=None),
        "LOCK TABLE",
        id="lock-table-bare",
    ),
    pytest.param(
        lambda m: m(LockTableStmt, mode="ACCESS EXCLUSIVE"),
        "LOCK TABLE IN ACCESS EXCLUSIVE MODE",
        id="lock-table-mode",
    ),

    # ── PrepareTransactionStmt ───────────────────────────────────────────────
    pytest.param(
        lambda m: m(PrepareTransactionStmt, prepared_id="tx_42", action="prepare"),
        "PREPARE TRANSACTION 'tx_42'",
        id="prepare-transaction-prepare",
    ),
    pytest.param(
        lambda m: m(PrepareTransactionStmt, prepared_id="tx_42", action="commit"),
        "COMMIT PREPARED 'tx_42'",
        id="prepare-transaction-commit",
    ),
    pytest.param(
        lambda m: m(PrepareTransactionStmt, prepared_id="tx_42", action="rollback"),
        "ROLLBACK PREPARED 'tx_42'",
        id="prepare-transaction-rollback",
    ),
]
