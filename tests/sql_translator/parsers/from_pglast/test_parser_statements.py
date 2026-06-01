"""Покрытие диспетчера _dispatch_stmt: для каждой ветки — отдельный тест
проверяет, что parser возвращает узел нужного класса с корректной формой."""
from __future__ import annotations

import pytest

from sql_translator.ast import (
    AlterRoleStmt, BeginStmt, CommitStmt, CopyStmt, CreateDatabaseStmt,
    CreateFunctionStmt, CreateIndexStmt, CreateRoleStmt, CreateTableStmt,
    CreateUserStmt, CreateViewStmt, GrantStmt, InsertStmt, LockTableStmt,
    MergeStmt, PrepareTransactionStmt, RawStatement, RollbackStmt,
    SavepointStmt, SelectStmt, SetConstraintsStmt,
)


class TestSelectAndInsertDispatch:
    def test_select(self, parse_one):
        s = parse_one("SELECT 1")
        assert isinstance(s, SelectStmt)

    def test_insert_values(self, parse_one):
        s = parse_one("INSERT INTO t VALUES (1, 2)")
        assert isinstance(s, InsertStmt)
        assert s.target is not None
        assert s.source is not None

    def test_insert_with_columns(self, parse_one):
        s = parse_one("INSERT INTO t (a, b) VALUES (1, 2)")
        assert [c.name for c in s.columns] == ["a", "b"]

    def test_insert_select(self, parse_one):
        s = parse_one("INSERT INTO t SELECT * FROM other")
        assert isinstance(s, InsertStmt)
        assert s.source is not None

    def test_insert_returning(self, parse_one):
        s = parse_one("INSERT INTO t (a) VALUES (1) RETURNING id")
        assert isinstance(s, InsertStmt)
        assert len(s.returning) == 1

    def test_insert_on_conflict_do_nothing(self, parse_one):
        s = parse_one("INSERT INTO t (a) VALUES (1) ON CONFLICT DO NOTHING")
        assert s.on_conflict is not None


class TestCreateTableDispatch:
    def test_simple(self, parse_one):
        s = parse_one("CREATE TABLE t (id INT, name TEXT)")
        assert isinstance(s, CreateTableStmt)
        assert len(s.columns) == 2
        assert s.if_not_exists is False
        assert s.temporary is False

    def test_if_not_exists(self, parse_one):
        s = parse_one("CREATE TABLE IF NOT EXISTS t (id INT)")
        assert s.if_not_exists is True

    def test_temporary(self, parse_one):
        s = parse_one("CREATE TEMP TABLE t (id INT)")
        assert s.temporary is True

    def test_unlogged(self, parse_one):
        s = parse_one("CREATE UNLOGGED TABLE t (id INT)")
        assert s.unlogged is True

    def test_column_types_normalized(self, parse_one):
        s = parse_one("CREATE TABLE t (a INT, b BIGINT, c BOOLEAN)")
        types = [c.type.name for c in s.columns]
        assert types == ["INTEGER", "BIGINT", "BOOLEAN"]


class TestCreateViewDispatch:
    def test_simple_view(self, parse_one):
        s = parse_one("CREATE VIEW v AS SELECT 1")
        assert isinstance(s, CreateViewStmt)
        assert s.is_materialized is False
        assert s.query is not None

    def test_or_replace(self, parse_one):
        s = parse_one("CREATE OR REPLACE VIEW v AS SELECT 1")
        assert s.or_replace is True

    def test_materialized(self, parse_one):
        s = parse_one("CREATE MATERIALIZED VIEW v AS SELECT 1")
        assert isinstance(s, CreateViewStmt)
        assert s.is_materialized is True

    def test_create_table_as_becomes_view_like(self, parse_one):
        # _conv_create_table_as → CreateViewStmt с is_materialized=True
        s = parse_one("CREATE TABLE t AS SELECT * FROM other")
        assert isinstance(s, CreateViewStmt)


class TestCreateIndexDispatch:
    def test_simple_index(self, parse_one):
        s = parse_one("CREATE INDEX idx ON t (col)")
        assert isinstance(s, CreateIndexStmt)
        assert s.unique is False
        assert s.if_not_exists is False
        assert len(s.columns) == 1

    def test_unique_index(self, parse_one):
        s = parse_one("CREATE UNIQUE INDEX idx ON t (col)")
        assert s.unique is True

    def test_if_not_exists(self, parse_one):
        s = parse_one("CREATE INDEX IF NOT EXISTS idx ON t (col)")
        assert s.if_not_exists is True

    def test_using_method(self, parse_one):
        s = parse_one("CREATE INDEX idx ON t USING gin (col)")
        assert s.using_method == "gin"

    def test_partial_index(self, parse_one):
        s = parse_one("CREATE INDEX idx ON t (col) WHERE col > 0")
        assert s.where is not None


class TestCreateFunctionDispatch:
    def test_simple_function(self, parse_one):
        sql = (
            "CREATE FUNCTION add_one(x INT) RETURNS INT "
            "AS $$ SELECT x + 1 $$ LANGUAGE sql"
        )
        s = parse_one(sql)
        assert isinstance(s, CreateFunctionStmt)
        assert s.language == "sql"
        assert s.returns is not None

    def test_or_replace_function(self, parse_one):
        sql = (
            "CREATE OR REPLACE FUNCTION f() RETURNS INT "
            "AS $$ SELECT 1 $$ LANGUAGE sql"
        )
        s = parse_one(sql)
        assert s.or_replace is True


class TestCreateDatabaseDispatch:
    def test_simple_database(self, parse_one):
        s = parse_one("CREATE DATABASE mydb")
        assert isinstance(s, CreateDatabaseStmt)
        assert s.name.name == "mydb"

    def test_with_encoding(self, parse_one):
        s = parse_one("CREATE DATABASE mydb ENCODING 'UTF8'")
        assert s.encoding == "UTF8"


class TestRolesAndPrivileges:
    def test_create_role(self, parse_one):
        s = parse_one("CREATE ROLE r")
        # CREATE ROLE без LOGIN → CreateRoleStmt; с LOGIN → CreateUserStmt
        assert isinstance(s, (CreateRoleStmt, CreateUserStmt))

    def test_create_user_has_login(self, parse_one):
        # CREATE USER эквивалентен CREATE ROLE WITH LOGIN
        s = parse_one("CREATE USER u")
        assert isinstance(s, CreateUserStmt)

    def test_grant(self, parse_one):
        s = parse_one("GRANT SELECT ON t TO u")
        assert isinstance(s, GrantStmt)
        assert s.is_grant is True
        assert "select" in s.privileges

    def test_revoke(self, parse_one):
        s = parse_one("REVOKE SELECT ON t FROM u")
        assert isinstance(s, GrantStmt)
        assert s.is_grant is False

    def test_grant_role_to_user(self, parse_one):
        s = parse_one("GRANT admin_role TO u")
        assert isinstance(s, GrantStmt)
        assert s.is_role_grant is True

    def test_alter_role(self, parse_one):
        s = parse_one("ALTER ROLE r WITH PASSWORD 'pwd'")
        assert isinstance(s, AlterRoleStmt)
        assert s.name.name == "r"
        assert s.password == "pwd"



class TestCopyDispatch:
    def test_copy_from_file(self, parse_one):
        s = parse_one("COPY t FROM '/data.csv'")
        assert isinstance(s, CopyStmt)
        assert s.direction == "FROM"
        assert s.filename == "/data.csv"

    def test_copy_to_file(self, parse_one):
        s = parse_one("COPY t TO '/out.csv'")
        assert s.direction == "TO"
        assert s.filename == "/out.csv"

    def test_copy_from_stdin(self, parse_one):
        s = parse_one("COPY t FROM STDIN")
        assert s.stdin is True
        assert s.filename is None

    def test_copy_to_stdout(self, parse_one):
        s = parse_one("COPY t TO STDOUT")
        assert s.stdout is True

    def test_copy_with_format(self, parse_one):
        s = parse_one("COPY t FROM '/data.csv' (FORMAT csv, HEADER true)")
        assert s.format == "csv"
        assert s.header is True

    def test_copy_program(self, parse_one):
        s = parse_one("COPY t FROM PROGRAM 'gzip -dc /data.csv.gz'")
        assert s.program is not None


class TestMergeDispatch:
    def test_merge(self, parse_one):
        sql = (
            "MERGE INTO target t USING src s ON t.id = s.id "
            "WHEN MATCHED THEN DELETE"
        )
        s = parse_one(sql)
        assert isinstance(s, MergeStmt)


class TestLockDispatch:
    @pytest.mark.parametrize("sql_mode,expected_mode", [
        ("ACCESS SHARE",          "ACCESS SHARE"),
        ("ROW SHARE",             "ROW SHARE"),
        ("ROW EXCLUSIVE",         "ROW EXCLUSIVE"),
        ("SHARE UPDATE EXCLUSIVE","SHARE UPDATE EXCLUSIVE"),
        ("SHARE",                 "SHARE"),
        ("SHARE ROW EXCLUSIVE",   "SHARE ROW EXCLUSIVE"),
        ("EXCLUSIVE",             "EXCLUSIVE"),
        ("ACCESS EXCLUSIVE",      "ACCESS EXCLUSIVE"),
    ])
    def test_lock_modes(self, parse_one, sql_mode, expected_mode):
        s = parse_one(f"LOCK TABLE t IN {sql_mode} MODE")
        assert isinstance(s, LockTableStmt)
        assert s.mode == expected_mode


class TestSetConstraintsDispatch:
    def test_deferred(self, parse_one):
        s = parse_one("SET CONSTRAINTS ALL DEFERRED")
        assert isinstance(s, SetConstraintsStmt)
        assert s.mode == "DEFERRED"

    def test_immediate(self, parse_one):
        s = parse_one("SET CONSTRAINTS ALL IMMEDIATE")
        assert s.mode == "IMMEDIATE"


class TestTransactionDispatch:
    def test_begin(self, parse_one):
        s = parse_one("BEGIN")
        assert isinstance(s, BeginStmt)

    def test_start_transaction(self, parse_one):
        s = parse_one("START TRANSACTION")
        assert isinstance(s, BeginStmt)

    def test_commit(self, parse_one):
        s = parse_one("COMMIT")
        assert isinstance(s, CommitStmt)

    def test_end_aliases_commit(self, parse_one):
        s = parse_one("END")
        assert isinstance(s, CommitStmt)

    def test_rollback(self, parse_one):
        s = parse_one("ROLLBACK")
        assert isinstance(s, RollbackStmt)

    def test_savepoint(self, parse_one):
        s = parse_one("SAVEPOINT sp1")
        assert isinstance(s, SavepointStmt)
        assert s.action == "savepoint"
        assert s.name == "sp1"

    def test_release_savepoint(self, parse_one):
        s = parse_one("RELEASE SAVEPOINT sp1")
        assert isinstance(s, SavepointStmt)
        assert s.action == "release"

    def test_rollback_to_savepoint(self, parse_one):
        s = parse_one("ROLLBACK TO SAVEPOINT sp1")
        assert isinstance(s, SavepointStmt)
        assert s.action == "rollback_to"

    def test_prepare_transaction(self, parse_one):
        s = parse_one("PREPARE TRANSACTION 'tx1'")
        assert isinstance(s, PrepareTransactionStmt)
        assert s.action == "prepare"
        assert s.prepared_id == "tx1"

    def test_commit_prepared(self, parse_one):
        s = parse_one("COMMIT PREPARED 'tx1'")
        assert isinstance(s, PrepareTransactionStmt)
        assert s.action == "commit"

    def test_rollback_prepared(self, parse_one):
        s = parse_one("ROLLBACK PREPARED 'tx1'")
        assert isinstance(s, PrepareTransactionStmt)
        assert s.action == "rollback"


class TestRawFallback:
    def test_unsupported_statement_wrapped_in_raw_with_warning(self):
        from sql_translator.parser import parse_sql
        sql = (
            "CREATE TRIGGER tr BEFORE INSERT ON t FOR EACH ROW "
            "EXECUTE FUNCTION f()"
        )
        with pytest.warns(UserWarning, match="unsupported statement"):
            script = parse_sql(sql)
        assert isinstance(script.statements[0], RawStatement)
