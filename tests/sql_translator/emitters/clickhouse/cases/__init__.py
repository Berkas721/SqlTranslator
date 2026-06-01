"""Кейсы для параметеризированного теста простых per-node методов эмиттера.

Каждый модуль экспортирует ``CASES: list[pytest.param]``, элементы — кортежи
``(builder, expected)``, где ``builder(make) -> Node``.
"""
from __future__ import annotations

from .expressions import CASES as EXPRESSION_CASES
from .identifiers_types import CASES as IDENT_TYPE_CASES
from .literals import CASES as LITERAL_CASES
from .clauses import CASES as CLAUSE_CASES
from .ddl_helpers import CASES as DDL_HELPER_CASES
from .tcl import CASES as TCL_CASES
from .misc import CASES as MISC_CASES

ALL_SIMPLE_CASES = (
    LITERAL_CASES
    + IDENT_TYPE_CASES
    + EXPRESSION_CASES
    + CLAUSE_CASES
    + DDL_HELPER_CASES
    + TCL_CASES
    + MISC_CASES
)
