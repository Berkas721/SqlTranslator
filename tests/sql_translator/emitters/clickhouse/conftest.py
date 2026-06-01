"""Хелперы для модульных тестов ClickHouseEmitter."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[3] / "src"
if str(_SRC) in sys.path:
    sys.path.remove(str(_SRC))
sys.path.insert(0, str(_SRC))

for _name in [
    n for n in list(sys.modules)
    if n == "sql_translator" or n.startswith("sql_translator.")
]:
    _mod = sys.modules[_name]
    _file = getattr(_mod, "__file__", "") or ""
    if "tests" in _file.replace("\\", "/").split("/"):
        del sys.modules[_name]

import sql_translator  # noqa: E402
sys.modules.setdefault("src", sql_translator)
for _sub in (
    "ast", "ast.metadata", "ast.node", "ast.nodes", "ast.registry",
    "emitters", "emitters.clickhouse", "emitters.clickhouse.emitter",
):
    try:
        _mod = importlib.import_module(f"sql_translator.{_sub}")
        sys.modules.setdefault(f"src.{_sub}", _mod)
    except ImportError:
        pass

from sql_translator.ast.metadata import Dialect  # noqa: E402
from sql_translator.emitters.clickhouse.emitter import ClickHouseEmitter  # noqa: E402


@pytest.fixture
def make():
    """Создаёт узел с проставленными node_kind и dialect=CLICKHOUSE."""
    def _make(cls, **kwargs):
        n = cls(**kwargs)
        n.node_kind = cls.__name__
        n.dialect = Dialect.CLICKHOUSE
        return n
    return _make


@pytest.fixture
def emit():
    """Возвращает функцию: node -> str (результат эмиссии)."""
    def _emit(node):
        em = ClickHouseEmitter()
        em.emit(node)
        return em.result()
    return _emit


@pytest.fixture
def emit_with():
    """Возвращает функцию с настраиваемым отступом."""
    def _emit_with(node, indent: int = 4):
        em = ClickHouseEmitter(indent=indent)
        em.emit(node)
        return em.result()
    return _emit_with
