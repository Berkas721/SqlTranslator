"""Контракт публичной функции parse_sql: диалекты, возвращаемое значение,
позиционирование, обработка ошибок."""
from __future__ import annotations

import pytest

from sql_translator.parser import parse_sql
from sql_translator.ast import (
    Dialect, InsertStmt, Script, SelectStmt, Statement,
)


class TestDialectValidation:
    def test_postgres_supported(self):
        script = parse_sql("SELECT 1", dialect="postgres")
        assert isinstance(script, Script)

    def test_default_dialect_is_postgres(self):
        script = parse_sql("SELECT 1")
        assert script.dialect == Dialect.POSTGRES

    @pytest.mark.parametrize("dialect", [
        "clickhouse", "oracle", "mysql", "", "POSTGRES", "Postgres", "pg",
    ])
    def test_unsupported_dialect_raises_value_error(self, dialect):
        with pytest.raises(ValueError, match="Unsupported dialect"):
            parse_sql("SELECT 1", dialect=dialect)

    def test_unsupported_dialect_mentions_dialect_name(self):
        with pytest.raises(ValueError, match="oracle"):
            parse_sql("SELECT 1", dialect="oracle")


class TestScriptShape:
    def test_returns_script_instance(self):
        s = parse_sql("SELECT 1")
        assert isinstance(s, Script)

    def test_script_node_kind_is_set(self):
        s = parse_sql("SELECT 1")
        assert s.node_kind == "Script"

    def test_script_dialect_is_postgres(self):
        s = parse_sql("SELECT 1")
        assert s.dialect == Dialect.POSTGRES

    def test_source_text_preserved_exactly(self):
        sql = "SELECT 1, 2, 3 FROM t"
        s = parse_sql(sql)
        assert s.source_text == sql

    def test_empty_sql_returns_script_with_no_statements(self):
        s = parse_sql("")
        assert isinstance(s, Script)
        assert s.statements == []

    def test_whitespace_only_returns_no_statements(self):
        s = parse_sql("   \n  \t  ")
        assert s.statements == []

    def test_comment_only_returns_no_statements(self):
        s = parse_sql("-- just a comment\n")
        assert s.statements == []


class TestStatementsList:
    def test_single_statement(self, parse_one):
        s = parse_one("SELECT 1")
        assert isinstance(s, SelectStmt)

    def test_multiple_statements_dispatched_individually(self):
        sql = "SELECT 1; INSERT INTO t VALUES (1); SELECT 2"
        s = parse_sql(sql)
        assert len(s.statements) == 3
        assert isinstance(s.statements[0], SelectStmt)
        assert isinstance(s.statements[1], InsertStmt)
        assert isinstance(s.statements[2], SelectStmt)

    def test_trailing_semicolon_does_not_create_extra_statement(self):
        s = parse_sql("SELECT 1;")
        assert len(s.statements) == 1

    def test_leading_semicolons_are_ignored(self):
        s = parse_sql(";;SELECT 1")
        # pglast обычно игнорирует пустые statement-ы между ;
        assert len(s.statements) == 1

    def test_every_statement_is_subclass_of_statement(self):
        s = parse_sql("SELECT 1; SELECT 2; SELECT 3")
        for stmt in s.statements:
            assert isinstance(stmt, Statement)

    def test_statement_dialect_is_postgres(self, parse_one):
        s = parse_one("SELECT 1")
        assert s.dialect == Dialect.POSTGRES

    def test_statement_has_unique_node_id(self):
        s = parse_sql("SELECT 1; SELECT 2; SELECT 3")
        ids = [stmt.node_id for stmt in s.statements]
        assert len(set(ids)) == len(ids)


class TestSourceSpan:
    def test_statement_has_source_span(self, parse_one):
        s = parse_one("SELECT 1")
        assert s.source_span is not None

    def test_span_start_at_offset_zero(self, parse_one):
        s = parse_one("SELECT 1")
        assert s.source_span.start.offset == 0

    def test_span_line_is_1_based(self, parse_one):
        s = parse_one("SELECT 1")
        assert s.source_span.start.line == 1

    def test_span_column_is_1_based(self, parse_one):
        s = parse_one("SELECT 1")
        assert s.source_span.start.column == 1

    def test_second_statement_has_later_offset(self):
        # pglast выдаёт stmt_location второго оператора уже после первого;
        # точное значение зависит от того, считает ли pglast разделитель/пробелы —
        # достаточно проверить монотонность.
        s = parse_sql("SELECT 1; SELECT 2")
        first  = s.statements[0].source_span.start.offset
        second = s.statements[1].source_span.start.offset
        assert second > first

    def test_position_column_is_consistent_with_offset(self):
        # Позиция первого оператора всегда line=1, column=1, offset=0.
        s = parse_sql("SELECT 1")
        start = s.statements[0].source_span.start
        assert (start.offset, start.line, start.column) == (0, 1, 1)


class TestErrorHandling:
    @pytest.mark.parametrize("bad_sql", [
        "SELEKT 1",                  # опечатка
        "SELECT FROM",               # незавершённый SELECT
        "SELECT 'unterminated",      # незакрытая строка
        "CREATE TABLE",              # незавершённый DDL
        "INSERT INTO",               # незавершённый INSERT
        "SELECT * FRO t",            # опечатка в ключевом слове
    ])
    def test_syntax_error_raises(self, bad_sql):
        with pytest.raises(Exception):
            parse_sql(bad_sql)

    def test_valid_sql_does_not_raise(self):
        # Smoke-test: типичные конструкции парсятся без исключений
        for sql in (
            "SELECT 1",
            "SELECT * FROM t WHERE x = 1",
            "INSERT INTO t (a, b) VALUES (1, 2)",
            "CREATE TABLE t (id INT)",
            "WITH cte AS (SELECT 1) SELECT * FROM cte",
        ):
            parse_sql(sql)  # не должен бросить
