"""Хелперы для тестов парсера."""
from __future__ import annotations

import pytest

from sql_translator.parser import parse_sql


@pytest.fixture
def parse():
    """Парсит SQL, возвращает Script."""
    return parse_sql


@pytest.fixture
def parse_one():
    """Парсит SQL, проверяет ровно один statement, возвращает его."""
    def _parse_one(sql: str):
        script = parse_sql(sql)
        assert len(script.statements) == 1, (
            f"Expected exactly one statement, got {len(script.statements)}"
        )
        return script.statements[0]
    return _parse_one


@pytest.fixture
def parse_expr():
    """Парсит 'SELECT <expr>' и возвращает выражение первого target-а."""
    def _parse_expr(sql_expr: str):
        script = parse_sql(f"SELECT {sql_expr}")
        return script.statements[0].targets[0].expression
    return _parse_expr
