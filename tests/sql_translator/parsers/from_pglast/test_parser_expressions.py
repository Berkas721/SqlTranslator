"""Покрытие конвертеров выражений из _EXPR_DISPATCH:
литералы, идентификаторы, операторы, функции, CAST, CASE, подзапросы и т.д."""
from __future__ import annotations

import pytest

from sql_translator.ast import (
    BetweenExpr, BinaryOp, Cast, CaseExpr, ColumnRef, FunctionCall, Identifier,
    LikeExpr, Literal, ParamRef, SimilarToExpr, StarExpr, SubqueryExpr,
    TupleConstructor, UnaryOp, WhenBranch,
)


class TestLiterals:
    def test_integer(self, parse_expr):
        e = parse_expr("42")
        assert isinstance(e, Literal)
        assert e.literal_kind == "int"
        assert e.value == 42

    def test_float(self, parse_expr):
        e = parse_expr("3.14")
        assert isinstance(e, Literal)
        assert e.literal_kind == "float"
        assert e.value == pytest.approx(3.14)

    def test_string(self, parse_expr):
        e = parse_expr("'hello'")
        assert isinstance(e, Literal)
        assert e.literal_kind == "string"
        assert e.value == "hello"
        assert e.quote_style == "single"

    def test_empty_string(self, parse_expr):
        e = parse_expr("''")
        assert e.literal_kind == "string"
        assert e.value == ""

    def test_boolean_true(self, parse_expr):
        e = parse_expr("TRUE")
        assert e.literal_kind == "bool"
        assert e.value is True

    def test_boolean_false(self, parse_expr):
        e = parse_expr("FALSE")
        assert e.literal_kind == "bool"
        assert e.value is False

    def test_null(self, parse_expr):
        e = parse_expr("NULL")
        assert isinstance(e, Literal)
        assert e.literal_kind == "null"
        assert e.value is None


class TestColumnRef:
    def test_simple_column(self, parse_expr):
        e = parse_expr("col")
        assert isinstance(e, ColumnRef)
        assert e.column.name == "col"
        assert e.table is None
        assert e.schema is None
        assert e.database is None

    def test_table_qualified(self, parse_expr):
        e = parse_expr("t.col")
        assert isinstance(e, ColumnRef)
        assert e.table.name == "t"
        assert e.column.name == "col"
        assert e.schema is None
        assert e.database is None

    def test_schema_qualified(self, parse_expr):
        e = parse_expr("s.t.col")
        assert e.schema.name == "s"
        assert e.table.name == "t"
        assert e.column.name == "col"
        assert e.database is None

    def test_db_schema_qualified(self, parse_expr):
        e = parse_expr("d.s.t.col")
        assert e.database.name == "d"
        assert e.schema.name == "s"
        assert e.table.name == "t"
        assert e.column.name == "col"

    def test_star(self, parse_expr):
        e = parse_expr("*")
        assert isinstance(e, StarExpr)
        assert e.table is None

    def test_qualified_star(self, parse_expr):
        e = parse_expr("t.*")
        assert isinstance(e, StarExpr)
        assert e.table.name == "t"

class TestBinaryArithmetic:
    @pytest.mark.parametrize("op", ["+", "-", "*", "/", "%"])
    def test_arithmetic_ops(self, parse_expr, op):
        e = parse_expr(f"1 {op} 2")
        assert isinstance(e, BinaryOp)
        assert e.op == op
        assert isinstance(e.left, Literal)
        assert isinstance(e.right, Literal)


class TestBinaryComparison:
    @pytest.mark.parametrize("op", ["=", "<>", "<", ">", "<=", ">="])
    def test_comparison_ops(self, parse_expr, op):
        e = parse_expr(f"a {op} b")
        assert isinstance(e, BinaryOp)
        assert e.op == op

    def test_is_distinct_from(self, parse_expr):
        e = parse_expr("a IS DISTINCT FROM b")
        assert isinstance(e, BinaryOp)
        assert e.op == "IS DISTINCT FROM"

    def test_is_not_distinct_from(self, parse_expr):
        e = parse_expr("a IS NOT DISTINCT FROM b")
        assert e.op == "IS NOT DISTINCT FROM"

class TestBooleanLogic:
    def test_and(self, parse_expr):
        e = parse_expr("a AND b")
        assert isinstance(e, BinaryOp)
        assert e.op == "AND"

    def test_or(self, parse_expr):
        e = parse_expr("a OR b")
        assert isinstance(e, BinaryOp)
        assert e.op == "OR"

    def test_not_is_prefix_unary(self, parse_expr):
        e = parse_expr("NOT a")
        assert isinstance(e, UnaryOp)
        assert e.op == "NOT"
        assert e.position == "prefix"

    def test_chained_and_is_left_associative(self, parse_expr):
        # AND/OR с >2 аргументами разворачиваются в левое дерево BinaryOp
        e = parse_expr("a AND b AND c")
        assert isinstance(e, BinaryOp)
        assert e.op == "AND"
        assert isinstance(e.left, BinaryOp)
        assert e.left.op == "AND"
        assert isinstance(e.right, ColumnRef)


class TestNullTests:
    def test_is_null(self, parse_expr):
        e = parse_expr("a IS NULL")
        assert isinstance(e, UnaryOp)
        assert e.op == "IS NULL"
        assert e.position == "postfix"

    def test_is_not_null(self, parse_expr):
        e = parse_expr("a IS NOT NULL")
        assert isinstance(e, UnaryOp)
        assert e.op == "IS NOT NULL"
        assert e.position == "postfix"


class TestBooleanTests:
    @pytest.mark.parametrize("sql,expected_op", [
        ("a IS TRUE",        "IS TRUE"),
        ("a IS NOT TRUE",    "IS NOT TRUE"),
        ("a IS FALSE",       "IS FALSE"),
        ("a IS NOT FALSE",   "IS NOT FALSE"),
        ("a IS UNKNOWN",     "IS UNKNOWN"),
        ("a IS NOT UNKNOWN", "IS NOT UNKNOWN"),
    ])
    def test_boolean_tests(self, parse_expr, sql, expected_op):
        e = parse_expr(sql)
        assert isinstance(e, UnaryOp)
        assert e.op == expected_op
        assert e.position == "postfix"


class TestBetween:
    def test_between(self, parse_expr):
        e = parse_expr("a BETWEEN 1 AND 10")
        assert isinstance(e, BetweenExpr)
        assert e.negated is False
        assert e.symmetric is False
        assert isinstance(e.low, Literal)
        assert isinstance(e.high, Literal)

    def test_not_between(self, parse_expr):
        e = parse_expr("a NOT BETWEEN 1 AND 10")
        assert e.negated is True
        assert e.symmetric is False

    def test_between_symmetric(self, parse_expr):
        e = parse_expr("a BETWEEN SYMMETRIC 1 AND 10")
        assert e.negated is False
        assert e.symmetric is True

    def test_not_between_symmetric(self, parse_expr):
        e = parse_expr("a NOT BETWEEN SYMMETRIC 1 AND 10")
        assert e.negated is True
        assert e.symmetric is True


class TestIn:
    def test_in_list(self, parse_expr):
        e = parse_expr("a IN (1, 2, 3)")
        assert isinstance(e, BinaryOp)
        assert e.op == "IN"
        assert isinstance(e.right, TupleConstructor)
        assert len(e.right.elements) == 3

    def test_not_in_list(self, parse_expr):
        e = parse_expr("a NOT IN (1, 2)")
        assert isinstance(e, BinaryOp)
        assert e.op == "NOT IN"
        assert isinstance(e.right, TupleConstructor)
        assert len(e.right.elements) == 2


class TestLike:
    def test_like(self, parse_expr):
        e = parse_expr("name LIKE 'abc%'")
        assert isinstance(e, LikeExpr)
        assert e.negated is False
        assert e.case_insensitive is False
        assert e.escape is None

    def test_not_like(self, parse_expr):
        e = parse_expr("name NOT LIKE 'abc%'")
        assert isinstance(e, LikeExpr)
        assert e.negated is True
        assert e.case_insensitive is False

    def test_ilike(self, parse_expr):
        e = parse_expr("name ILIKE 'abc%'")
        assert isinstance(e, LikeExpr)
        assert e.case_insensitive is True
        assert e.negated is False

    def test_not_ilike(self, parse_expr):
        e = parse_expr("name NOT ILIKE 'abc%'")
        assert e.case_insensitive is True
        assert e.negated is True

    def test_like_escape(self, parse_expr):
        e = parse_expr("name LIKE 'a\\%b' ESCAPE '\\'")
        assert isinstance(e, LikeExpr)
        assert e.escape is not None


class TestSimilarTo:
    def test_similar_to(self, parse_expr):
        e = parse_expr("name SIMILAR TO 'a.*'")
        assert isinstance(e, SimilarToExpr)
        assert e.negated is False

    def test_not_similar_to(self, parse_expr):
        e = parse_expr("name NOT SIMILAR TO 'a.*'")
        assert isinstance(e, SimilarToExpr)
        assert e.negated is True


class TestFunctionCall:
    def test_no_args(self, parse_expr):
        e = parse_expr("now()")
        assert isinstance(e, FunctionCall)
        assert e.name.name == "now"
        assert e.args == []
        assert e.distinct is False
        assert e.star is False

    def test_with_args(self, parse_expr):
        e = parse_expr("substring('abc', 1, 2)")
        assert isinstance(e, FunctionCall)
        assert e.name.name == "substring"
        assert len(e.args) == 3

    def test_count_star(self, parse_expr):
        e = parse_expr("count(*)")
        assert isinstance(e, FunctionCall)
        assert e.name.name == "count"
        assert e.star is True

    def test_count_distinct(self, parse_expr):
        e = parse_expr("count(DISTINCT x)")
        assert isinstance(e, FunctionCall)
        assert e.name.name == "count"
        assert e.distinct is True

    def test_filter_clause(self, parse_expr):
        e = parse_expr("count(*) FILTER (WHERE x > 0)")
        assert isinstance(e, FunctionCall)
        assert e.filter_where is not None

    def test_over_window(self, parse_expr):
        e = parse_expr("row_number() OVER (ORDER BY id)")
        assert isinstance(e, FunctionCall)
        assert e.over is not None

    def test_qualified_function_kept_dotted(self, parse_expr):
        # myschema.fn(x) сохраняется как 'myschema.fn' (не pg_catalog → не теряется)
        e = parse_expr("myschema.fn(1)")
        assert isinstance(e, FunctionCall)
        assert e.name.name == "myschema.fn"

    def test_pg_catalog_prefix_stripped(self, parse_expr):
        # pg_catalog.count(*) → имя 'count' без префикса
        e = parse_expr("pg_catalog.count(*)")
        assert isinstance(e, FunctionCall)
        assert e.name.name == "count"



class TestCast:
    def test_postfix_cast(self, parse_expr):
        e = parse_expr("x::INTEGER")
        assert isinstance(e, Cast)
        assert e.target_type.name == "INTEGER"

    def test_cast_keyword_syntax(self, parse_expr):
        e = parse_expr("CAST(x AS INTEGER)")
        assert isinstance(e, Cast)
        assert e.target_type.name == "INTEGER"

    @pytest.mark.parametrize("pg_type,expected_name", [
        ("int2",   "SMALLINT"),
        ("int4",   "INTEGER"),
        ("int8",   "BIGINT"),
        ("float4", "REAL"),
        ("float8", "DOUBLE PRECISION"),
        ("bool",   "BOOLEAN"),
        ("bpchar", "CHAR"),
    ])
    def test_pg_catalog_type_normalization(self, parse_expr, pg_type, expected_name):
        e = parse_expr(f"x::{pg_type}")
        assert e.target_type.name == expected_name

    def test_timestamptz_normalization(self, parse_expr):
        e = parse_expr("x::timestamptz")
        assert e.target_type.name == "TIMESTAMP"
        assert e.target_type.time_zone == "WITH TIME ZONE"

    def test_timetz_normalization(self, parse_expr):
        e = parse_expr("x::timetz")
        assert e.target_type.name == "TIME"
        assert e.target_type.time_zone == "WITH TIME ZONE"

    def test_user_type_uppercased(self, parse_expr):
        # Тип не из _PG_TYPE_NORM → пишется как есть, в верхнем регистре
        e = parse_expr("x::text")
        assert e.target_type.name == "TEXT"

    def test_type_with_params(self, parse_expr):
        e = parse_expr("x::VARCHAR(100)")
        assert e.target_type.name == "VARCHAR"
        assert len(e.target_type.params) == 1
        assert e.target_type.params[0].value == 100

    def test_array_type(self, parse_expr):
        e = parse_expr("x::INTEGER[]")
        assert e.target_type.name == "INTEGER"
        assert e.target_type.array_dims == 1


class TestCase:
    def test_searched_case(self, parse_expr):
        e = parse_expr("CASE WHEN x > 0 THEN 'pos' ELSE 'neg' END")
        assert isinstance(e, CaseExpr)
        assert e.arg is None
        assert len(e.branches) == 1
        assert e.else_expr is not None

    def test_simple_case(self, parse_expr):
        e = parse_expr("CASE x WHEN 1 THEN 'one' WHEN 2 THEN 'two' END")
        assert isinstance(e, CaseExpr)
        assert e.arg is not None
        assert len(e.branches) == 2
        assert e.else_expr is None

    def test_when_branch_structure(self, parse_expr):
        e = parse_expr("CASE WHEN x > 0 THEN 'pos' END")
        branch = e.branches[0]
        assert isinstance(branch, WhenBranch)
        assert branch.condition is not None
        assert branch.result is not None


class TestSubqueries:
    def test_exists(self, parse_expr):
        e = parse_expr("EXISTS (SELECT 1)")
        assert isinstance(e, SubqueryExpr)
        assert e.kind == "exists"
        assert e.query is not None

    def test_scalar_subquery(self, parse_expr):
        e = parse_expr("(SELECT 1)")
        assert isinstance(e, SubqueryExpr)
        assert e.kind == "scalar"

    def test_any_with_operator(self, parse_expr):
        e = parse_expr("x = ANY (SELECT y FROM t)")
        assert isinstance(e, SubqueryExpr)
        assert e.kind == "any"
        assert e.outer_op == "="

    def test_all_with_operator(self, parse_expr):
        e = parse_expr("x > ALL (SELECT y FROM t)")
        assert isinstance(e, SubqueryExpr)
        assert e.kind == "all"
        assert e.outer_op == ">"


class TestParamRef:
    def test_first_param(self, parse_expr):
        e = parse_expr("$1")
        assert isinstance(e, ParamRef)
        assert e.number == 1

    def test_multiple_params(self, parse):
        s = parse("SELECT $1, $2, $3")
        targets = s.statements[0].targets
        assert [t.expression.number for t in targets] == [1, 2, 3]


class TestExpressionSpans:
    def test_binary_op_has_source_span(self, parse_expr):
        e = parse_expr("1 + 2")
        assert e.source_span is not None

    def test_function_call_has_source_span(self, parse_expr):
        e = parse_expr("now()")
        assert e.source_span is not None

    def test_column_ref_has_source_span(self, parse_expr):
        e = parse_expr("col")
        assert e.source_span is not None
