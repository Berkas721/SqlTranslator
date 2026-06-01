"""Правила pg→ch для Literal и ArrayConstructor.

Источник правил: ``src/sql_translator/ast/rules/clickhouse/literals.py``.
"""
from __future__ import annotations

import pytest

from sql_translator.ast.metadata import Kind
from sql_translator.ast.nodes import ArrayConstructor, Literal


def _lit(make, value=1, literal_kind="int", raw=None, quote_style=None):
    return make(Literal,
                value=value,
                literal_kind=literal_kind,
                raw=raw if raw is not None else (str(value) if value is not None else None),
                quote_style=quote_style)


class TestPlainLiteralsBlockFallback:
    @pytest.mark.parametrize("literal_kind,value,raw", [
        ("int", 42, "42"),
        ("float", 1.5, "1.5"),
        ("string", "abc", None),
        ("null", None, None),
        ("date", "2024-01-01", None),
        ("timestamp", "2024-01-01 00:00:00", None),
        ("uuid", "00000000-0000-0000-0000-000000000000", None),
        ("bit", "0101", None),
        ("hex", "DEADBEEF", None),
    ])
    def test_plain_literal_no_fallback(
        self, make, apply, rule_ids, literal_kind, value, raw
    ):
        n = _lit(make, value=value, literal_kind=literal_kind, raw=raw)
        r = apply(n)
        assert "pg_ch.fallback" not in rule_ids(r)

    def test_plain_int_no_kind_C_or_D(self, make, apply, kinds):
        n = _lit(make, 42, "int", "42")
        r = apply(n)
        for k in (Kind.C, Kind.D, Kind.E, Kind.F):
            assert k not in kinds(r)

    def test_plain_string_single_quote_no_E_rewrite(self, make, apply):
        n = _lit(make, "abc", "string", quote_style="single")
        r = apply(n)
        # quote_style не меняется.
        assert r.quote_style == "single"


class TestNumericUnderscore:
    def test_int_with_underscore_stripped(self, make, apply):
        n = _lit(make, 42000, "int", raw="42_000")
        r = apply(n)
        assert r.raw == "42000"

    def test_float_with_underscore_stripped(self, make, apply):
        n = _lit(make, 1500.5, "float", raw="1_500.5")
        r = apply(n)
        assert r.raw == "1500.5"

    def test_underscore_no_annotation(self, make, apply, rule_ids):
        n = _lit(make, 42000, "int", raw="42_000")
        r = apply(n)
        # Kind.B без message → нет аннотации.
        assert "pg_ch_lit_numeric_underscore" not in rule_ids(r)

    def test_int_without_underscore_unchanged(self, make, apply):
        n = _lit(make, 42, "int", raw="42")
        r = apply(n)
        assert r.raw == "42"


class TestStringQuoteStyle:
    @pytest.mark.parametrize("style", ["E", "dollar", "U&"])
    def test_non_single_quote_normalized_to_single(self, make, apply, style):
        n = _lit(make, "abc", "string", quote_style=style)
        r = apply(n)
        assert r.quote_style == "single"

    @pytest.mark.parametrize("style,rule_id", [
        ("E", "pg_ch_lit_estring"),
        ("dollar", "pg_ch_lit_dollar"),
        ("U&", "pg_ch_lit_unicode"),
    ])
    def test_quote_rule_no_annotation(
        self, make, apply, rule_ids, style, rule_id
    ):
        # Все три правила — Kind.B без message.
        n = _lit(make, "abc", "string", quote_style=style)
        r = apply(n)
        assert rule_id not in rule_ids(r)


class TestArrayConstructorSyntax:
    @pytest.mark.parametrize("syntax", ["curly_literal", "array_kw"])
    def test_array_syntax_normalized_to_bracket(self, make, apply, syntax):
        n = make(ArrayConstructor, syntax=syntax)
        r = apply(n)
        assert r.syntax == "bracket"

    def test_array_bracket_kept(self, make, apply):
        n = make(ArrayConstructor, syntax="bracket")
        r = apply(n)
        assert r.syntax == "bracket"

    def test_array_no_fallback(self, make, apply, rule_ids):
        n = make(ArrayConstructor, syntax="bracket")
        r = apply(n)
        assert "pg_ch.fallback" not in rule_ids(r)


class TestBoolLiteral:
    def test_true_raw_normalized(self, make, apply):
        n = _lit(make, True, "bool", raw="TRUE")
        r = apply(n)
        assert r.raw == "true"

    def test_false_raw_normalized(self, make, apply):
        n = _lit(make, False, "bool", raw="FALSE")
        r = apply(n)
        assert r.raw == "false"

    def test_bool_triggers_kindC(self, make, apply, rule_ids, kinds):
        n = _lit(make, True, "bool", raw="TRUE")
        r = apply(n)
        assert "pg_ch_lit_bool" in rule_ids(r)
        assert Kind.C in kinds(r)

    def test_bool_message_mentions_three_valued(self, make, apply):
        n = _lit(make, True, "bool", raw="TRUE")
        r = apply(n)
        ann = next(a for a in r.annotations if a.rule_id == "pg_ch_lit_bool")
        msg = (ann.message or "").lower()
        assert "boolean" in msg or "трёхзначн" in msg or "nullable" in msg


class TestIntervalLiteral:
    def test_interval_triggers_kindD(self, make, apply, rule_ids, kinds):
        n = _lit(make, "1 year 2 months", "interval")
        r = apply(n)
        assert "pg_ch_lit_interval" in rule_ids(r)
        assert Kind.D in kinds(r)

    def test_interval_message_mentions_composite_units(self, make, apply):
        n = _lit(make, "1 year 2 months", "interval")
        r = apply(n)
        ann = next(a for a in r.annotations if a.rule_id == "pg_ch_lit_interval")
        msg = (ann.message or "").lower()
        assert "interval" in msg or "единиц" in msg

    def test_non_interval_no_rule(self, make, apply, rule_ids):
        n = _lit(make, 1, "int", "1")
        r = apply(n)
        assert "pg_ch_lit_interval" not in rule_ids(r)


class TestLiteralsIsolation:
    def test_plain_int_no_bool_rewrite(self, make, apply):
        n = _lit(make, 1, "int", "1")
        r = apply(n)
        assert r.raw == "1"

    def test_string_no_numeric_underscore_rule(self, make, apply, rule_ids):
        n = _lit(make, "a_b_c", "string", quote_style="single")
        r = apply(n)
        assert "pg_ch_lit_numeric_underscore" not in rule_ids(r)

    def test_unknown_literal_kind_gets_fallback(self, make, apply, rule_ids):
        # Никакое A/B/C/D-правило не подходит → срабатывает F-fallback.
        n = _lit(make, "x", "unknown_kind")
        r = apply(n)
        assert "pg_ch.fallback" in rule_ids(r)
