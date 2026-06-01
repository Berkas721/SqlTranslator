"""Общий setup для всех тестов под tests/sql_translator/.

Делает две вещи:
  1. Добавляет src/ в sys.path — чтобы работали `from sql_translator.X` импорты.
  2. Регистрирует alias `src` → `sql_translator` (и ключевые подпакеты) —
     потому что часть исходного кода использует legacy-импорты `from src.ast …`.
     Shim снимает необходимость править исходники только ради тестов.
"""
from __future__ import annotations

import importlib
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[1].parent / "src"
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

import sql_translator  # noqa: E402

sys.modules.setdefault("src", sql_translator)

for _sub in (
    "ast", "ast.metadata", "ast.node", "ast.nodes", "ast.registry",
    "ast.rules", "ast.rules.clickhouse",
    "parser",
    "emitters", "emitters.clickhouse",
):
    try:
        _mod = importlib.import_module(f"sql_translator.{_sub}")
        sys.modules.setdefault(f"src.{_sub}", _mod)
    except ImportError:
        pass
