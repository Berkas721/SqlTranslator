"""Правила pg→ch для Cast.

Источник правил: ``src/sql_translator/ast/rules/clickhouse/expressions/cast.py``.
"""
from __future__ import annotations

import pytest

from sql_translator.ast.metadata import Kind
from sql_translator.ast.nodes import Cast, Identifier, Literal, TypeRef


def _lit(make, value=1):
    return make(Literal, value=value, literal_kind="int", raw=str(value))


def _type(make, name="INT", **kwargs):
    return make(TypeRef, name=name, **kwargs)


class TestCastPostfixRewrite:
    def test_postfix_style_rewrites_to_cast(self, make, apply):
        n = make(
            Cast,
            expression=_lit(make),
            target_type=_type(make, "INT"),
            style="postfix",
        )
        r = apply(n)
        # rewrite: стиль переключён на 'cast'.
        assert r.style == "cast"

    def test_cast_style_is_left_alone(self, make, apply):
        n = make(
            Cast,
            expression=_lit(make),
            target_type=_type(make, "INT"),
            style="cast",
        )
        r = apply(n)
        assert r.style == "cast"

    def test_postfix_does_not_emit_B_annotation(
        self, make, apply, rule_ids
    ):
        # Kind.B без message → нет аннотации.
        n = make(
            Cast,
            expression=_lit(make),
            target_type=_type(make, "INT"),
            style="postfix",
        )
        r = apply(n)
        assert "pg_ch_cast_postfix" not in rule_ids(r)


class TestCastOverflow:
    def test_every_cast_gets_kindC_overflow_annotation(
        self, make, apply, rule_ids, kinds
    ):
        n = make(
            Cast,
            expression=_lit(make),
            target_type=_type(make, "INT"),
        )
        r = apply(n)
        assert "pg_ch_cast_overflow" in rule_ids(r)
        assert Kind.C in kinds(r)

    def test_overflow_annotation_mentions_truncation(
        self, make, apply
    ):
        n = make(
            Cast,
            expression=_lit(make),
            target_type=_type(make, "UInt8"),
        )
        r = apply(n)
        ann = next(a for a in r.annotations if a.rule_id == "pg_ch_cast_overflow")
        assert "UInt8" in (ann.message or "") or "переполнен" in (ann.message or "")


class TestCastTimezone:
    def test_target_type_with_time_zone_triggers_kindD(
        self, make, apply, rule_ids, kinds
    ):
        n = make(
            Cast,
            expression=_lit(make),
            target_type=_type(make, "TIMESTAMP", time_zone="UTC"),
        )
        r = apply(n)
        assert "pg_ch_cast_timezone" in rule_ids(r)
        assert Kind.D in kinds(r)

    def test_target_type_without_time_zone_does_not_trigger(
        self, make, apply, rule_ids
    ):
        n = make(
            Cast,
            expression=_lit(make),
            target_type=_type(make, "TIMESTAMP", time_zone=None),
        )
        r = apply(n)
        assert "pg_ch_cast_timezone" not in rule_ids(r)


class TestCastRegTypes:
    @pytest.mark.parametrize("type_name", [
        "regclass", "regproc", "regprocedure", "regoper", "regoperator",
        "regtype", "regconfig", "regdictionary", "regnamespace", "regrole",
    ])
    def test_lowercase_reg_types_trigger_kindE(
        self, make, apply, rule_ids, kinds, type_name
    ):
        n = make(
            Cast,
            expression=_lit(make),
            target_type=_type(make, type_name),
        )
        r = apply(n)
        assert "pg_ch_cast_reg_type" in rule_ids(r)
        assert Kind.E in kinds(r)

    @pytest.mark.parametrize("type_name", [
        "REGCLASS", "RegProc", "regCLASS",
    ])
    def test_reg_types_case_insensitive(
        self, make, apply, rule_ids, type_name
    ):
        n = make(
            Cast,
            expression=_lit(make),
            target_type=_type(make, type_name),
        )
        r = apply(n)
        assert "pg_ch_cast_reg_type" in rule_ids(r)

    @pytest.mark.parametrize("type_name", [
        "INT", "TEXT", "JSON", "regular", "oid",
    ])
    def test_non_reg_types_do_not_trigger(
        self, make, apply, rule_ids, type_name
    ):
        n = make(
            Cast,
            expression=_lit(make),
            target_type=_type(make, type_name),
        )
        r = apply(n)
        assert "pg_ch_cast_reg_type" not in rule_ids(r)


class TestCastCombined:
    def test_postfix_to_timestamp_with_zone_yields_B_rewrite_and_D(
        self, make, apply, rule_ids
    ):
        n = make(
            Cast,
            expression=_lit(make),
            target_type=_type(make, "TIMESTAMP", time_zone="UTC"),
            style="postfix",
        )
        r = apply(n)
        assert r.style == "cast"
        ids = rule_ids(r)
        assert "pg_ch_cast_overflow" in ids
        assert "pg_ch_cast_timezone" in ids

    def test_cast_to_regclass_yields_C_and_E(self, make, apply, kinds):
        n = make(
            Cast,
            expression=_lit(make),
            target_type=_type(make, "regclass"),
        )
        r = apply(n)
        ks = kinds(n)
        assert Kind.C in ks
        assert Kind.E in ks
