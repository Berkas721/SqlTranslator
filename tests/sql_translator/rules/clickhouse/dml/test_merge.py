"""Правила pg→ch для MERGE.
"""
from __future__ import annotations

from sql_translator.ast.metadata import Kind
from sql_translator.ast.nodes import MergeStmt


class TestMergeStmt:
    def test_merge_always_kindE(self, make, apply, rule_ids, kinds):
        n = make(MergeStmt)
        r = apply(n)
        assert "pg_ch_merge_stmt" in rule_ids(r)
        assert Kind.E in kinds(r)

    def test_merge_annotation_mentions_replacing_merge_tree(
        self, make, apply
    ):
        n = make(MergeStmt)
        r = apply(n)
        ann = next(a for a in r.annotations if a.rule_id == "pg_ch_merge_stmt")
        msg = ann.message or ""
        assert "ReplacingMergeTree" in msg
        assert "CollapsingMergeTree" in msg

    def test_merge_produces_exactly_one_annotation(self, make, apply):
        n = make(MergeStmt)
        r = apply(n)
        assert len(r.annotations) == 1
