"""Кейсы для вспомогательных clause-узлов:
OrderByItem, WithFillSpec, FrameBound, FrameSpec, WindowSpec, WindowDef,
DistinctClause, SetOpClause, SampleClause, SettingAssignment, SelectTarget,
TableRef, TableFunctionRef, GroupByClause."""
from __future__ import annotations

import pytest

from sql_translator.ast.nodes import (
    DistinctClause,
    FrameBound,
    FrameSpec,
    FunctionCall,
    GroupByClause,
    Identifier,
    Literal,
    OrderByItem,
    SampleClause,
    SelectTarget,
    SetOpClause,
    SettingAssignment,
    TableFunctionRef,
    TableRef,
    WindowDef,
    WindowSpec,
    WithFillSpec,
)


def _ident(make, name, quoted=False):
    return make(Identifier, name=name, quoted=quoted)


def _lit(make, value=1, kind="int", raw=None):
    return make(Literal, value=value, literal_kind=kind,
                raw=raw if raw is not None else str(value))


CASES: list = [
    # ── OrderByItem ──────────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(OrderByItem, expression=_ident(m, "x")),
        "x",
        id="orderbyitem-plain",
    ),
    pytest.param(
        lambda m: m(OrderByItem, expression=_ident(m, "x"), direction="DESC"),
        "x DESC",
        id="orderbyitem-desc",
    ),
    pytest.param(
        lambda m: m(OrderByItem, expression=_ident(m, "x"),
                    direction="ASC", nulls="FIRST"),
        "x ASC NULLS FIRST",
        id="orderbyitem-asc-nulls-first",
    ),
    pytest.param(
        lambda m: m(OrderByItem, expression=_ident(m, "x"), collate="utf8"),
        "x COLLATE 'utf8'",
        id="orderbyitem-collate",
    ),
    pytest.param(
        lambda m: m(OrderByItem, expression=_ident(m, "x"),
                    with_fill=m(WithFillSpec,
                                from_value=_lit(m, 1),
                                to_value=_lit(m, 10),
                                step=_lit(m, 1))),
        "x WITH FILL FROM 1 TO 10 STEP 1",
        id="orderbyitem-with-fill-full",
    ),

    # ── WithFillSpec (standalone dispatch) ───────────────────────────────────
    pytest.param(
        lambda m: m(WithFillSpec),
        "WITH FILL",
        id="withfill-empty",
    ),
    pytest.param(
        lambda m: m(WithFillSpec, from_value=_lit(m, 1)),
        "WITH FILL FROM 1",
        id="withfill-from-only",
    ),

    # ── FrameBound ───────────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(FrameBound, kind="UNBOUNDED_PRECEDING"),
        "UNBOUNDED PRECEDING",
        id="framebound-unbounded-preceding",
    ),
    pytest.param(
        lambda m: m(FrameBound, kind="UNBOUNDED_FOLLOWING"),
        "UNBOUNDED FOLLOWING",
        id="framebound-unbounded-following",
    ),
    pytest.param(
        lambda m: m(FrameBound, kind="CURRENT_ROW"),
        "CURRENT ROW",
        id="framebound-current-row",
    ),
    pytest.param(
        lambda m: m(FrameBound, kind="N_PRECEDING", offset=_lit(m, 3)),
        "3 PRECEDING",
        id="framebound-n-preceding",
    ),
    pytest.param(
        lambda m: m(FrameBound, kind="N_FOLLOWING", offset=_lit(m, 5)),
        "5 FOLLOWING",
        id="framebound-n-following",
    ),

    # ── FrameSpec ────────────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(FrameSpec, unit="ROWS",
                    start=m(FrameBound, kind="CURRENT_ROW")),
        "ROWS CURRENT ROW",
        id="framespec-rows-current-row",
    ),
    pytest.param(
        lambda m: m(FrameSpec, unit="RANGE",
                    start=m(FrameBound, kind="UNBOUNDED_PRECEDING"),
                    end=m(FrameBound, kind="CURRENT_ROW")),
        "RANGE BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW",
        id="framespec-range-between",
    ),

    # ── WindowSpec ───────────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(WindowSpec),
        "()",
        id="windowspec-empty",
    ),
    pytest.param(
        lambda m: m(WindowSpec, partition_by=[_ident(m, "a"), _ident(m, "b")]),
        "(PARTITION BY a, b)",
        id="windowspec-partition-by",
    ),
    pytest.param(
        lambda m: m(WindowSpec,
                    partition_by=[_ident(m, "a")],
                    order_by=[m(OrderByItem, expression=_ident(m, "b"),
                                direction="DESC")]),
        "(PARTITION BY a ORDER BY b DESC)",
        id="windowspec-partition-and-order",
    ),

    # ── WindowDef ────────────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(WindowDef, name=_ident(m, "w"),
                    spec=m(WindowSpec, partition_by=[_ident(m, "x")])),
        "w AS (PARTITION BY x)",
        id="windowdef-named",
    ),

    # ── DistinctClause ───────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(DistinctClause, kind="distinct"),
        "DISTINCT",
        id="distinct-clause",
    ),
    pytest.param(
        lambda m: m(DistinctClause, kind="distinct_on",
                    on=[_ident(m, "a"), _ident(m, "b")]),
        "DISTINCT ON (a, b)",
        id="distinct-on-clause",
    ),
    pytest.param(
        lambda m: m(DistinctClause, kind="all"),
        "",
        id="distinct-all-empty",
    ),

    # ── SetOpClause ──────────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(SetOpClause, op="UNION"),
        "UNION",
        id="setop-union",
    ),
    pytest.param(
        lambda m: m(SetOpClause, op="UNION", quantifier="ALL"),
        "UNION ALL",
        id="setop-union-all",
    ),
    pytest.param(
        lambda m: m(SetOpClause, op="INTERSECT", quantifier="DISTINCT"),
        "INTERSECT DISTINCT",
        id="setop-intersect-distinct",
    ),

    # ── SampleClause ─────────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(SampleClause, ratio=_lit(m, 0.1, "float", "0.1")),
        "0.1",
        id="sample-ratio-only",
    ),
    pytest.param(
        lambda m: m(SampleClause, ratio=_lit(m, 0.1, "float", "0.1"),
                    offset=_lit(m, 0.05, "float", "0.05")),
        "0.1 OFFSET 0.05",
        id="sample-ratio-offset",
    ),

    # ── SettingAssignment ────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(SettingAssignment, name="max_threads", value=_lit(m, 8)),
        "max_threads = 8",
        id="setting-assignment",
    ),

    # ── SelectTarget ─────────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(SelectTarget, expression=_ident(m, "x")),
        "x",
        id="selecttarget-no-alias",
    ),
    pytest.param(
        lambda m: m(SelectTarget, expression=_ident(m, "x"),
                    alias=_ident(m, "y")),
        "x AS y",
        id="selecttarget-with-alias",
    ),

    # ── TableRef ─────────────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(TableRef, name=_ident(m, "t")),
        "t",
        id="tableref-name-only",
    ),
    pytest.param(
        lambda m: m(TableRef, schema=_ident(m, "s"), name=_ident(m, "t")),
        "s.t",
        id="tableref-schema-name",
    ),
    pytest.param(
        lambda m: m(TableRef, database=_ident(m, "d"),
                    schema=_ident(m, "s"), name=_ident(m, "t")),
        "d.s.t",
        id="tableref-db-schema-name",
    ),
    pytest.param(
        lambda m: m(TableRef, name=_ident(m, "t"), alias=_ident(m, "a")),
        "t AS a",
        id="tableref-with-alias",
    ),
    pytest.param(
        lambda m: m(TableRef, name=_ident(m, "t"),
                    ch_sample=m(SampleClause,
                                ratio=_lit(m, 0.1, "float", "0.1"))),
        "t SAMPLE 0.1",
        id="tableref-ch-sample",
    ),

    # ── TableFunctionRef ─────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(TableFunctionRef,
                    call=m(FunctionCall, name=_ident(m, "numbers"),
                           args=[_lit(m, 10)])),
        "numbers(10)",
        id="tablefuncref",
    ),
    pytest.param(
        lambda m: m(TableFunctionRef,
                    call=m(FunctionCall, name=_ident(m, "numbers"),
                           args=[_lit(m, 10)]),
                    alias=_ident(m, "n")),
        "numbers(10) AS n",
        id="tablefuncref-alias",
    ),

    # ── GroupByClause ────────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(GroupByClause, kind="ordinary",
                    items=[_ident(m, "a"), _ident(m, "b")]),
        "a, b",
        id="groupby-ordinary",
    ),
    pytest.param(
        lambda m: m(GroupByClause, kind="rollup",
                    items=[_ident(m, "a"), _ident(m, "b")]),
        "ROLLUP (a, b)",
        id="groupby-rollup",
    ),
    pytest.param(
        lambda m: m(GroupByClause, kind="cube", items=[_ident(m, "a")]),
        "CUBE (a)",
        id="groupby-cube",
    ),
    pytest.param(
        lambda m: m(GroupByClause, kind="grouping_sets",
                    items=[_ident(m, "a"), _ident(m, "b")]),
        "GROUPING SETS (a, b)",
        id="groupby-grouping-sets",
    ),
]
