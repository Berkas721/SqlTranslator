"""Правила преобразования MERGE: PostgreSQL → ClickHouse.
"""
from __future__ import annotations

from src.ast.metadata import Dialect, Kind
from src.ast.registry import Rule, default_translator

_MERGE_RULES: list[Rule] = [
    Rule(
        rule_id="pg_ch_merge_stmt",
        title="MERGE INTO ... USING ... ON ... WHEN ... (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="MergeStmt",
        kind=Kind.E,
        when=lambda n: True,
        rewrite=None,
        message=(
            "нет аналога в ClickHouse. "
            "Функциональный суррогат для upsert-сценариев — движки "
            "ReplacingMergeTree, CollapsingMergeTree, VersionedCollapsingMergeTree."
        ),
    ),
]

for _rule in _MERGE_RULES:
    default_translator.register(_rule)
