"""Тесты эмиссии SelectStmt (многоклаузная конструкция с переносами/отступами)."""
from __future__ import annotations

from sql_translator.ast.nodes import (
    BinaryOp,
    CommonTableExpr,
    DistinctClause,
    GroupByClause,
    Identifier,
    Literal,
    OrderByItem,
    SampleClause,
    SelectStmt,
    SelectTarget,
    SetOpClause,
    SettingAssignment,
    SetTransactionStmt,
    StarExpr,
    TableRef,
    WindowDef,
    WindowSpec,
    WithClause,
)


def _ident(make, name):
    return make(Identifier, name=name)


def _lit(make, value, kind="int", raw=None):
    return make(Literal, value=value, literal_kind=kind,
                raw=raw if raw is not None else str(value))


def _star_target(make):
    return make(SelectTarget, expression=make(StarExpr))


def test_select_star_from_table(make, emit):
    n = make(SelectStmt,
             targets=[_star_target(make)],
             from_items=[make(TableRef, name=_ident(make, "t"))])
    assert emit(n) == "SELECT\n    *\nFROM t"


def test_select_no_targets_emits_star(make, emit):
    n = make(SelectStmt,
             from_items=[make(TableRef, name=_ident(make, "t"))])
    assert emit(n) == "SELECT *\nFROM t"


def test_select_distinct(make, emit):
    n = make(SelectStmt,
             distinct=make(DistinctClause, kind="distinct"),
             targets=[make(SelectTarget, expression=_ident(make, "x"))],
             from_items=[make(TableRef, name=_ident(make, "t"))])
    assert emit(n) == "SELECT DISTINCT\n    x\nFROM t"


def test_select_distinct_on(make, emit):
    n = make(SelectStmt,
             distinct=make(DistinctClause, kind="distinct_on",
                           on=[_ident(make, "a")]),
             targets=[make(SelectTarget, expression=_ident(make, "x"))],
             from_items=[make(TableRef, name=_ident(make, "t"))])
    assert emit(n) == "SELECT DISTINCT ON (a)\n    x\nFROM t"


def test_select_multiple_targets_comma_newline(make, emit):
    n = make(SelectStmt, targets=[
        make(SelectTarget, expression=_ident(make, "a")),
        make(SelectTarget, expression=_ident(make, "b")),
        make(SelectTarget, expression=_ident(make, "c")),
    ])
    assert emit(n) == "SELECT\n    a,\n    b,\n    c"


def test_select_where(make, emit):
    n = make(SelectStmt,
             targets=[_star_target(make)],
             from_items=[make(TableRef, name=_ident(make, "t"))],
             where=make(BinaryOp, op=">", left=_ident(make, "x"),
                        right=_lit(make, 0)))
    assert emit(n) == "SELECT\n    *\nFROM t\nWHERE x > 0"


def test_select_group_by_having(make, emit):
    n = make(SelectStmt,
             targets=[make(SelectTarget, expression=_ident(make, "g"))],
             from_items=[make(TableRef, name=_ident(make, "t"))],
             group_by=make(GroupByClause, kind="ordinary",
                           items=[_ident(make, "g")]),
             having=make(BinaryOp, op=">", left=_ident(make, "g"),
                         right=_lit(make, 5)))
    assert emit(n) == ("SELECT\n    g\nFROM t\nGROUP BY g\nHAVING g > 5")


def test_select_order_by_limit_offset(make, emit):
    n = make(SelectStmt,
             targets=[_star_target(make)],
             from_items=[make(TableRef, name=_ident(make, "t"))],
             order_by=[make(OrderByItem, expression=_ident(make, "x"),
                            direction="ASC")],
             limit=_lit(make, 10),
             offset=_lit(make, 5))
    assert emit(n) == (
        "SELECT\n    *\nFROM t\n"
        "ORDER BY x ASC\nLIMIT 10\nOFFSET 5"
    )


def test_select_limit_with_ties(make, emit):
    n = make(SelectStmt,
             targets=[_star_target(make)],
             from_items=[make(TableRef, name=_ident(make, "t"))],
             limit=_lit(make, 10),
             limit_with_ties=True)
    assert emit(n) == "SELECT\n    *\nFROM t\nLIMIT 10 WITH TIES"


def test_select_sample(make, emit):
    n = make(SelectStmt,
             targets=[_star_target(make)],
             from_items=[make(TableRef, name=_ident(make, "t"))],
             sample=make(SampleClause,
                         ratio=_lit(make, 0.1, "float", "0.1")))
    assert emit(n) == "SELECT\n    *\nFROM t\nSAMPLE 0.1"


def test_select_settings(make, emit):
    n = make(SelectStmt,
             targets=[_star_target(make)],
             from_items=[make(TableRef, name=_ident(make, "t"))],
             settings=[
                 make(SettingAssignment, name="max_threads", value=_lit(make, 8)),
                 make(SettingAssignment, name="readonly", value=_lit(make, 1)),
             ])
    assert emit(n) == (
        "SELECT\n    *\nFROM t\n"
        "SETTINGS max_threads = 8, readonly = 1"
    )


def test_select_union_all(make, emit):
    right = make(SelectStmt,
                 targets=[_star_target(make)],
                 from_items=[make(TableRef, name=_ident(make, "u"))])
    n = make(SelectStmt,
             targets=[_star_target(make)],
             from_items=[make(TableRef, name=_ident(make, "t"))],
             set_op=make(SetOpClause, op="UNION", quantifier="ALL",
                         right=right))
    assert emit(n) == (
        "SELECT\n    *\nFROM t\n"
        "UNION ALL\n"
        "SELECT\n    *\nFROM u"
    )


def test_select_multiple_from_items_comma_newline(make, emit):
    n = make(SelectStmt,
             targets=[_star_target(make)],
             from_items=[
                 make(TableRef, name=_ident(make, "a")),
                 make(TableRef, name=_ident(make, "b")),
             ])
    assert emit(n) == "SELECT\n    *\nFROM a,\n     b"


def test_select_window_clause(make, emit):
    n = make(SelectStmt,
             targets=[_star_target(make)],
             from_items=[make(TableRef, name=_ident(make, "t"))],
             windows=[make(WindowDef, name=_ident(make, "w"),
                           spec=make(WindowSpec,
                                     partition_by=[_ident(make, "x")]))])
    assert emit(n) == (
        "SELECT\n    *\nFROM t\nWINDOW w AS (PARTITION BY x)"
    )


def test_select_with_cte(make, emit):
    inner = make(SelectStmt,
                 targets=[_star_target(make)],
                 from_items=[make(TableRef, name=_ident(make, "base"))])
    cte = make(CommonTableExpr, name=_ident(make, "c"), query=inner)
    n = make(SelectStmt,
             with_clause=make(WithClause, ctes=[cte]),
             targets=[_star_target(make)],
             from_items=[make(TableRef, name=_ident(make, "c"))])
    out = emit(n)
    assert out.startswith("WITH c AS (\n")
    assert "SELECT\n        *\n    FROM base" in out
    assert out.endswith("SELECT\n    *\nFROM c")
