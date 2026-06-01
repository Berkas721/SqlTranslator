"""Кейсы для прочих простых узлов: RawStatement, ValuesClause,
SubqueryExpr (EXISTS/NOT EXISTS), CreateRoleStmt, CreateDatabaseStmt,
CreateUserStmt, AlterRoleStmt, MergeStmt fallback."""
from __future__ import annotations

import pytest

from sql_translator.ast.nodes import (
    AlterRoleStmt,
    CreateDatabaseStmt,
    CreateRoleStmt,
    CreateUserStmt,
    Identifier,
    Literal,
    MergeStmt,
    RawStatement,
    ValuesClause,
)


def _ident(make, name, quoted=False):
    return make(Identifier, name=name, quoted=quoted)


def _lit(make, value=1, kind="int", raw=None):
    return make(Literal, value=value, literal_kind=kind,
                raw=raw if raw is not None else str(value))


CASES: list = [
    # ── RawStatement ─────────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(RawStatement, text="/* anything */"),
        "/* anything */",
        id="raw-statement",
    ),

    # ── ValuesClause ─────────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(ValuesClause, rows=[[_lit(m, 1), _lit(m, 2)]]),
        "VALUES\n    (1, 2)",
        id="values-single-row",
    ),
    pytest.param(
        lambda m: m(ValuesClause, rows=[
            [_lit(m, 1), _lit(m, 2)],
            [_lit(m, 3), _lit(m, 4)],
        ]),
        "VALUES\n    (1, 2),\n    (3, 4)",
        id="values-two-rows",
    ),

    # ── CreateRoleStmt ───────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(CreateRoleStmt, name=_ident(m, "ro")),
        "CREATE ROLE ro",
        id="create-role",
    ),
    pytest.param(
        lambda m: m(CreateRoleStmt, name=_ident(m, "ro"), if_not_exists=True),
        "CREATE ROLE IF NOT EXISTS ro",
        id="create-role-ine",
    ),

    # ── CreateDatabaseStmt ───────────────────────────────────────────────────
    pytest.param(
        lambda m: m(CreateDatabaseStmt, name=_ident(m, "db")),
        "CREATE DATABASE db",
        id="create-db",
    ),
    pytest.param(
        lambda m: m(CreateDatabaseStmt, name=_ident(m, "db"),
                    if_not_exists=True, engine="Atomic"),
        "CREATE DATABASE IF NOT EXISTS db ENGINE = Atomic",
        id="create-db-ine-engine",
    ),

    # ── CreateUserStmt ───────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(CreateUserStmt, name=_ident(m, "alice")),
        "CREATE USER alice",
        id="create-user-bare",
    ),
    pytest.param(
        lambda m: m(CreateUserStmt, name=_ident(m, "alice"),
                    if_not_exists=True, password="secret"),
        "CREATE USER IF NOT EXISTS alice IDENTIFIED WITH plaintext_password BY 'secret'",
        id="create-user-password",
    ),

    # ── AlterRoleStmt ────────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(AlterRoleStmt, name=_ident(m, "alice"), password="new"),
        "ALTER USER alice IDENTIFIED WITH plaintext_password BY 'new'",
        id="alter-role-password",
    ),

    # ── MergeStmt — fallback comment ─────────────────────────────────────────
    pytest.param(
        lambda m: m(MergeStmt),
        "/* MERGE: no equivalent in ClickHouse */",
        id="merge-fallback",
    ),
]
