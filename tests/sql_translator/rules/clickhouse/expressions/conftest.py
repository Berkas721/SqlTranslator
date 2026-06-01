"""Хелперы для модульных тестов expressions-правил clickhouse."""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest

_SRC = Path(__file__).resolve().parents[4] / "src"
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
    "ast.rules", "ast.rules.clickhouse",
):
    try:
        _mod = importlib.import_module(f"sql_translator.{_sub}")
        sys.modules.setdefault(f"src.{_sub}", _mod)
    except ImportError:
        pass

import sql_translator.ast.rules.clickhouse  # noqa: F401,E402

from sql_translator.ast.metadata import Dialect  # noqa: E402
from sql_translator.ast.registry import TranslateContext, default_translator  # noqa: E402


@pytest.fixture
def ctx() -> TranslateContext:
    return TranslateContext(
        source_dialect=Dialect.POSTGRES,
        target_dialect=Dialect.CLICKHOUSE,
        translator=default_translator,
    )


@pytest.fixture
def make():
    def _make(cls, **kwargs):
        n = cls(**kwargs)
        n.node_kind = cls.__name__
        n.dialect = Dialect.POSTGRES
        return n
    return _make


@pytest.fixture
def apply(ctx):
    def _apply(node):
        return default_translator.apply(node, Dialect.CLICKHOUSE, ctx)
    return _apply


@pytest.fixture
def kinds():
    return lambda n: [a.kind for a in n.annotations]


@pytest.fixture
def rule_ids():
    return lambda n: [a.rule_id for a in n.annotations]
