"""Тесты эмиссии InsertStmt (VALUES / SELECT / DEFAULT VALUES / FORMAT / ON CONFLICT)."""
from __future__ import annotations

from sql_translator.ast.nodes import (
    DefaultValues,
    Identifier,
    InsertStmt,
    Literal,
    OnConflictClause,
    SelectStmt,
    SelectTarget,
    SettingAssignment,
    StarExpr,
    TableRef,
    ValuesClause,
)


def _ident(make, name):
    return make(Identifier, name=name)


def _lit(make, value, kind="int", raw=None):
    return make(Literal, value=value, literal_kind=kind,
                raw=raw if raw is not None else str(value))


def test_insert_values_single_row(make, emit):
    n = make(InsertStmt,
             target=make(TableRef, name=_ident(make, "t")),
             columns=[_ident(make, "a"), _ident(make, "b")],
             source=make(ValuesClause, rows=[[_lit(make, 1), _lit(make, 2)]]))
    assert emit(n) == "INSERT INTO t (a, b)\nVALUES\n    (1, 2)"


def test_insert_values_multiple_rows(make, emit):
    n = make(InsertStmt,
             target=make(TableRef, name=_ident(make, "t")),
             source=make(ValuesClause, rows=[
                 [_lit(make, 1)],
                 [_lit(make, 2)],
                 [_lit(make, 3)],
             ]))
    assert emit(n) == "INSERT INTO t\nVALUES\n    (1),\n    (2),\n    (3)"


def test_insert_select(make, emit):
    sel = make(SelectStmt,
               targets=[make(SelectTarget, expression=make(StarExpr))],
               from_items=[make(TableRef, name=_ident(make, "src"))])
    n = make(InsertStmt,
             target=make(TableRef, name=_ident(make, "dst")),
             source=sel)
    assert emit(n) == "INSERT INTO dst\nSELECT\n    *\nFROM src"


def test_insert_default_values(make, emit):
    n = make(InsertStmt,
             target=make(TableRef, name=_ident(make, "t")),
             source=make(DefaultValues))
    assert emit(n) == "INSERT INTO t\nDEFAULT VALUES"


def test_insert_ch_format(make, emit):
    n = make(InsertStmt,
             target=make(TableRef, name=_ident(make, "t")),
             ch_format="JSONEachRow")
    assert emit(n) == "INSERT INTO t FORMAT JSONEachRow"


def test_insert_on_conflict_nothing(make, emit):
    n = make(InsertStmt,
             target=make(TableRef, name=_ident(make, "t")),
             source=make(ValuesClause, rows=[[_lit(make, 1)]]),
             on_conflict=make(OnConflictClause, action="nothing"))
    out = emit(n)
    assert out.endswith("\nON CONFLICT DO NOTHING")
    assert out.startswith("INSERT INTO t\nVALUES\n    (1)")


def test_insert_on_conflict_update(make, emit):
    n = make(InsertStmt,
             target=make(TableRef, name=_ident(make, "t")),
             source=make(ValuesClause, rows=[[_lit(make, 1)]]),
             on_conflict=make(OnConflictClause, action="update",
                              target=_ident(make, "id"),
                              updates=[make(SettingAssignment, name="x",
                                            value=_lit(make, 2))]))
    out = emit(n)
    assert "ON CONFLICT (id) DO UPDATE SET x = 2" in out
