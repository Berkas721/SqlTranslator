"""Правила pg→ch для CreateDatabaseStmt, CreateUserStmt, AlterRoleStmt, GrantStmt.

Источник правил: ``src/sql_translator/ast/rules/clickhouse/ddl/create_database.py``.
"""
from __future__ import annotations

from sql_translator.ast.metadata import Kind
from sql_translator.ast.nodes import (
    AlterRoleStmt,
    CreateDatabaseStmt,
    CreateUserStmt,
    GrantStmt,
    Identifier,
    SettingAssignment,
    TableRef,
)


class TestCreateDatabaseStmt:
    def test_plain_create_database_only_kindA_no_annotation(
        self, make, apply, kinds
    ):
        n = make(CreateDatabaseStmt, name=make(Identifier, name="db"))
        r = apply(n)
        assert kinds(r) == []

    def test_encoding_triggers_kindC(self, make, apply, rule_ids):
        n = make(CreateDatabaseStmt, name=make(Identifier, name="db"), encoding="UTF8")
        r = apply(n)
        assert "pg_ch_create_db_encoding" in rule_ids(r)
        assert any(a.kind is Kind.C for a in r.annotations)

    def test_lc_collate_triggers_kindC(self, make, apply, rule_ids):
        n = make(CreateDatabaseStmt, name=make(Identifier, name="db"), lc_collate="C")
        r = apply(n)
        assert "pg_ch_create_db_encoding" in rule_ids(r)

    def test_owner_triggers_kindD(self, make, apply, rule_ids, kinds):
        owner = make(Identifier, name="alice")
        n = make(CreateDatabaseStmt, name=make(Identifier, name="db"), owner=owner)
        r = apply(n)
        assert "pg_ch_create_db_owner" in rule_ids(r)
        assert Kind.D in kinds(r)

    def test_template_triggers_kindD(self, make, apply, rule_ids):
        n = make(
            CreateDatabaseStmt,
            name=make(Identifier, name="db"),
            template="template0",
        )
        r = apply(n)
        assert "pg_ch_create_db_template" in rule_ids(r)

    def test_owner_and_encoding_yield_both_C_and_D(
        self, make, apply, rule_ids
    ):
        owner = make(Identifier, name="alice")
        n = make(
            CreateDatabaseStmt,
            name=make(Identifier, name="db"),
            encoding="UTF8",
            owner=owner,
        )
        r = apply(n)
        ids = rule_ids(r)
        assert "pg_ch_create_db_encoding" in ids
        assert "pg_ch_create_db_owner" in ids


class TestCreateUserStmt:
    def test_plain_user_only_kindA(self, make, apply, kinds):
        n = make(CreateUserStmt, name=make(Identifier, name="bob"))
        r = apply(n)
        assert kinds(r) == []
        assert r.auth_method is None

    def test_password_rewrites_auth_method_to_default(
        self, make, apply, kinds
    ):
        n = make(
            CreateUserStmt,
            name=make(Identifier, name="bob"),
            password="secret",
        )
        r = apply(n)
        assert kinds(r) == []
        assert r.auth_method == "sha256_password"
        assert r.password == "secret"

    def test_password_with_explicit_auth_method_is_preserved(
        self, make, apply
    ):
        n = make(
            CreateUserStmt,
            name=make(Identifier, name="bob"),
            password="secret",
            auth_method="double_sha1_password",
        )
        r = apply(n)
        assert r.auth_method == "double_sha1_password"


class TestAlterRoleStmt:
    def test_plain_alter_only_kindA(self, make, apply, kinds):
        n = make(AlterRoleStmt, name=make(Identifier, name="bob"))
        r = apply(n)
        assert kinds(r) == []

    def test_password_rewrites_auth_method(self, make, apply, kinds):
        n = make(
            AlterRoleStmt,
            name=make(Identifier, name="bob"),
            password="secret",
        )
        r = apply(n)
        assert kinds(r) == []
        assert r.auth_method == "sha256_password"

    def test_settings_trigger_kindD(self, make, apply, rule_ids):
        sa = make(SettingAssignment, name="work_mem", value=None)
        n = make(
            AlterRoleStmt,
            name=make(Identifier, name="bob"),
            settings=[sa],
        )
        r = apply(n)
        assert "pg_ch_alter_role_settings" in rule_ids(r)


class TestGrantStmt:
    def test_plain_grant_only_kindA(self, make, apply, kinds):
        n = make(GrantStmt)
        r = apply(n)
        assert kinds(r) == []

    def test_grant_privilege_triggers_kindC(self, make, apply, rule_ids):
        obj = make(TableRef)
        n = make(
            GrantStmt,
            is_grant=True,
            privileges=["SELECT", "INSERT"],
            objects=[obj],
            grantees=[make(Identifier, name="bob")],
            is_role_grant=False,
        )
        r = apply(n)
        assert "pg_ch_grant_privilege" in rule_ids(r)

    def test_role_grant_triggers_kindD_not_C(self, make, apply, rule_ids):
        n = make(
            GrantStmt,
            is_grant=True,
            is_role_grant=True,
            roles=[make(Identifier, name="admin")],
            grantees=[make(Identifier, name="bob")],
        )
        r = apply(n)
        ids = rule_ids(r)
        assert "pg_ch_grant_role" in ids
        assert "pg_ch_grant_privilege" not in ids

    def test_privilege_without_privileges_list_does_not_trigger_C(
        self, make, apply, rule_ids
    ):
        n = make(GrantStmt, is_grant=True, is_role_grant=False, privileges=[])
        r = apply(n)
        assert "pg_ch_grant_privilege" not in rule_ids(r)
