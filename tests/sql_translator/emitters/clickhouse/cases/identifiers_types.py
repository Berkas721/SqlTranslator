"""Кейсы для Identifier / ColumnRef / StarExpr / TypeRef."""
from __future__ import annotations

import pytest

from sql_translator.ast.nodes import (
    ColumnRef,
    Identifier,
    Literal,
    StarExpr,
    TypeRef,
)


def _ident(make, name, quoted=False):
    return make(Identifier, name=name, quoted=quoted)


def _lit_int(make, v):
    return make(Literal, value=v, literal_kind="int", raw=str(v))


CASES: list = [
    # ── Identifier ───────────────────────────────────────────────────────────
    pytest.param(
        lambda m: _ident(m, "name"),
        "name",
        id="ident-bare",
    ),
    pytest.param(
        lambda m: _ident(m, "name", quoted=True),
        "`name`",
        id="ident-quoted",
    ),
    pytest.param(
        lambda m: _ident(m, "weird`tick", quoted=True),
        "`weird``tick`",
        id="ident-quoted-escape",
    ),

    # ── ColumnRef ────────────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(ColumnRef, column=_ident(m, "x")),
        "x",
        id="colref-column-only",
    ),
    pytest.param(
        lambda m: m(ColumnRef, table=_ident(m, "t"), column=_ident(m, "x")),
        "t.x",
        id="colref-table-column",
    ),
    pytest.param(
        lambda m: m(ColumnRef,
                    schema=_ident(m, "s"),
                    table=_ident(m, "t"),
                    column=_ident(m, "x")),
        "s.t.x",
        id="colref-schema-table-column",
    ),
    pytest.param(
        lambda m: m(ColumnRef,
                    database=_ident(m, "d"),
                    schema=_ident(m, "s"),
                    table=_ident(m, "t"),
                    column=_ident(m, "x")),
        "d.s.t.x",
        id="colref-db-schema-table-column",
    ),

    # ── StarExpr ─────────────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(StarExpr),
        "*",
        id="star-bare",
    ),
    pytest.param(
        lambda m: m(StarExpr, table=_ident(m, "t")),
        "t.*",
        id="star-qualified",
    ),

    # ── TypeRef ──────────────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(TypeRef, name="UInt32"),
        "UInt32",
        id="type-bare",
    ),
    pytest.param(
        lambda m: m(TypeRef, name="Decimal", params=[
            _lit_int(m, 10), _lit_int(m, 2),
        ]),
        "Decimal(10, 2)",
        id="type-with-params",
    ),
    pytest.param(
        lambda m: m(TypeRef, name="String", array_dims=1),
        "Array(String)",
        id="type-array-1d",
    ),
    pytest.param(
        lambda m: m(TypeRef, name="Int64", array_dims=2),
        "Array(Array(Int64))",
        id="type-array-2d",
    ),
    pytest.param(
        lambda m: m(TypeRef, name="Decimal", array_dims=1, params=[
            _lit_int(m, 10), _lit_int(m, 2),
        ]),
        "Array(Decimal(10, 2))",
        id="type-array-with-params",
    ),
]
