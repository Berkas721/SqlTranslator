"""Правила pg→ch для SELECT-конструкций.

Источник правил: ``src/sql_translator/ast/rules/clickhouse/dml/select.py``.
"""
from __future__ import annotations

import pytest

from sql_translator.ast.metadata import Kind
from sql_translator.ast.nodes import (
    CommonTableExpr,
    DistinctClause,
    FetchClause,
    GroupByClause,
    Identifier,
    JoinExpr,
    Literal,
    LockingClause,
    OrderByItem,
    SelectStmt,
    SetOpClause,
    SubqueryRef,
    TableFunctionRef,
    TableRef,
    WithClause,
)


class TestSelectStmtFetch:
    def _fetch(self, make, with_ties):
        f = make(FetchClause, first=True, count=make(Literal, value=10, raw="10"), with_ties=with_ties)
        return f

    def test_fetch_only_rewrites_to_limit_without_ties(
        self, make, apply, kinds
    ):
        fetch = self._fetch(make, with_ties=False)
        n = make(SelectStmt, fetch=fetch)
        r = apply(n)
        # rewrite: fetch снят, limit заполнен значением count.
        assert r.fetch is None
        assert r.limit is not None
        assert r.limit_with_ties is False
        # Kind.B без message — без аннотации.
        assert kinds(r) == []

    def test_fetch_with_ties_rewrites_to_limit_with_ties(
        self, make, apply
    ):
        fetch = self._fetch(make, with_ties=True)
        n = make(SelectStmt, fetch=fetch)
        r = apply(n)
        assert r.fetch is None
        assert r.limit is not None
        assert r.limit_with_ties is True

    def test_no_fetch_no_rewrite(self, make, apply):
        n = make(SelectStmt)
        r = apply(n)
        assert r.fetch is None
        assert r.limit is None
        assert r.limit_with_ties is False


class TestSelectStmtRecursive:
    def test_with_recursive_triggers_kindD(self, make, apply, rule_ids, kinds):
        cte = make(CommonTableExpr, name=make(Identifier, name="t"))
        wc = make(WithClause, recursive=True, ctes=[cte])
        n = make(SelectStmt, with_clause=wc)
        r = apply(n)
        assert "pg_ch_select_with_recursive" in rule_ids(r)
        assert Kind.D in kinds(r)

    def test_with_non_recursive_does_not_trigger(self, make, apply, rule_ids):
        wc = make(WithClause, recursive=False)
        n = make(SelectStmt, with_clause=wc)
        r = apply(n)
        assert "pg_ch_select_with_recursive" not in rule_ids(r)

    def test_no_with_clause_does_not_trigger(self, make, apply, rule_ids):
        n = make(SelectStmt)
        r = apply(n)
        assert "pg_ch_select_with_recursive" not in rule_ids(r)


class TestSelectStmtLocking:
    def test_for_update_triggers_kindE(self, make, apply, rule_ids, kinds):
        lock = make(LockingClause, mode="UPDATE")
        n = make(SelectStmt, locking=[lock])
        r = apply(n)
        assert "pg_ch_select_locking" in rule_ids(r)
        assert Kind.E in kinds(r)

    def test_empty_locking_does_not_trigger(self, make, apply, rule_ids):
        n = make(SelectStmt, locking=[])
        r = apply(n)
        assert "pg_ch_select_locking" not in rule_ids(r)


class TestDistinctClause:
    def test_distinct_on_triggers_kindC(self, make, apply, rule_ids, kinds):
        n = make(DistinctClause, kind="distinct_on")
        r = apply(n)
        assert "pg_ch_distinct_on" in rule_ids(r)
        assert Kind.C in kinds(r)

    @pytest.mark.parametrize("kind_value", ["distinct", "all"])
    def test_plain_distinct_does_not_trigger_C(
        self, make, apply, rule_ids, kind_value
    ):
        n = make(DistinctClause, kind=kind_value)
        r = apply(n)
        assert "pg_ch_distinct_on" not in rule_ids(r)


class TestWithClause:
    def test_plain_with_clause_only_kindA_no_annotation(
        self, make, apply, kinds
    ):
        n = make(WithClause, recursive=False)
        r = apply(n)
        assert kinds(r) == []

    def test_recursive_with_clause_only_kindA_at_this_level(
        self, make, apply, kinds
    ):
        # WITH RECURSIVE-аннотация D создаётся на SelectStmt, не на WithClause.
        n = make(WithClause, recursive=True)
        r = apply(n)
        assert kinds(r) == []


class TestGroupByClause:
    def test_group_by_all_triggers_kindE(self, make, apply, rule_ids, kinds):
        n = make(GroupByClause, kind="all")
        r = apply(n)
        assert "pg_ch_group_by_all" in rule_ids(r)
        assert Kind.E in kinds(r)

    def test_group_by_distinct_triggers_kindE(self, make, apply, rule_ids):
        n = make(GroupByClause, kind="distinct")
        r = apply(n)
        assert "pg_ch_group_by_distinct" in rule_ids(r)

    @pytest.mark.parametrize("kind_value", ["ordinary", "rollup", "cube", "grouping_sets"])
    def test_other_kinds_do_not_trigger_E(
        self, make, apply, rule_ids, kind_value
    ):
        n = make(GroupByClause, kind=kind_value)
        r = apply(n)
        ids = rule_ids(r)
        assert "pg_ch_group_by_all" not in ids
        assert "pg_ch_group_by_distinct" not in ids


class TestSetOpClause:
    @pytest.mark.parametrize("op", ["INTERSECT", "EXCEPT"])
    def test_intersect_except_no_quantifier_triggers_kindC(
        self, make, apply, rule_ids, kinds, op
    ):
        n = make(SetOpClause, op=op, quantifier=None)
        r = apply(n)
        assert "pg_ch_setop_default_mode" in rule_ids(r)
        assert Kind.C in kinds(r)

    @pytest.mark.parametrize("op", ["INTERSECT", "EXCEPT"])
    @pytest.mark.parametrize("quant", ["ALL", "DISTINCT"])
    def test_quantified_does_not_trigger(self, make, apply, rule_ids, op, quant):
        n = make(SetOpClause, op=op, quantifier=quant)
        r = apply(n)
        assert "pg_ch_setop_default_mode" not in rule_ids(r)

    @pytest.mark.parametrize("quant", [None, "ALL", "DISTINCT"])
    def test_union_does_not_trigger(self, make, apply, rule_ids, quant):
        n = make(SetOpClause, op="UNION", quantifier=quant)
        r = apply(n)
        assert "pg_ch_setop_default_mode" not in rule_ids(r)


def _tref(make):
    return make(TableRef)


class TestJoinExpr:
    def test_full_join_triggers_kindC(self, make, apply, rule_ids, kinds):
        n = make(JoinExpr, kind="full", left=_tref(make), right=_tref(make))
        r = apply(n)
        assert "pg_ch_join_full" in rule_ids(r)
        assert Kind.C in kinds(r)

    @pytest.mark.parametrize("kind_value", ["natural_inner"])
    def test_natural_join_triggers_kindE(
        self, make, apply, rule_ids, kinds, kind_value
    ):
        n = make(JoinExpr, kind=kind_value, left=_tref(make), right=_tref(make))
        r = apply(n)
        assert "pg_ch_join_natural" in rule_ids(r)
        assert Kind.E in kinds(r)

    def test_lateral_join_triggers_kindE(self, make, apply, rule_ids):
        n = make(JoinExpr, kind="inner", lateral=True,
                 left=_tref(make), right=_tref(make))
        r = apply(n)
        assert "pg_ch_join_lateral" in rule_ids(r)

    @pytest.mark.parametrize("kind_value", ["inner", "left", "right", "cross"])
    def test_plain_join_kinds_do_not_trigger_C_or_E(
        self, make, apply, rule_ids, kind_value
    ):
        n = make(JoinExpr, kind=kind_value,
                 left=_tref(make), right=_tref(make))
        r = apply(n)
        ids = rule_ids(r)
        assert "pg_ch_join_full" not in ids
        assert "pg_ch_join_natural" not in ids
        assert "pg_ch_join_lateral" not in ids


class TestOrderByItem:
    @pytest.mark.parametrize("nulls_value", ["FIRST", "LAST"])
    def test_nulls_triggers_kindC(self, make, apply, rule_ids, kinds, nulls_value):
        n = make(OrderByItem, nulls=nulls_value)
        r = apply(n)
        assert "pg_ch_orderby_nulls" in rule_ids(r)
        assert Kind.C in kinds(r)

    def test_no_nulls_does_not_trigger(self, make, apply, rule_ids):
        n = make(OrderByItem, nulls=None)
        r = apply(n)
        assert "pg_ch_orderby_nulls" not in rule_ids(r)

    def test_using_op_is_kindB_without_annotation(self, make, apply, kinds):
        n = make(OrderByItem, using_op="<")
        r = apply(n)
        # B без message → нет аннотации, но F-fallback заблокирован catch-all.
        assert kinds(r) == []


class TestLockingClause:
    def test_locking_clause_always_kindE(self, make, apply, rule_ids, kinds):
        n = make(LockingClause, mode="UPDATE")
        r = apply(n)
        assert "pg_ch_locking_clause" in rule_ids(r)
        assert Kind.E in kinds(r)

    def test_locking_clause_skip_locked_also_kindE(self, make, apply, kinds):
        n = make(LockingClause, mode="SHARE", wait="SKIP_LOCKED")
        r = apply(n)
        assert Kind.E in kinds(r)


class TestTableRefTablesample:
    def test_tablesample_rewrites_to_ch_sample(self, make, apply, kinds):
        arg = make(Literal, value=10, literal_kind="int", raw="10")
        n = make(TableRef, tablesample_method="BERNOULLI", tablesample_args=[arg])
        r = apply(n)
        # rewrite: tablesample_method очищен, ch_sample заполнен.
        assert r.tablesample_method is None
        assert r.tablesample_args == []
        assert r.ch_sample is not None
        assert r.ch_sample.ratio is not None
        # B-rule без message — без аннотации.
        assert kinds(r) == []

    def test_tablesample_repeatable_is_dropped(self, make, apply):
        arg = make(Literal, value=10, literal_kind="int", raw="10")
        seed = make(Literal, value=42, literal_kind="int", raw="42")
        n = make(
            TableRef,
            tablesample_method="SYSTEM",
            tablesample_args=[arg],
            tablesample_repeatable=seed,
        )
        r = apply(n)
        # REPEATABLE-указание в CH не имеет аналога — отбрасывается.
        assert r.tablesample_repeatable is None

    def test_no_tablesample_keeps_ch_sample_none(self, make, apply):
        n = make(TableRef)
        r = apply(n)
        assert r.ch_sample is None


class TestTableRefE:
    def test_only_triggers_kindE(self, make, apply, rule_ids, kinds):
        n = make(TableRef, only=True)
        r = apply(n)
        assert "pg_ch_tableref_only" in rule_ids(r)
        assert Kind.E in kinds(r)

    def test_descendants_star_triggers_kindE(self, make, apply, rule_ids):
        n = make(TableRef, descendants_star=True)
        r = apply(n)
        assert "pg_ch_tableref_descendants_star" in rule_ids(r)

    def test_column_aliases_triggers_kindE(self, make, apply, rule_ids):
        n = make(TableRef, column_aliases=[make(Identifier, name="c1")])
        r = apply(n)
        assert "pg_ch_tableref_column_aliases" in rule_ids(r)

    def test_plain_tableref_no_annotations(self, make, apply, kinds):
        n = make(TableRef)
        r = apply(n)
        assert kinds(r) == []


class TestSubqueryRef:
    def test_lateral_triggers_kindE(self, make, apply, rule_ids, kinds):
        n = make(SubqueryRef, lateral=True)
        r = apply(n)
        assert "pg_ch_subqueryref_lateral" in rule_ids(r)
        assert Kind.E in kinds(r)

    def test_non_lateral_only_kindA(self, make, apply, kinds):
        n = make(SubqueryRef, lateral=False)
        r = apply(n)
        assert kinds(r) == []


class TestTableFunctionRef:
    def test_lateral_triggers_kindE(self, make, apply, rule_ids, kinds):
        n = make(TableFunctionRef, lateral=True)
        r = apply(n)
        assert "pg_ch_tablefuncref_lateral" in rule_ids(r)
        assert Kind.E in kinds(r)

    def test_with_ordinality_triggers_kindE(self, make, apply, rule_ids):
        n = make(TableFunctionRef, with_ordinality=True)
        r = apply(n)
        assert "pg_ch_tablefuncref_with_ordinality" in rule_ids(r)

    def test_plain_only_kindA(self, make, apply, kinds):
        n = make(TableFunctionRef)
        r = apply(n)
        assert kinds(r) == []
