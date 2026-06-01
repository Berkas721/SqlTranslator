"""Кейсы для Literal / ArrayConstructor / TupleConstructor."""
from __future__ import annotations

import pytest

from sql_translator.ast.nodes import (
    ArrayConstructor,
    Literal,
    TupleConstructor,
    TypeRef,
)


def _lit(make, value=None, literal_kind="int", raw=None):
    return make(Literal, value=value, literal_kind=literal_kind, raw=raw)


CASES: list = [
    # ── Literal ──────────────────────────────────────────────────────────────
    pytest.param(
        lambda m: _lit(m, value=42, literal_kind="int", raw="42"),
        "42",
        id="literal-int",
    ),
    pytest.param(
        lambda m: _lit(m, value=1.5, literal_kind="float", raw="1.5"),
        "1.5",
        id="literal-float",
    ),
    pytest.param(
        lambda m: _lit(m, value="abc", literal_kind="string", raw="abc"),
        "'abc'",
        id="literal-string-simple",
    ),
    pytest.param(
        lambda m: _lit(m, value="O'Brien", literal_kind="string", raw="O'Brien"),
        "'O\\'Brien'",
        id="literal-string-quote-escape",
    ),
    pytest.param(
        lambda m: _lit(m, value="a\\b", literal_kind="string", raw="a\\b"),
        "'a\\\\b'",
        id="literal-string-backslash-escape",
    ),
    pytest.param(
        lambda m: _lit(m, value=True, literal_kind="bool"),
        "true",
        id="literal-bool-true",
    ),
    pytest.param(
        lambda m: _lit(m, value=False, literal_kind="bool"),
        "false",
        id="literal-bool-false",
    ),
    pytest.param(
        lambda m: _lit(m, value=None, literal_kind="null"),
        "NULL",
        id="literal-null",
    ),
    pytest.param(
        lambda m: _lit(m, value="2024-01-01", literal_kind="date", raw="2024-01-01"),
        "'2024-01-01'",
        id="literal-date",
    ),
    pytest.param(
        lambda m: _lit(m, value="2024-01-01 00:00:00",
                       literal_kind="timestamp", raw="2024-01-01 00:00:00"),
        "'2024-01-01 00:00:00'",
        id="literal-timestamp",
    ),
    pytest.param(
        lambda m: _lit(m, value="1 day", literal_kind="interval", raw="1 day"),
        "1 day",
        id="literal-interval",
    ),
    pytest.param(
        lambda m: _lit(m, value="0101", literal_kind="bit", raw="0101"),
        "0101",
        id="literal-bit-fallback-raw",
    ),

    pytest.param(
        lambda m: _lit_with_explicit(m),
        "Date '2024-01-01'",
        id="literal-explicit-type",
    ),

    # ── ArrayConstructor ─────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(ArrayConstructor, elements=[]),
        "[]",
        id="array-empty",
    ),
    pytest.param(
        lambda m: m(ArrayConstructor, elements=[
            _lit(m, 1, "int", "1"),
            _lit(m, 2, "int", "2"),
            _lit(m, 3, "int", "3"),
        ]),
        "[1, 2, 3]",
        id="array-three-ints",
    ),
    pytest.param(
        lambda m: m(ArrayConstructor, elements=[
            _lit(m, "a", "string", "a"),
            _lit(m, "b", "string", "b"),
        ]),
        "['a', 'b']",
        id="array-strings",
    ),

    # ── TupleConstructor ─────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(TupleConstructor, syntax="parens", elements=[
            _lit(m, 1, "int", "1"),
            _lit(m, 2, "int", "2"),
        ]),
        "(1, 2)",
        id="tuple-parens",
    ),
    pytest.param(
        lambda m: m(TupleConstructor, syntax="row_kw", elements=[
            _lit(m, 1, "int", "1"),
            _lit(m, 2, "int", "2"),
        ]),
        "tuple(1, 2)",
        id="tuple-row-kw",
    ),
    pytest.param(
        lambda m: m(TupleConstructor, syntax="parens", elements=[]),
        "()",
        id="tuple-empty",
    ),
]


def _make_type(make, name: str, **kwargs):
    return make(TypeRef, name=name, **kwargs)


def _lit_with_explicit(make):
    """Сборка Literal с explicit_type через make (нужно для node_kind/dialect)."""
    t = _make_type(make, "Date")
    return make(
        Literal,
        value="2024-01-01",
        literal_kind="string",
        raw="2024-01-01",
        explicit_type=t,
    )
