"""Правила pg→ch для агрегатных функций.

Источник правил: ``src/sql_translator/ast/rules/clickhouse/functions/aggregate_fns.py``.
"""
from __future__ import annotations

import pytest

from sql_translator.ast.metadata import Kind
from sql_translator.ast.nodes import (
    FunctionCall,
    Identifier,
    Literal,
    OrderByItem,
)


def _lit(make, value=1, kind="int"):
    return make(Literal, value=value, literal_kind=kind, raw=str(value))


def _ident(make, name):
    return make(Identifier, name=name)


def _fn(make, name, *args, **kwargs):
    ident = _ident(make, name)
    return make(FunctionCall, name=ident, args=list(args), **kwargs)


class TestBoolAnd:
    @pytest.mark.parametrize("fn_name", ["bool_and", "BOOL_AND"])
    def test_bool_and_rewrites_to_min_toUInt8(self, make, apply, fn_name):
        x = _ident(make, "x")
        n = _fn(make, fn_name, x)
        r = apply(n)
        # Результат: min(toUInt8(x)).
        assert isinstance(r, FunctionCall)
        assert r.name.name == "min"
        assert len(r.args) == 1
        inner = r.args[0]
        assert isinstance(inner, FunctionCall)
        assert inner.name.name == "toUInt8"

    def test_bool_and_no_annotation(self, make, apply, rule_ids):
        x = _ident(make, "x")
        n = _fn(make, "bool_and", x)
        r = apply(n)
        assert "pg_ch_fn_bool_and" not in rule_ids(r)


class TestBoolOrEvery:
    @pytest.mark.parametrize("fn_name", ["bool_or", "every", "BOOL_OR", "EVERY"])
    def test_bool_or_every_rewrites_to_max_toUInt8(self, make, apply, fn_name):
        x = _ident(make, "x")
        n = _fn(make, fn_name, x)
        r = apply(n)
        assert isinstance(r, FunctionCall)
        assert r.name.name == "max"
        inner = r.args[0]
        assert isinstance(inner, FunctionCall)
        assert inner.name.name == "toUInt8"


class TestBitFamily:
    @pytest.mark.parametrize("fn_name,new_name", [
        ("bit_and", "groupBitAnd"),
        ("bit_or",  "groupBitOr"),
        ("bit_xor", "groupBitXor"),
        ("BIT_AND", "groupBitAnd"),
        ("Bit_Xor", "groupBitXor"),
    ])
    def test_bit_family_renamed(self, make, apply, fn_name, new_name):
        x = _ident(make, "x")
        n = _fn(make, fn_name, x)
        r = apply(n)
        assert r.name.name == new_name


class TestStringAgg:
    def test_string_agg_rewrites_to_arrayStringConcat(self, make, apply):
        expr = _ident(make, "x")
        sep = _lit(make, ",", kind="str")
        n = _fn(make, "string_agg", expr, sep)
        r = apply(n)
        assert isinstance(r, FunctionCall)
        assert r.name.name == "arrayStringConcat"
        # Первый аргумент — groupArray(x).
        assert isinstance(r.args[0], FunctionCall)
        assert r.args[0].name.name == "groupArray"

    def test_string_agg_with_one_arg_fallback_rename(self, make, apply):
        # Меньше двух аргументов — fallback: только rename.
        n = _fn(make, "string_agg", _ident(make, "x"))
        r = apply(n)
        assert isinstance(r, FunctionCall)
        assert r.name.name == "arrayStringConcat"


class TestAvg:
    def test_avg_triggers_kindC(self, make, apply, rule_ids, kinds):
        n = _fn(make, "avg", _ident(make, "x"))
        r = apply(n)
        assert "pg_ch_fn_avg" in rule_ids(r)
        assert Kind.C in kinds(r)


class TestStddevFamily:
    @pytest.mark.parametrize("fn_name", [
        "stddev", "stddev_samp", "stddev_pop",
        "variance", "var_samp", "var_pop",
        "STDDEV", "Variance",
    ])
    def test_stddev_family_triggers_kindC(
        self, make, apply, rule_ids, kinds, fn_name
    ):
        n = _fn(make, fn_name, _ident(make, "x"))
        r = apply(n)
        assert "pg_ch_fn_stddev_family" in rule_ids(r)
        assert Kind.C in kinds(r)


class TestArrayAgg:
    def test_array_agg_renamed_to_groupArray(self, make, apply):
        n = _fn(make, "array_agg", _ident(make, "x"))
        r = apply(n)
        assert r.name.name == "groupArray"

    def test_array_agg_triggers_kindD_annotation(
        self, make, apply, rule_ids, kinds
    ):
        n = _fn(make, "array_agg", _ident(make, "x"))
        r = apply(n)
        assert "pg_ch_fn_array_agg" in rule_ids(r)
        assert Kind.D in kinds(r)


class TestPercentileCont:
    def test_percentile_cont_rewrites_to_quantile(self, make, apply):
        f = _lit(make, 1)
        x = _ident(make, "x")
        wg = make(OrderByItem, expression=x)
        n = _fn(make, "percentile_cont", f, within_group=[wg])
        r = apply(n)
        assert isinstance(r, FunctionCall)
        assert r.name.name == "quantile"
        assert r.parameters and r.parameters[0] is f
        assert r.args and r.args[0] is x
        # within_group очищен.
        assert r.within_group == []

    def test_percentile_cont_kindD_annotation(self, make, apply, rule_ids, kinds):
        f = _lit(make, 1)
        wg = make(OrderByItem, expression=_ident(make, "x"))
        n = _fn(make, "percentile_cont", f, within_group=[wg])
        r = apply(n)
        assert "pg_ch_fn_percentile_cont" in rule_ids(r)
        assert Kind.D in kinds(r)


class TestPercentileDisc:
    def test_percentile_disc_rewrites_to_quantileExact(self, make, apply):
        f = _lit(make, 1)
        x = _ident(make, "x")
        wg = make(OrderByItem, expression=x)
        n = _fn(make, "percentile_disc", f, within_group=[wg])
        r = apply(n)
        assert r.name.name == "quantileExact"
        assert r.parameters and r.parameters[0] is f
        assert r.args and r.args[0] is x


class TestMode:
    def test_mode_rewrites_to_arrayElement_topK(self, make, apply):
        x = _ident(make, "x")
        wg = make(OrderByItem, expression=x)
        n = _fn(make, "mode", within_group=[wg])
        r = apply(n)
        assert isinstance(r, FunctionCall)
        assert r.name.name == "arrayElement"
        # Первый аргумент — topK(1)(x).
        topk = r.args[0]
        assert isinstance(topk, FunctionCall)
        assert topk.name.name == "topK"
        assert topk.parameters

    def test_mode_kindD_annotation(self, make, apply, rule_ids, kinds):
        wg = make(OrderByItem, expression=_ident(make, "x"))
        n = _fn(make, "mode", within_group=[wg])
        r = apply(n)
        assert "pg_ch_fn_mode" in rule_ids(r)
        assert Kind.D in kinds(r)


class TestFilterClause:
    def test_known_agg_with_filter_renamed_with_if_suffix(self, make, apply):
        cond = _lit(make, True, kind="bool")
        n = _fn(make, "sum", _ident(make, "x"), filter_where=cond)
        r = apply(n)
        assert r.name.name == "sumIf"
        # Условие добавлено в args.
        assert r.args[-1] is cond
        # filter_where очищен.
        assert r.filter_where is None

    @pytest.mark.parametrize("fn_name,new_name", [
        ("sum", "sumIf"),
        ("count", "countIf"),
        ("avg", "avgIf"),
        ("min", "minIf"),
        ("max", "maxIf"),
        ("any", "anyIf"),
    ])
    def test_filter_renames_for_each_known_agg(
        self, make, apply, fn_name, new_name
    ):
        cond = _lit(make, True, kind="bool")
        n = _fn(make, fn_name, _ident(make, "x"), filter_where=cond)
        r = apply(n)
        assert r.name.name == new_name

    def test_unknown_agg_with_filter_keeps_name(self, make, apply):
        cond = _lit(make, True, kind="bool")
        n = _fn(make, "custom_agg", _ident(make, "x"), filter_where=cond)
        r = apply(n)
        # Имя не переименовано (нет в _FILTER_IF_MAP), но условие добавлено.
        assert r.name.name == "custom_agg"
        assert r.args[-1] is cond
        assert r.filter_where is None

    def test_filter_clause_triggers_kindD(self, make, apply, rule_ids, kinds):
        cond = _lit(make, True, kind="bool")
        n = _fn(make, "sum", _ident(make, "x"), filter_where=cond)
        r = apply(n)
        assert "pg_ch_fn_filter_clause" in rule_ids(r)
        assert Kind.D in kinds(r)

    def test_no_filter_no_filter_clause_rule(self, make, apply, rule_ids):
        n = _fn(make, "sum", _ident(make, "x"))
        r = apply(n)
        assert "pg_ch_fn_filter_clause" not in rule_ids(r)


class TestJsonAgg:
    @pytest.mark.parametrize("fn_name", [
        "json_agg", "jsonb_agg", "json_object_agg", "jsonb_object_agg",
        "JSON_AGG", "JSONB_OBJECT_AGG",
    ])
    def test_json_agg_family_triggers_kindE(
        self, make, apply, rule_ids, kinds, fn_name
    ):
        n = _fn(make, fn_name, _ident(make, "x"))
        r = apply(n)
        assert "pg_ch_fn_json_agg" in rule_ids(r)
        assert Kind.E in kinds(r)


class TestAggIsolation:
    def test_unknown_function_no_agg_rules(self, make, apply, rule_ids):
        n = _fn(make, "some_random_agg_fn")
        r = apply(n)
        ids = rule_ids(r)
        for forbidden in (
            "pg_ch_fn_bool_and", "pg_ch_fn_bool_or",
            "pg_ch_fn_bit_and", "pg_ch_fn_bit_or", "pg_ch_fn_bit_xor",
            "pg_ch_fn_string_agg", "pg_ch_fn_avg",
            "pg_ch_fn_stddev_family", "pg_ch_fn_array_agg",
            "pg_ch_fn_percentile_cont", "pg_ch_fn_percentile_disc",
            "pg_ch_fn_mode", "pg_ch_fn_filter_clause", "pg_ch_fn_json_agg",
        ):
            assert forbidden not in ids
