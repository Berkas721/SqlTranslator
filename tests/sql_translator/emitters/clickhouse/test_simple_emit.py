"""Параметеризированный тест простых per-node методов ClickHouseEmitter.

Кейсы описаны в ``cases/*.py`` как list[pytest.param] с тройкой
``(builder, expected, id)``, где ``builder(make)`` возвращает AST-узел.
"""
from __future__ import annotations

import pytest

from tests.sql_translator.emitters.clickhouse.cases import ALL_SIMPLE_CASES


@pytest.mark.parametrize("builder,expected", ALL_SIMPLE_CASES)
def test_emit_simple_node(make, emit, builder, expected):
    node = builder(make)
    assert emit(node) == expected
