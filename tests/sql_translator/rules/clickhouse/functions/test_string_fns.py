"""Правила pg→ch для строковых функций.

Источник правил: ``src/sql_translator/ast/rules/clickhouse/functions/string_fns.py``.
"""
from __future__ import annotations

import pytest

from sql_translator.ast.metadata import Kind
from sql_translator.ast.nodes import FunctionCall, Identifier


def _fn(make, name, *args):
    ident = make(Identifier, name=name)
    return make(FunctionCall, name=ident, args=list(args))


class TestCharLengthRewrite:
    @pytest.mark.parametrize("fn_name", [
        "char_length", "character_length", "CHAR_LENGTH", "Character_Length",
    ])
    def test_char_length_renamed_to_lengthUTF8(self, make, apply, fn_name):
        n = _fn(make, fn_name)
        r = apply(n)
        assert r.name.name == "lengthUTF8"

    def test_char_length_does_not_emit_annotation(self, make, apply, rule_ids):
        # Kind.B без message → нет аннотации.
        n = _fn(make, "char_length")
        r = apply(n)
        assert "pg_ch_fn_char_length" not in rule_ids(r)

    def test_unrelated_function_is_not_renamed(self, make, apply):
        n = _fn(make, "length")
        r = apply(n)
        assert r.name.name == "length"


class TestLengthBytes:
    def test_length_triggers_kindC(self, make, apply, rule_ids, kinds):
        n = _fn(make, "length")
        r = apply(n)
        assert "pg_ch_fn_length_bytes" in rule_ids(r)
        assert Kind.C in kinds(r)

    def test_length_message_mentions_bytes_or_utf8(self, make, apply):
        n = _fn(make, "length")
        r = apply(n)
        ann = next(a for a in r.annotations if a.rule_id == "pg_ch_fn_length_bytes")
        msg = (ann.message or "").lower()
        assert "байт" in msg or "lengthutf8" in msg


class TestUpperLowerLocale:
    @pytest.mark.parametrize("fn_name,rule_id", [
        ("upper", "pg_ch_fn_upper_locale"),
        ("UPPER", "pg_ch_fn_upper_locale"),
        ("lower", "pg_ch_fn_lower_locale"),
        ("Lower", "pg_ch_fn_lower_locale"),
    ])
    def test_upper_lower_trigger_kindC(
        self, make, apply, rule_ids, kinds, fn_name, rule_id
    ):
        n = _fn(make, fn_name)
        r = apply(n)
        assert rule_id in rule_ids(r)
        assert Kind.C in kinds(r)

    def test_upper_message_mentions_locale_or_utf8(self, make, apply):
        n = _fn(make, "upper")
        r = apply(n)
        ann = next(a for a in r.annotations if a.rule_id == "pg_ch_fn_upper_locale")
        msg = (ann.message or "").lower()
        assert "локаль" in msg or "utf8" in msg or "ascii" in msg


class TestTrimForms:
    @pytest.mark.parametrize("fn_name", [
        "ltrim", "rtrim", "btrim", "trim", "LTRIM", "Trim",
    ])
    def test_trim_family_triggers_kindC(
        self, make, apply, rule_ids, kinds, fn_name
    ):
        n = _fn(make, fn_name)
        r = apply(n)
        assert "pg_ch_fn_trim_forms" in rule_ids(r)
        assert Kind.C in kinds(r)

    def test_unrelated_function_does_not_trigger_trim(
        self, make, apply, rule_ids
    ):
        n = _fn(make, "concat")
        r = apply(n)
        assert "pg_ch_fn_trim_forms" not in rule_ids(r)


class TestQuoteIdent:
    @pytest.mark.parametrize("fn_name", [
        "quote_ident", "quote_literal", "quote_nullable",
        "QUOTE_IDENT", "Quote_Literal",
    ])
    def test_quote_family_triggers_kindE(
        self, make, apply, rule_ids, kinds, fn_name
    ):
        n = _fn(make, fn_name)
        r = apply(n)
        assert "pg_ch_fn_quote_ident" in rule_ids(r)
        assert Kind.E in kinds(r)


class TestTsvector:
    @pytest.mark.parametrize("fn_name", [
        "to_tsvector", "to_tsquery", "plainto_tsquery", "phraseto_tsquery",
        "websearch_to_tsquery", "ts_rank", "ts_rank_cd", "ts_headline",
        "ts_rewrite", "tsvector_to_array", "array_to_tsvector",
    ])
    def test_tsvector_family_triggers_kindE(
        self, make, apply, rule_ids, kinds, fn_name
    ):
        n = _fn(make, fn_name)
        r = apply(n)
        assert "pg_ch_fn_tsvector" in rule_ids(r)
        assert Kind.E in kinds(r)

    def test_case_insensitive(self, make, apply, rule_ids):
        n = _fn(make, "TO_TSVECTOR")
        r = apply(n)
        assert "pg_ch_fn_tsvector" in rule_ids(r)


class TestConvertEncoding:
    @pytest.mark.parametrize("fn_name", [
        "convert", "convert_from", "convert_to", "CONVERT_FROM",
    ])
    def test_convert_family_triggers_kindE(
        self, make, apply, rule_ids, kinds, fn_name
    ):
        n = _fn(make, fn_name)
        r = apply(n)
        assert "pg_ch_fn_convert_encoding" in rule_ids(r)
        assert Kind.E in kinds(r)


class TestStringFnsIsolation:
    def test_unknown_function_no_string_rules(self, make, apply, rule_ids):
        n = _fn(make, "some_random_string_fn")
        r = apply(n)
        ids = rule_ids(r)
        for forbidden in (
            "pg_ch_fn_char_length", "pg_ch_fn_length_bytes",
            "pg_ch_fn_upper_locale", "pg_ch_fn_lower_locale",
            "pg_ch_fn_trim_forms", "pg_ch_fn_quote_ident",
            "pg_ch_fn_tsvector", "pg_ch_fn_convert_encoding",
        ):
            assert forbidden not in ids
