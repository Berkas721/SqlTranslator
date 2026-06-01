"""Правила pg→ch для COPY.
Источник правил: ``src/sql_translator/ast/rules/clickhouse/dml/copy.py``.
"""
from __future__ import annotations

import pytest

from sql_translator.ast.metadata import Kind
from sql_translator.ast.nodes import (
    CopyStmt,
    Identifier,
    Literal,
    TableRef,
)


def _copy(make, **kwargs):
    kwargs.setdefault("table", make(TableRef))
    kwargs.setdefault("direction", "FROM")
    return make(CopyStmt, **kwargs)


class TestCopyRewriteFrom:
    def test_copy_from_file_sets_ch_from_infile_and_format(
        self, make, apply
    ):
        n = _copy(make, direction="FROM", filename="/data/t.csv", format="CSV")
        r = apply(n)
        assert r.ch_from_infile == "/data/t.csv"
        assert r.ch_format == "CSV"
        assert r.ch_into_outfile is None

    def test_copy_from_file_default_format_csv(self, make, apply):
        n = _copy(make, direction="FROM", filename="/data/t.csv", format=None)
        r = apply(n)
        assert r.ch_format == "CSV"

    def test_copy_from_stdin_sets_format_no_infile(self, make, apply):
        n = _copy(make, direction="FROM", stdin=True, format="TSV")
        r = apply(n)
        assert r.ch_from_infile is None
        assert r.ch_format == "TSV"

    def test_copy_from_stdin_default_format_csv(self, make, apply):
        n = _copy(make, direction="FROM", stdin=True, format=None)
        r = apply(n)
        assert r.ch_format == "CSV"


class TestCopyRewriteTo:
    def test_copy_to_file_sets_ch_into_outfile_and_format(
        self, make, apply
    ):
        n = _copy(make, direction="TO", filename="/out/t.csv", format="CSV")
        r = apply(n)
        assert r.ch_into_outfile == "/out/t.csv"
        assert r.ch_format == "CSV"
        assert r.ch_from_infile is None

    def test_copy_to_file_default_format_csv(self, make, apply):
        n = _copy(make, direction="TO", filename="/out/t.csv", format=None)
        r = apply(n)
        assert r.ch_format == "CSV"


class TestCopySessionOptions:
    @pytest.mark.parametrize("field,value", [
        ("delimiter", ","),
        ("quote_char", '"'),
        ("escape_char", "\\"),
        ("null_str", "\\N"),
        ("header", True),
        ("encoding", "UTF8"),
    ])
    def test_each_option_does_not_produce_fallback(
        self, make, apply, rule_ids, field, value
    ):
        n = _copy(make, direction="FROM", stdin=True, **{field: value})
        r = apply(n)
        ids = rule_ids(r)
        assert "pg_ch.fallback" not in ids
        assert "pg_ch_copy_options_session" not in ids

    def test_header_false_does_not_break(self, make, apply, kinds):
        # `header is not None` — False значимо для when, но annotation нет.
        n = _copy(make, direction="FROM", stdin=True, header=False)
        r = apply(n)
        from sql_translator.ast.metadata import Kind as _K
        assert _K.F not in kinds(r)


class TestCopyFormatRule:
    def test_format_triggers_kindD(self, make, apply, rule_ids, kinds):
        n = _copy(make, direction="FROM", stdin=True, format="CSV")
        r = apply(n)
        assert "pg_ch_copy_format" in rule_ids(r)
        assert Kind.D in kinds(r)

    def test_no_format_no_D_rule(self, make, apply, rule_ids):
        n = _copy(make, direction="FROM", stdin=True, format=None)
        r = apply(n)
        assert "pg_ch_copy_format" not in rule_ids(r)


class TestCopyOnError:
    def test_on_error_triggers_kindD(self, make, apply, rule_ids, kinds):
        n = _copy(make, direction="FROM", stdin=True, on_error="ignore")
        r = apply(n)
        assert "pg_ch_copy_on_error" in rule_ids(r)
        assert Kind.D in kinds(r)

    def test_reject_limit_triggers_kindD(self, make, apply, rule_ids):
        n = _copy(make, direction="FROM", stdin=True, reject_limit=100)
        r = apply(n)
        assert "pg_ch_copy_on_error" in rule_ids(r)

    def test_neither_does_not_trigger(self, make, apply, rule_ids):
        n = _copy(make, direction="FROM", stdin=True)
        r = apply(n)
        assert "pg_ch_copy_on_error" not in rule_ids(r)


class TestCopyKindE:
    def test_program_triggers_kindE(self, make, apply, rule_ids, kinds):
        n = _copy(make, direction="FROM", program="gzip -dc t.csv.gz")
        r = apply(n)
        assert "pg_ch_copy_program" in rule_ids(r)
        assert Kind.E in kinds(r)

    def test_where_triggers_kindE(self, make, apply, rule_ids):
        cond = make(Literal, value=True, literal_kind="bool")
        n = _copy(make, direction="FROM", stdin=True, where=cond)
        r = apply(n)
        assert "pg_ch_copy_where" in rule_ids(r)

    def test_freeze_triggers_kindE(self, make, apply, rule_ids):
        n = _copy(make, direction="FROM", stdin=True, freeze=True)
        r = apply(n)
        assert "pg_ch_copy_freeze" in rule_ids(r)

    def test_freeze_false_still_triggers(self, make, apply, rule_ids):
        # ``when=lambda n: n.freeze is not None`` — False тоже срабатывает.
        n = _copy(make, direction="FROM", stdin=True, freeze=False)
        r = apply(n)
        assert "pg_ch_copy_freeze" in rule_ids(r)

    def test_freeze_none_does_not_trigger(self, make, apply, rule_ids):
        n = _copy(make, direction="FROM", stdin=True, freeze=None)
        r = apply(n)
        assert "pg_ch_copy_freeze" not in rule_ids(r)

    def test_header_match_triggers_kindE(self, make, apply, rule_ids):
        n = _copy(make, direction="FROM", stdin=True, header_match=True)
        r = apply(n)
        assert "pg_ch_copy_header_match" in rule_ids(r)

    @pytest.mark.parametrize("field,rule_id", [
        ("force_quote",    "pg_ch_copy_force_quote"),
        ("force_not_null", "pg_ch_copy_force_not_null"),
        ("force_null",     "pg_ch_copy_force_null"),
    ])
    def test_force_lists_trigger_kindE(
        self, make, apply, rule_ids, field, rule_id
    ):
        col = make(Identifier, name="c")
        n = _copy(make, direction="FROM", stdin=True, **{field: [col]})
        r = apply(n)
        assert rule_id in rule_ids(r)

    def test_log_verbosity_triggers_kindE(self, make, apply, rule_ids):
        n = _copy(make, direction="FROM", stdin=True, log_verbosity="verbose")
        r = apply(n)
        assert "pg_ch_copy_log_verbosity" in rule_ids(r)


class TestCopyCombined:
    def test_from_file_with_format_yields_B_rewrite_plus_D_annotation(
        self, make, apply, rule_ids, kinds
    ):
        n = _copy(make, direction="FROM", filename="/data/t.csv", format="CSV")
        r = apply(n)
        assert r.ch_from_infile == "/data/t.csv"
        ks = kinds(r)
        assert Kind.D in ks
        assert ks.count(Kind.D) == 1

    def test_from_file_with_program_keeps_rewrite_and_E_annotation(
        self, make, apply, rule_ids
    ):
        n = _copy(
            make,
            direction="FROM",
            filename="/data/t.csv",
            program="gzip -dc t.csv.gz",
        )
        r = apply(n)
        assert r.ch_from_infile == "/data/t.csv"
        assert "pg_ch_copy_program" in rule_ids(r)
