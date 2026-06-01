"""Кейсы для DDL-вспомогательных узлов:
ColumnConstraint, ColumnDef, TableConstraint, LikeClause, EngineSpec,
TtlClause, TtlRule, IndexColumn, OnConflictClause, DefaultValues."""
from __future__ import annotations

import pytest

from sql_translator.ast.nodes import (
    ColumnConstraint,
    ColumnDef,
    DefaultValues,
    EngineSpec,
    FunctionCall,
    Identifier,
    IndexColumn,
    LikeClause,
    Literal,
    OnConflictClause,
    SettingAssignment,
    TableConstraint,
    TableRef,
    TtlClause,
    TtlRule,
    TypeRef,
)


def _ident(make, name, quoted=False):
    return make(Identifier, name=name, quoted=quoted)


def _lit(make, value=1, kind="int", raw=None):
    return make(Literal, value=value, literal_kind=kind,
                raw=raw if raw is not None else str(value))


CASES: list = [
    # ── ColumnConstraint ─────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(ColumnConstraint, kind="not_null"),
        "NOT NULL",
        id="constraint-not-null",
    ),
    pytest.param(
        lambda m: m(ColumnConstraint, kind="null"),
        "NULL",
        id="constraint-null",
    ),
    pytest.param(
        lambda m: m(ColumnConstraint, kind="primary_key"),
        "PRIMARY KEY",
        id="constraint-pk",
    ),
    pytest.param(
        lambda m: m(ColumnConstraint, kind="unique"),
        "UNIQUE",
        id="constraint-unique",
    ),
    pytest.param(
        lambda m: m(ColumnConstraint, kind="default",
                    expression=_lit(m, 0)),
        "DEFAULT 0",
        id="constraint-default",
    ),
    pytest.param(
        lambda m: m(ColumnConstraint, kind="check",
                    expression=_ident(m, "x")),
        "CHECK (x)",
        id="constraint-check",
    ),
    pytest.param(
        lambda m: m(ColumnConstraint, kind="generated_stored",
                    expression=_ident(m, "x")),
        "MATERIALIZED x",
        id="constraint-materialized",
    ),
    pytest.param(
        lambda m: m(ColumnConstraint, kind="generated_virtual",
                    expression=_ident(m, "x")),
        "ALIAS x",
        id="constraint-alias",
    ),
    pytest.param(
        lambda m: m(ColumnConstraint, kind="generated_identity"),
        "DEFAULT generateUUIDv4()",
        id="constraint-identity",
    ),
    pytest.param(
        lambda m: m(ColumnConstraint, kind="references",
                    ref_table=m(TableRef, name=_ident(m, "other")),
                    ref_columns=[_ident(m, "id")]),
        "REFERENCES other (id)",
        id="constraint-references",
    ),

    # ── ColumnDef ────────────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(ColumnDef, name=_ident(m, "id"),
                    type=m(TypeRef, name="UInt64")),
        "id UInt64",
        id="columndef-bare",
    ),
    pytest.param(
        lambda m: m(ColumnDef, name=_ident(m, "id"),
                    type=m(TypeRef, name="UInt64"),
                    constraints=[m(ColumnConstraint, kind="not_null")]),
        "id UInt64 NOT NULL",
        id="columndef-not-null",
    ),
    pytest.param(
        lambda m: m(ColumnDef, name=_ident(m, "v"),
                    type=m(TypeRef, name="UInt32"),
                    codec=[m(FunctionCall, name=_ident(m, "ZSTD"),
                             args=[_lit(m, 3)])]),
        "v UInt32 CODEC(ZSTD(3))",
        id="columndef-codec",
    ),
    pytest.param(
        lambda m: m(ColumnDef, name=_ident(m, "v"),
                    type=m(TypeRef, name="UInt32"),
                    ttl=_ident(m, "ts")),
        "v UInt32 TTL ts",
        id="columndef-ttl",
    ),

    # ── TableConstraint ──────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(TableConstraint, kind="primary_key",
                    columns=[_ident(m, "a"), _ident(m, "b")]),
        "PRIMARY KEY (a, b)",
        id="tableconstraint-pk",
    ),
    pytest.param(
        lambda m: m(TableConstraint, kind="unique", name="uq_x",
                    columns=[_ident(m, "x")]),
        "CONSTRAINT uq_x UNIQUE (x)",
        id="tableconstraint-named-unique",
    ),
    pytest.param(
        lambda m: m(TableConstraint, kind="check",
                    expression=_ident(m, "x")),
        "CHECK (x)",
        id="tableconstraint-check",
    ),
    pytest.param(
        lambda m: m(TableConstraint, kind="foreign_key",
                    columns=[_ident(m, "uid")],
                    ref_table=m(TableRef, name=_ident(m, "users")),
                    ref_columns=[_ident(m, "id")]),
        "FOREIGN KEY (uid) REFERENCES users (id)",
        id="tableconstraint-fk",
    ),

    # ── LikeClause ───────────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(LikeClause, source=m(TableRef, name=_ident(m, "src"))),
        "AS src",
        id="likeclause",
    ),

    # ── EngineSpec ───────────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(EngineSpec, name="MergeTree"),
        "ENGINE = MergeTree",
        id="engine-bare",
    ),
    pytest.param(
        lambda m: m(EngineSpec, name="ReplacingMergeTree",
                    args=[_ident(m, "v")]),
        "ENGINE = ReplacingMergeTree(v)",
        id="engine-with-args",
    ),

    # ── TtlClause / TtlRule ──────────────────────────────────────────────────
    pytest.param(
        lambda m: m(TtlClause, rules=[
            m(TtlRule, expression=_ident(m, "ts"), action="DELETE"),
        ]),
        "TTL ts",
        id="ttl-delete-default",
    ),
    pytest.param(
        lambda m: m(TtlClause, rules=[
            m(TtlRule, expression=_ident(m, "ts"),
              action="TO_VOLUME", target="cold"),
        ]),
        "TTL ts TO_VOLUME 'cold'",
        id="ttl-to-volume",
    ),
    pytest.param(
        lambda m: m(TtlRule, expression=_ident(m, "ts"), action="DELETE"),
        "ts",
        id="ttlrule-delete",
    ),
    pytest.param(
        lambda m: m(TtlRule, expression=_ident(m, "ts"),
                    action="TO_DISK", target="ssd"),
        "ts TO_DISK 'ssd'",
        id="ttlrule-to-disk",
    ),

    # ── IndexColumn ──────────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(IndexColumn, expression=_ident(m, "x")),
        "x",
        id="indexcol-plain",
    ),
    pytest.param(
        lambda m: m(IndexColumn, expression=_ident(m, "x"),
                    direction="DESC", nulls="FIRST"),
        "x DESC NULLS FIRST",
        id="indexcol-desc-nulls",
    ),

    # ── OnConflictClause ─────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(OnConflictClause, action="nothing"),
        "ON CONFLICT DO NOTHING",
        id="onconflict-nothing",
    ),
    pytest.param(
        lambda m: m(OnConflictClause, target=_ident(m, "id"), action="nothing"),
        "ON CONFLICT (id) DO NOTHING",
        id="onconflict-target-nothing",
    ),
    pytest.param(
        lambda m: m(OnConflictClause, action="update",
                    updates=[m(SettingAssignment, name="x",
                               value=_lit(m, 1))]),
        "ON CONFLICT DO UPDATE SET x = 1",
        id="onconflict-update",
    ),

    # ── DefaultValues ────────────────────────────────────────────────────────
    pytest.param(
        lambda m: m(DefaultValues),
        "DEFAULT VALUES",
        id="default-values",
    ),
]
