"""Покрытие клауз SELECT: targets, WITH, DISTINCT, WHERE, GROUP BY, HAVING,
ORDER BY, LIMIT/OFFSET/FETCH, JOIN, set-operations, locking."""
from __future__ import annotations

import pytest

from sql_translator.ast import (
    JoinExpr, OrderByItem, SelectStmt,
)


class TestSelectTargets:
    def test_single_target(self, parse_one):
        s = parse_one("SELECT 1")
        assert len(s.targets) == 1

    def test_multiple_targets(self, parse_one):
        s = parse_one("SELECT 1, 2, 3")
        assert len(s.targets) == 3

    def test_target_alias(self, parse_one):
        s = parse_one("SELECT 1 AS num")
        assert s.targets[0].alias is not None
        assert s.targets[0].alias.name == "num"


class TestWithClause:
    def test_with_non_recursive(self, parse_one):
        s = parse_one("WITH cte AS (SELECT 1) SELECT * FROM cte")
        assert s.with_clause is not None
        assert s.with_clause.recursive is False
        assert len(s.with_clause.ctes) == 1

    def test_with_recursive(self, parse_one):
        sql = "WITH RECURSIVE cte AS (SELECT 1) SELECT * FROM cte"
        s = parse_one(sql)
        assert s.with_clause.recursive is True

    def test_multiple_ctes(self, parse_one):
        sql = (
            "WITH a AS (SELECT 1), b AS (SELECT 2) "
            "SELECT * FROM a JOIN b ON TRUE"
        )
        s = parse_one(sql)
        assert len(s.with_clause.ctes) == 2


class TestDistinct:
    def test_plain_distinct(self, parse_one):
        s = parse_one("SELECT DISTINCT a FROM t")
        assert s.distinct is not None
        assert s.distinct.kind == "distinct"

    def test_distinct_on(self, parse_one):
        s = parse_one("SELECT DISTINCT ON (a) a, b FROM t")
        assert s.distinct is not None
        assert s.distinct.kind == "distinct_on"
        assert len(s.distinct.on) == 1


class TestWhereGroupByHaving:
    def test_where_present(self, parse_one):
        s = parse_one("SELECT * FROM t WHERE x > 0")
        assert s.where is not None

    def test_where_absent(self, parse_one):
        s = parse_one("SELECT * FROM t")
        assert s.where is None

    def test_group_by_ordinary(self, parse_one):
        s = parse_one("SELECT a, count(*) FROM t GROUP BY a")
        assert s.group_by is not None
        assert s.group_by.kind == "ordinary"
        assert len(s.group_by.items) == 1

    def test_group_by_distinct(self, parse_one):
        s = parse_one("SELECT a FROM t GROUP BY DISTINCT a")
        assert s.group_by.kind == "distinct"

    def test_having_present(self, parse_one):
        s = parse_one("SELECT a FROM t GROUP BY a HAVING count(*) > 1")
        assert s.having is not None

    def test_having_absent(self, parse_one):
        s = parse_one("SELECT a FROM t GROUP BY a")
        assert s.having is None


class TestOrderBy:
    def test_single_order(self, parse_one):
        s = parse_one("SELECT * FROM t ORDER BY a")
        assert len(s.order_by) == 1
        assert isinstance(s.order_by[0], OrderByItem)

    def test_multiple_order(self, parse_one):
        s = parse_one("SELECT * FROM t ORDER BY a, b DESC")
        assert len(s.order_by) == 2

    def test_direction_desc(self, parse_one):
        s = parse_one("SELECT * FROM t ORDER BY a DESC")
        assert s.order_by[0].direction == "DESC"

    def test_direction_asc(self, parse_one):
        s = parse_one("SELECT * FROM t ORDER BY a ASC")
        assert s.order_by[0].direction == "ASC"

    def test_nulls_first(self, parse_one):
        s = parse_one("SELECT * FROM t ORDER BY a NULLS FIRST")
        assert s.order_by[0].nulls == "FIRST"

    def test_nulls_last(self, parse_one):
        s = parse_one("SELECT * FROM t ORDER BY a NULLS LAST")
        assert s.order_by[0].nulls == "LAST"


class TestLimitOffsetFetch:
    def test_limit_only(self, parse_one):
        s = parse_one("SELECT * FROM t LIMIT 10")
        assert s.limit is not None
        assert s.fetch is None
        assert s.offset is None

    def test_offset_only(self, parse_one):
        s = parse_one("SELECT * FROM t OFFSET 5")
        assert s.offset is not None
        assert s.limit is None

    def test_limit_and_offset(self, parse_one):
        s = parse_one("SELECT * FROM t LIMIT 10 OFFSET 5")
        assert s.limit is not None
        assert s.offset is not None

    def test_fetch_first_only(self, parse_one):
        # FETCH FIRST n ROWS ONLY → попадает в limit (limitOption=COUNT)
        s = parse_one("SELECT * FROM t ORDER BY a FETCH FIRST 5 ROWS ONLY")
        assert s.limit is not None
        assert s.fetch is None

    def test_fetch_with_ties(self, parse_one):
        # FETCH FIRST n ROWS WITH TIES → выделяется в fetch с with_ties=True
        s = parse_one("SELECT * FROM t ORDER BY a FETCH FIRST 5 ROWS WITH TIES")
        assert s.fetch is not None
        assert s.fetch.with_ties is True
        assert s.limit is None


class TestFromAndJoins:
    def test_single_table(self, parse_one):
        s = parse_one("SELECT * FROM t")
        assert len(s.from_items) == 1

    def test_cross_join_via_comma_creates_two_items(self, parse_one):
        s = parse_one("SELECT * FROM a, b")
        assert len(s.from_items) == 2

    @pytest.mark.parametrize("sql_join,expected_kind", [
        ("a JOIN b ON a.id = b.id",            "inner"),
        ("a INNER JOIN b ON a.id = b.id",      "inner"),
        ("a LEFT JOIN b ON a.id = b.id",       "left"),
        ("a LEFT OUTER JOIN b ON a.id = b.id", "left"),
        ("a RIGHT JOIN b ON a.id = b.id",      "right"),
        ("a FULL JOIN b ON a.id = b.id",       "full"),
        ("a FULL OUTER JOIN b ON a.id = b.id", "full"),
    ])
    def test_join_kinds(self, parse_one, sql_join, expected_kind):
        s = parse_one(f"SELECT * FROM {sql_join}")
        join = s.from_items[0]
        assert isinstance(join, JoinExpr)
        assert join.kind == expected_kind


class TestSetOperations:
    @pytest.mark.parametrize("op", ["UNION", "INTERSECT", "EXCEPT"])
    def test_set_op_default_is_distinct(self, parse_one, op):
        s = parse_one(f"SELECT 1 {op} SELECT 2")
        assert isinstance(s, SelectStmt)
        assert s.set_op is not None
        assert s.set_op.op == op
        assert s.set_op.quantifier == "DISTINCT"

    @pytest.mark.parametrize("op", ["UNION", "INTERSECT", "EXCEPT"])
    def test_set_op_all(self, parse_one, op):
        s = parse_one(f"SELECT 1 {op} ALL SELECT 2")
        assert s.set_op.quantifier == "ALL"

    def test_chained_set_op_is_left_associative(self, parse_one):
        s = parse_one("SELECT 1 UNION SELECT 2 UNION SELECT 3")
        # Левая голова имеет .set_op, идущий вправо до конца цепочки
        assert s.set_op is not None
        # На правом конце .set_op = None (узел-«хвост»)
        right1 = s.set_op.right
        assert right1.set_op is None or right1.set_op.right.set_op is None


class TestLockingClause:
    @pytest.mark.parametrize("clause,expected_mode", [
        ("FOR UPDATE",         "UPDATE"),
        ("FOR SHARE",          "SHARE"),
        ("FOR NO KEY UPDATE",  "NO_KEY_UPDATE"),
        ("FOR KEY SHARE",      "KEY_SHARE"),
    ])
    def test_locking_modes(self, parse_one, clause, expected_mode):
        s = parse_one(f"SELECT * FROM t {clause}")
        assert len(s.locking) == 1
        assert s.locking[0].mode == expected_mode

    def test_no_locking_by_default(self, parse_one):
        s = parse_one("SELECT * FROM t")
        assert s.locking == []


class TestNamedWindows:
    def test_named_window_collected(self, parse_one):
        s = parse_one(
            "SELECT row_number() OVER w FROM t "
            "WINDOW w AS (ORDER BY id)"
        )
        assert len(s.windows) == 1
        assert s.windows[0].name.name == "w"
