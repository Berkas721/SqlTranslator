"""Правила pg→ch для оконных функций и фреймов.

Источник правил: ``src/sql_translator/ast/rules/clickhouse/functions/window_fns.py``.
"""
from __future__ import annotations

import pytest

from sql_translator.ast.metadata import Kind
from sql_translator.ast.nodes import (
    Cast,
    FrameBound,
    FrameSpec,
    FunctionCall,
    Identifier,
    Literal,
    TypeRef,
    WindowSpec,
)


def _lit(make, value=1, kind="int"):
    return make(Literal, value=value, literal_kind=kind, raw=str(value))


def _ident(make, name):
    return make(Identifier, name=name)


def _fn(make, name, *args, **kwargs):
    ident = _ident(make, name)
    return make(FunctionCall, name=ident, args=list(args), **kwargs)


def _bound(make, kind="UNBOUNDED_PRECEDING", offset=None):
    return make(FrameBound, kind=kind, offset=offset)


def _frame(make, unit="ROWS", start=None, end=None, exclude=None):
    if start is None:
        start = _bound(make, "UNBOUNDED_PRECEDING")
    return make(FrameSpec, unit=unit, start=start, end=end, exclude=exclude)


class TestFrameBase:
    def test_plain_rows_frame_no_E_or_D(self, make, apply, kinds):
        n = _frame(make, unit="ROWS")
        r = apply(n)
        ks = kinds(r)
        # Базовый A без message — без аннотации.
        assert Kind.E not in ks
        assert Kind.D not in ks

    def test_plain_rows_frame_no_fallback(self, make, apply, rule_ids):
        n = _frame(make, unit="ROWS")
        r = apply(n)
        # Catch-all A блокирует F-fallback.
        assert "pg_ch.fallback" not in rule_ids(r)


class TestFrameGroups:
    def test_groups_frame_triggers_kindE(self, make, apply, rule_ids, kinds):
        n = _frame(make, unit="GROUPS")
        r = apply(n)
        assert "pg_ch_frame_groups" in rule_ids(r)
        assert Kind.E in kinds(r)

    def test_rows_frame_no_groups_rule(self, make, apply, rule_ids):
        n = _frame(make, unit="ROWS")
        r = apply(n)
        assert "pg_ch_frame_groups" not in rule_ids(r)


class TestFrameExclude:
    @pytest.mark.parametrize("exclude_value", [
        "CURRENT_ROW", "GROUP", "TIES", "NO_OTHERS",
    ])
    def test_exclude_modifier_triggers_kindE(
        self, make, apply, rule_ids, kinds, exclude_value
    ):
        n = _frame(make, unit="ROWS", exclude=exclude_value)
        r = apply(n)
        assert "pg_ch_frame_exclude" in rule_ids(r)
        assert Kind.E in kinds(r)

    def test_no_exclude_no_rule(self, make, apply, rule_ids):
        n = _frame(make, unit="ROWS", exclude=None)
        r = apply(n)
        assert "pg_ch_frame_exclude" not in rule_ids(r)


class TestFrameRangeInterval:
    def test_range_with_interval_literal_in_start_triggers_kindD(
        self, make, apply, rule_ids, kinds
    ):
        interval = _lit(make, "1 day", kind="interval")
        start = _bound(make, "N_PRECEDING", offset=interval)
        n = _frame(make, unit="RANGE", start=start)
        r = apply(n)
        assert "pg_ch_frame_range_interval" in rule_ids(r)
        assert Kind.D in kinds(r)

    def test_range_with_interval_literal_in_end_triggers_kindD(
        self, make, apply, rule_ids
    ):
        interval = _lit(make, "1 day", kind="interval")
        end = _bound(make, "N_FOLLOWING", offset=interval)
        n = _frame(make, unit="RANGE",
                   start=_bound(make, "UNBOUNDED_PRECEDING"),
                   end=end)
        r = apply(n)
        assert "pg_ch_frame_range_interval" in rule_ids(r)

    def test_range_with_cast_offset_triggers_kindD(
        self, make, apply, rule_ids
    ):
        cast = make(
            Cast,
            expression=_lit(make, 1),
            target_type=make(TypeRef, name="INTERVAL"),
        )
        start = _bound(make, "N_PRECEDING", offset=cast)
        n = _frame(make, unit="RANGE", start=start)
        r = apply(n)
        assert "pg_ch_frame_range_interval" in rule_ids(r)

    def test_range_with_integer_offset_does_not_trigger(
        self, make, apply, rule_ids
    ):
        start = _bound(make, "N_PRECEDING", offset=_lit(make, 5))
        n = _frame(make, unit="RANGE", start=start)
        r = apply(n)
        assert "pg_ch_frame_range_interval" not in rule_ids(r)

    def test_rows_with_interval_does_not_trigger(self, make, apply, rule_ids):
        interval = _lit(make, "1 day", kind="interval")
        start = _bound(make, "N_PRECEDING", offset=interval)
        n = _frame(make, unit="ROWS", start=start)
        r = apply(n)
        assert "pg_ch_frame_range_interval" not in rule_ids(r)


class TestNtile:
    @pytest.mark.parametrize("fn_name", ["ntile", "NTILE", "NTile"])
    def test_ntile_triggers_kindC(
        self, make, apply, rule_ids, kinds, fn_name
    ):
        n = _fn(make, fn_name, _lit(make, 4))
        r = apply(n)
        assert "pg_ch_fn_ntile" in rule_ids(r)
        assert Kind.C in kinds(r)

    def test_other_window_fn_no_ntile_rule(self, make, apply, rule_ids):
        n = _fn(make, "row_number")
        r = apply(n)
        assert "pg_ch_fn_ntile" not in rule_ids(r)


class TestWindowFilter:
    def test_filter_plus_over_triggers_kindE(
        self, make, apply, rule_ids, kinds
    ):
        cond = _lit(make, True, kind="bool")
        win = make(WindowSpec)
        n = _fn(make, "sum", _ident(make, "x"),
                filter_where=cond, over=win)
        r = apply(n)
        assert "pg_ch_fn_window_filter" in rule_ids(r)
        assert Kind.E in kinds(r)

    def test_filter_plus_over_does_not_trigger_agg_filter_rule(
        self, make, apply, rule_ids
    ):
        # ``pg_ch_fn_filter_clause`` требует ``over is None`` — не должна сработать.
        cond = _lit(make, True, kind="bool")
        win = make(WindowSpec)
        n = _fn(make, "sum", _ident(make, "x"),
                filter_where=cond, over=win)
        r = apply(n)
        assert "pg_ch_fn_filter_clause" not in rule_ids(r)

    def test_over_without_filter_no_window_filter_rule(
        self, make, apply, rule_ids
    ):
        win = make(WindowSpec)
        n = _fn(make, "sum", _ident(make, "x"), over=win)
        r = apply(n)
        assert "pg_ch_fn_window_filter" not in rule_ids(r)

    def test_filter_without_over_no_window_filter_rule(
        self, make, apply, rule_ids
    ):
        cond = _lit(make, True, kind="bool")
        n = _fn(make, "sum", _ident(make, "x"), filter_where=cond)
        r = apply(n)
        assert "pg_ch_fn_window_filter" not in rule_ids(r)


class TestWindowCombined:
    def test_groups_with_exclude_yields_two_E_annotations(
        self, make, apply, rule_ids, kinds
    ):
        n = _frame(make, unit="GROUPS", exclude="CURRENT_ROW")
        r = apply(n)
        ids = rule_ids(r)
        assert "pg_ch_frame_groups" in ids
        assert "pg_ch_frame_exclude" in ids
        assert kinds(r).count(Kind.E) >= 2

    def test_range_interval_with_exclude(self, make, apply, rule_ids):
        interval = _lit(make, "1 day", kind="interval")
        start = _bound(make, "N_PRECEDING", offset=interval)
        n = _frame(make, unit="RANGE", start=start, exclude="TIES")
        r = apply(n)
        ids = rule_ids(r)
        assert "pg_ch_frame_range_interval" in ids
        assert "pg_ch_frame_exclude" in ids
