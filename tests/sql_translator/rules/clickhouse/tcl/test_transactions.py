"""Правила pg→ch для TCL-команд.

Источник правил: ``src/sql_translator/ast/rules/clickhouse/tcl/transactions.py``.
"""
from __future__ import annotations

import pytest

from sql_translator.ast.metadata import Kind
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


class TestBeginStmt:
    def test_begin_style_keeps_style(self, make, apply):
        n = make(BeginStmt, style="begin")
        r = apply(n)
        assert r.style == "begin"

    def test_start_transaction_rewrites_to_begin(self, make, apply):
        n = make(BeginStmt, style="start_transaction")
        r = apply(n)
        assert r.style == "begin"

    def test_start_transaction_no_B_annotation(self, make, apply, rule_ids):
        # Kind.B без message → нет аннотации.
        n = make(BeginStmt, style="start_transaction")
        r = apply(n)
        assert "pg_ch_begin_start_transaction" not in rule_ids(r)

    def test_begin_always_triggers_kindC_semantics(
        self, make, apply, rule_ids, kinds
    ):
        n = make(BeginStmt, style="begin")
        r = apply(n)
        assert "pg_ch_begin_semantics" in rule_ids(r)
        assert Kind.C in kinds(r)

    def test_begin_semantics_message_mentions_experimental(self, make, apply):
        n = make(BeginStmt, style="begin")
        r = apply(n)
        ann = next(a for a in r.annotations if a.rule_id == "pg_ch_begin_semantics")
        msg = (ann.message or "").lower()
        assert "экспериментальн" in msg or "insert" in msg

    def test_begin_no_fallback(self, make, apply, rule_ids):
        n = make(BeginStmt)
        r = apply(n)
        assert "pg_ch.fallback" not in rule_ids(r)


class TestCommitStmt:
    def test_commit_style_keeps_style(self, make, apply):
        n = make(CommitStmt, style="commit")
        r = apply(n)
        assert r.style == "commit"

    def test_end_rewrites_to_commit(self, make, apply):
        n = make(CommitStmt, style="end")
        r = apply(n)
        assert r.style == "commit"

    def test_end_no_B_annotation(self, make, apply, rule_ids):
        n = make(CommitStmt, style="end")
        r = apply(n)
        assert "pg_ch_commit_end_alias" not in rule_ids(r)

    def test_commit_always_triggers_kindC_semantics(
        self, make, apply, rule_ids, kinds
    ):
        n = make(CommitStmt, style="commit")
        r = apply(n)
        assert "pg_ch_commit_semantics" in rule_ids(r)
        assert Kind.C in kinds(r)


class TestRollbackStmt:
    def test_rollback_style_keeps_style(self, make, apply):
        n = make(RollbackStmt, style="rollback")
        r = apply(n)
        assert r.style == "rollback"

    def test_abort_rewrites_to_rollback(self, make, apply):
        n = make(RollbackStmt, style="abort")
        r = apply(n)
        assert r.style == "rollback"

    def test_abort_no_B_annotation(self, make, apply, rule_ids):
        n = make(RollbackStmt, style="abort")
        r = apply(n)
        assert "pg_ch_rollback_abort_alias" not in rule_ids(r)

    def test_rollback_always_triggers_kindC_semantics(
        self, make, apply, rule_ids, kinds
    ):
        n = make(RollbackStmt, style="rollback")
        r = apply(n)
        assert "pg_ch_rollback_semantics" in rule_ids(r)
        assert Kind.C in kinds(r)


class TestSavepointStmt:
    @pytest.mark.parametrize("action", [
        "savepoint", "release", "rollback_to",
    ])
    def test_savepoint_always_triggers_kindE(
        self, make, apply, rule_ids, kinds, action
    ):
        n = make(SavepointStmt, action=action, name="sp1")
        r = apply(n)
        assert "pg_ch_savepoint_e" in rule_ids(r)
        assert Kind.E in kinds(r)

    def test_savepoint_no_fallback(self, make, apply, rule_ids):
        n = make(SavepointStmt)
        r = apply(n)
        assert "pg_ch.fallback" not in rule_ids(r)


class TestSetTransactionIsolation:
    @pytest.mark.parametrize("level", [
        "READ UNCOMMITTED", "READ COMMITTED", "REPEATABLE READ", "SERIALIZABLE",
    ])
    def test_isolation_level_triggers_kindE(
        self, make, apply, rule_ids, kinds, level
    ):
        n = make(SetTransactionStmt, isolation_level=level)
        r = apply(n)
        assert "pg_ch_set_transaction_isolation" in rule_ids(r)
        assert Kind.E in kinds(r)

    def test_no_isolation_no_rule(self, make, apply, rule_ids):
        n = make(SetTransactionStmt, isolation_level=None)
        r = apply(n)
        assert "pg_ch_set_transaction_isolation" not in rule_ids(r)


class TestSetTransactionReadOnly:
    @pytest.mark.parametrize("value", [True, False])
    def test_read_only_triggers_kindE(
        self, make, apply, rule_ids, kinds, value
    ):
        n = make(SetTransactionStmt, read_only=value)
        r = apply(n)
        assert "pg_ch_set_transaction_readonly" in rule_ids(r)
        assert Kind.E in kinds(r)

    def test_no_read_only_no_rule(self, make, apply, rule_ids):
        n = make(SetTransactionStmt, read_only=None)
        r = apply(n)
        assert "pg_ch_set_transaction_readonly" not in rule_ids(r)


class TestSetTransactionDeferrable:
    @pytest.mark.parametrize("value", [True, False])
    def test_deferrable_triggers_kindE(
        self, make, apply, rule_ids, kinds, value
    ):
        n = make(SetTransactionStmt, deferrable=value)
        r = apply(n)
        assert "pg_ch_set_transaction_deferrable" in rule_ids(r)
        assert Kind.E in kinds(r)

    def test_no_deferrable_no_rule(self, make, apply, rule_ids):
        n = make(SetTransactionStmt, deferrable=None)
        r = apply(n)
        assert "pg_ch_set_transaction_deferrable" not in rule_ids(r)


class TestSetTransactionScope:
    @pytest.mark.parametrize("scope", ["session", "local"])
    def test_session_local_scope_triggers_kindE(
        self, make, apply, rule_ids, kinds, scope
    ):
        n = make(SetTransactionStmt, scope=scope)
        r = apply(n)
        assert "pg_ch_set_transaction_session" in rule_ids(r)
        assert Kind.E in kinds(r)

    def test_transaction_scope_does_not_trigger(self, make, apply, rule_ids):
        n = make(SetTransactionStmt, scope="transaction")
        r = apply(n)
        assert "pg_ch_set_transaction_session" not in rule_ids(r)


class TestSetTransactionBase:
    def test_empty_set_transaction_no_fallback(self, make, apply, rule_ids):
        # Базовый A без message блокирует F-fallback; ни одно E не сработает.
        n = make(SetTransactionStmt, scope="transaction")
        r = apply(n)
        ids = rule_ids(r)
        assert "pg_ch.fallback" not in ids
        for forbidden in (
            "pg_ch_set_transaction_isolation",
            "pg_ch_set_transaction_readonly",
            "pg_ch_set_transaction_deferrable",
            "pg_ch_set_transaction_session",
        ):
            assert forbidden not in ids


class TestSetConstraintsStmt:
    @pytest.mark.parametrize("mode", ["DEFERRED", "IMMEDIATE"])
    def test_set_constraints_triggers_kindE(
        self, make, apply, rule_ids, kinds, mode
    ):
        n = make(SetConstraintsStmt, mode=mode)
        r = apply(n)
        assert "pg_ch_set_constraints_e" in rule_ids(r)
        assert Kind.E in kinds(r)


class TestLockTableStmt:
    @pytest.mark.parametrize("mode", [
        "ACCESS SHARE", "ROW SHARE", "ACCESS EXCLUSIVE", None,
    ])
    def test_lock_table_triggers_kindE(
        self, make, apply, rule_ids, kinds, mode
    ):
        n = make(LockTableStmt, mode=mode)
        r = apply(n)
        assert "pg_ch_lock_table_e" in rule_ids(r)
        assert Kind.E in kinds(r)


class TestPrepareTransactionStmt:
    @pytest.mark.parametrize("action", ["prepare", "commit", "rollback"])
    def test_prepare_transaction_triggers_kindE(
        self, make, apply, rule_ids, kinds, action
    ):
        n = make(PrepareTransactionStmt, prepared_id="tx_42", action=action)
        r = apply(n)
        assert "pg_ch_prepare_transaction_e" in rule_ids(r)
        assert Kind.E in kinds(r)
