"""Правила преобразования SELECT: PostgreSQL → ClickHouse.
"""
from __future__ import annotations

from src.ast.metadata import Dialect, Kind
from src.ast.nodes import BinaryOp, Literal, SampleClause
from src.ast.registry import Rule, TranslateContext, default_translator

_E_MSG = "нет аналога в ClickHouse"


def _rewrite_fetch_only(n, ctx: TranslateContext):
    """FETCH FIRST n ROWS ONLY → LIMIT n."""
    n.limit = n.fetch.count
    n.fetch = None
    return n


def _rewrite_fetch_ties(n, ctx: TranslateContext):
    """FETCH [n] WITH TIES → LIMIT n WITH TIES."""
    n.limit = n.fetch.count
    n.limit_with_ties = True
    n.fetch = None
    return n


_SELECT_RULES: list[Rule] = [
    Rule(
        rule_id="pg_ch_select_base",
        title="SelectStmt (базовый проход, тип A)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="SelectStmt",
        kind=Kind.A,
        when=lambda n: True,
        rewrite=None,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_select_fetch_only",
        title="FETCH FIRST [count] ROWS ONLY → LIMIT count (тип B)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="SelectStmt",
        kind=Kind.B,
        when=lambda n: n.fetch is not None and not n.fetch.with_ties,
        rewrite=_rewrite_fetch_only,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_select_fetch_ties",
        title="FETCH [count] WITH TIES → LIMIT count WITH TIES (тип B)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="SelectStmt",
        kind=Kind.B,
        when=lambda n: n.fetch is not None and n.fetch.with_ties,
        rewrite=_rewrite_fetch_ties,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_select_with_recursive",
        title="WITH RECURSIVE with_query (тип D)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="SelectStmt",
        kind=Kind.D,
        when=lambda n: n.with_clause is not None and n.with_clause.recursive,
        rewrite=None,
        message=(
            "Поддержка в CH с 24.8 при allow_experimental_analyzer "
            "и enable_recursive_cte; не поддерживаются взаимно-рекурсивные CTE."
        ),
    ),
    Rule(
        rule_id="pg_ch_select_locking",
        title="FOR {UPDATE|NO KEY UPDATE|SHARE|KEY SHARE} [NOWAIT|SKIP LOCKED] (тип E)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="SelectStmt",
        kind=Kind.E,
        when=lambda n: bool(n.locking),
        rewrite=None,
        message=_E_MSG,
    ),
]


_DISTINCT_RULES: list[Rule] = [
    Rule(
        rule_id="pg_ch_distinct_base",
        title="DistinctClause (базовый проход, тип A)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="DistinctClause",
        kind=Kind.A,
        when=lambda n: True,
        rewrite=None,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_distinct_on",
        title="DISTINCT ON (expr [, ...]) (тип C)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="DistinctClause",
        kind=Kind.C,
        when=lambda n: n.kind == "distinct_on",
        rewrite=None,
        message=(
            "Без ORDER BY порядок выдачи в CH не гарантирован "
            "из-за параллельной обработки блоков."
        ),
    ),
]


_WITH_RULES: list[Rule] = [
    Rule(
        rule_id="pg_ch_with_base",
        title="WithClause (базовый проход, тип A)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="WithClause",
        kind=Kind.A,
        when=lambda n: True,
        rewrite=None,
        message=None,
    ),
]


_GROUP_BY_RULES: list[Rule] = [
    Rule(
        rule_id="pg_ch_group_by_base",
        title="GroupByClause (базовый проход, тип A)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="GroupByClause",
        kind=Kind.A,
        when=lambda n: True,
        rewrite=None,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_group_by_all",
        title="GROUP BY ALL (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="GroupByClause",
        kind=Kind.E,
        when=lambda n: n.kind == "all",
        rewrite=None,
        message=_E_MSG,
    ),
    Rule(
        rule_id="pg_ch_group_by_distinct",
        title="GROUP BY DISTINCT (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="GroupByClause",
        kind=Kind.E,
        when=lambda n: n.kind == "distinct",
        rewrite=None,
        message=_E_MSG,
    ),
]


_SETOP_RULES: list[Rule] = [
    Rule(
        rule_id="pg_ch_setop_base",
        title="SetOpClause (базовый проход, тип A)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="SetOpClause",
        kind=Kind.A,
        when=lambda n: True,
        rewrite=None,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_setop_default_mode",
        title="INTERSECT / EXCEPT без ALL|DISTINCT (тип C)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="SetOpClause",
        kind=Kind.C,
        when=lambda n: n.op in ("INTERSECT", "EXCEPT") and n.quantifier is None,
        rewrite=None,
        message=(
            "PGSQL: умолчание DISTINCT. "
            "CH: до 24.2 — ALL, с 24.2 — DISTINCT (настройка union_default_mode)."
        ),
    ),
]


_JOIN_RULES: list[Rule] = [
    Rule(
        rule_id="pg_ch_join_base",
        title="JoinExpr (базовый проход, тип A)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="JoinExpr",
        kind=Kind.A,
        when=lambda n: True,
        rewrite=None,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_join_full",
        title="FULL [OUTER] JOIN (тип C)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="JoinExpr",
        kind=Kind.C,
        when=lambda n: n.kind == "full",
        rewrite=None,
        message=(
            "CH выполняет только полной загрузкой сторон в память или grace-merge; "
            "PGSQL использует merge-join и hash-join с потоковой обработкой."
        ),
    ),
    Rule(
        rule_id="pg_ch_join_natural",
        title="NATURAL JOIN (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="JoinExpr",
        kind=Kind.E,
        when=lambda n: "natural" in n.kind,
        rewrite=None,
        message=_E_MSG,
    ),
    Rule(
        rule_id="pg_ch_join_lateral",
        title="LATERAL join (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="JoinExpr",
        kind=Kind.E,
        when=lambda n: n.lateral,
        rewrite=None,
        message=_E_MSG,
    ),
]


_ORDER_BY_RULES: list[Rule] = [
    Rule(
        rule_id="pg_ch_orderby_base",
        title="OrderByItem (базовый проход, тип A)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="OrderByItem",
        kind=Kind.A,
        when=lambda n: True,
        rewrite=None,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_orderby_using",
        title="ORDER BY expression USING operator → expression_function(...) (тип B)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="OrderByItem",
        kind=Kind.B,
        when=lambda n: n.using_op is not None,
        rewrite=None,   # эмиттер рендерит using_op как скалярную функцию
        message=None,
    ),
    Rule(
        rule_id="pg_ch_orderby_nulls",
        title="ORDER BY ... NULLS { FIRST | LAST } (тип C)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="OrderByItem",
        kind=Kind.C,
        when=lambda n: n.nulls is not None,
        rewrite=None,
        message=(
            "Значение по умолчанию различается: PGSQL — NULLS LAST для ASC / "
            "NULLS FIRST для DESC; CH — NULLS LAST всегда. NaN в CH трактуется как NULL."
        ),
    ),
]


_LOCKING_RULES: list[Rule] = [
    Rule(
        rule_id="pg_ch_locking_clause",
        title="FOR {UPDATE|NO KEY UPDATE|SHARE|KEY SHARE} [NOWAIT|SKIP LOCKED] (тип E)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="LockingClause",
        kind=Kind.E,
        when=lambda n: True,
        rewrite=None,
        message=_E_MSG,
    ),
]


def _rewrite_tablesample(n, ctx: TranslateContext):
    """TABLESAMPLE method(arg) [REPEATABLE(seed)] → SAMPLE arg/100."""
    sample = SampleClause()
    sample.node_kind = "SampleClause"
    sample.dialect = Dialect.CLICKHOUSE

    if n.tablesample_args:
        # Конвертируем процент (0–100) в коэффициент (0.0–1.0) через BinaryOp
        divisor = Literal(value=100, literal_kind="int", raw="100")
        divisor.node_kind = "Literal"
        divisor.dialect = Dialect.CLICKHOUSE
        ratio = BinaryOp(op="/", left=n.tablesample_args[0], right=divisor)
        ratio.node_kind = "BinaryOp"
        ratio.dialect = Dialect.CLICKHOUSE
        sample.ratio = ratio

    # REPEATABLE(seed) → SAMPLE OFFSET семантически не совпадают; опускаем
    n.ch_sample = sample
    n.tablesample_method = None
    n.tablesample_args = []
    n.tablesample_repeatable = None
    return n


_TABLE_REF_RULES: list[Rule] = [
    Rule(
        rule_id="pg_ch_tableref_base",
        title="TableRef (базовый проход, тип A)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="TableRef",
        kind=Kind.A,
        when=lambda n: True,
        rewrite=None,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_tableref_tablesample",
        title="TABLESAMPLE method (arg) [REPEATABLE (seed)] → SAMPLE k (тип B)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="TableRef",
        kind=Kind.B,
        when=lambda n: n.tablesample_method is not None,
        rewrite=_rewrite_tablesample,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_tableref_only",
        title="ONLY table_name (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="TableRef",
        kind=Kind.E,
        when=lambda n: n.only,
        rewrite=None,
        message=_E_MSG,
    ),
    Rule(
        rule_id="pg_ch_tableref_descendants_star",
        title="table_name * (суффикс наследников, тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="TableRef",
        kind=Kind.E,
        when=lambda n: n.descendants_star,
        rewrite=None,
        message=_E_MSG,
    ),
    Rule(
        rule_id="pg_ch_tableref_column_aliases",
        title="table_name AS alias (col1, col2, ...) (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="TableRef",
        kind=Kind.E,
        when=lambda n: bool(n.column_aliases),
        rewrite=None,
        message=_E_MSG,
    ),
]


_SUBQUERY_REF_RULES: list[Rule] = [
    Rule(
        rule_id="pg_ch_subqueryref_base",
        title="SubqueryRef (базовый проход, тип A)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="SubqueryRef",
        kind=Kind.A,
        when=lambda n: True,
        rewrite=None,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_subqueryref_lateral",
        title="LATERAL (subquery) (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="SubqueryRef",
        kind=Kind.E,
        when=lambda n: n.lateral,
        rewrite=None,
        message=_E_MSG,
    ),
]


_TABLE_FUNC_REF_RULES: list[Rule] = [
    Rule(
        rule_id="pg_ch_tablefuncref_base",
        title="TableFunctionRef (базовый проход, тип A)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="TableFunctionRef",
        kind=Kind.A,
        when=lambda n: True,
        rewrite=None,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_tablefuncref_lateral",
        title="LATERAL function_name(...) (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="TableFunctionRef",
        kind=Kind.E,
        when=lambda n: n.lateral,
        rewrite=None,
        message=_E_MSG,
    ),
    Rule(
        rule_id="pg_ch_tablefuncref_with_ordinality",
        title="function_name(...) WITH ORDINALITY (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="TableFunctionRef",
        kind=Kind.E,
        when=lambda n: n.with_ordinality,
        rewrite=None,
        message=_E_MSG,
    ),
]


for _rule in (
    _SELECT_RULES
    + _DISTINCT_RULES
    + _WITH_RULES
    + _GROUP_BY_RULES
    + _SETOP_RULES
    + _JOIN_RULES
    + _ORDER_BY_RULES
    + _LOCKING_RULES
    + _TABLE_REF_RULES
    + _SUBQUERY_REF_RULES
    + _TABLE_FUNC_REF_RULES
):
    default_translator.register(_rule)
