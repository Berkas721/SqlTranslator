"""Правила преобразования агрегатных функций: PostgreSQL → ClickHouse.
"""
from __future__ import annotations

from src.ast.metadata import Dialect, Kind
from src.ast.nodes import FunctionCall, Identifier, Literal
from src.ast.registry import Rule, TranslateContext, default_translator


def _fn_name(n) -> str:
    if isinstance(n, FunctionCall) and n.name is not None:
        return n.name.name.lower()
    return ""


def _make_fn(dialect: Dialect, name: str, *args) -> FunctionCall:
    fn = FunctionCall()
    fn.node_kind = "FunctionCall"
    fn.dialect = dialect
    ident = Identifier()
    ident.node_kind = "Identifier"
    ident.dialect = dialect
    ident.name = name
    fn.name = ident
    fn.args = list(args)
    return fn


def _make_fn_param(dialect: Dialect, name: str, params: list, args: list) -> FunctionCall:
    """Создаёт параметрический агрегат: name(params...)(args...)."""
    fn = _make_fn(dialect, name, *args)
    fn.parameters = list(params)
    return fn


def _make_lit_int(dialect: Dialect, value: int) -> Literal:
    lit = Literal()
    lit.node_kind = "Literal"
    lit.dialect = dialect
    lit.value = value
    lit.literal_kind = "int"
    lit.raw = str(value)
    return lit


_FILTER_IF_MAP: dict[str, str] = {
    "sum":      "sumIf",
    "count":    "countIf",
    "avg":      "avgIf",
    "min":      "minIf",
    "max":      "maxIf",
    "any":      "anyIf",
    "anylast":  "anyLastIf",
    "anyheavy": "anyHeavyIf",
}


def _rewrite_rename(new_name: str):
    def _rewrite(n, ctx: TranslateContext):
        n.name.name = new_name
        return n
    _rewrite.__name__ = f"_rewrite_to_{new_name}"
    return _rewrite


def _rewrite_bool_and(n, ctx: TranslateContext):
    """bool_and(expr) → min(toUInt8(expr))."""
    to_uint8 = _make_fn(n.dialect, "toUInt8", *n.args)
    return _make_fn(n.dialect, "min", to_uint8)


def _rewrite_bool_or(n, ctx: TranslateContext):
    """bool_or(expr) / every(expr) → max(toUInt8(expr))."""
    to_uint8 = _make_fn(n.dialect, "toUInt8", *n.args)
    return _make_fn(n.dialect, "max", to_uint8)


def _rewrite_string_agg(n, ctx: TranslateContext):
    """string_agg(expr, sep) → arrayStringConcat(groupArray(expr), sep)."""
    if len(n.args) < 2:
        # fallback: rename only
        n.name.name = "arrayStringConcat"
        return n
    expr, sep = n.args[0], n.args[1]
    group_arr = _make_fn(n.dialect, "groupArray", expr)
    return _make_fn(n.dialect, "arrayStringConcat", group_arr, sep)


def _rewrite_array_agg(n, ctx: TranslateContext):
    """array_agg(expr) → groupArray(expr)."""
    n.name.name = "groupArray"
    return n


def _rewrite_percentile_cont(n, ctx: TranslateContext):
    """percentile_cont(f) WITHIN GROUP (ORDER BY x) → quantile(f)(x)."""
    f_param = n.args[0] if n.args else _make_lit_int(n.dialect, 0)
    x_expr = n.within_group[0].expression if n.within_group else None
    result = _make_fn_param(n.dialect, "quantile", [f_param],
                            [x_expr] if x_expr is not None else [])
    result.within_group = []
    return result


def _rewrite_percentile_disc(n, ctx: TranslateContext):
    """percentile_disc(f) WITHIN GROUP (ORDER BY x) → quantileExact(f)(x)."""
    f_param = n.args[0] if n.args else _make_lit_int(n.dialect, 0)
    x_expr = n.within_group[0].expression if n.within_group else None
    result = _make_fn_param(n.dialect, "quantileExact", [f_param],
                            [x_expr] if x_expr is not None else [])
    result.within_group = []
    return result


def _rewrite_mode(n, ctx: TranslateContext):
    """mode() WITHIN GROUP (ORDER BY x) → arrayElement(topK(1)(x), 1).
    """
    x_expr = n.within_group[0].expression if n.within_group else _make_lit_int(n.dialect, 0)
    lit1 = _make_lit_int(n.dialect, 1)
    # topK(1)(x) — параметрический агрегат
    topk = _make_fn_param(n.dialect, "topK", [lit1], [x_expr])
    # arrayElement(topK(1)(x), 1) — первый элемент массива топ-1
    lit1_idx = _make_lit_int(n.dialect, 1)
    result = _make_fn(n.dialect, "arrayElement", topk, lit1_idx)
    return result


def _rewrite_filter_clause(n, ctx: TranslateContext):
    """agg(expr) FILTER (WHERE cond) → aggIf(expr, cond).
    """
    cond = n.filter_where
    fn_lower = n.name.name.lower()
    new_name = _FILTER_IF_MAP.get(fn_lower)
    if new_name:
        n.name.name = new_name
    n.args.append(cond)
    n.filter_where = None
    return n


_AGG_FN_RULES: list[Rule] = [
    Rule(
        rule_id="pg_ch_fn_bool_and",
        title="bool_and(expr) → min(toUInt8(expr)) (тип B)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.B,
        when=lambda n: _fn_name(n) == "bool_and",
        rewrite=_rewrite_bool_and,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_fn_bool_or",
        title="bool_or(expr) / every(expr) → max(toUInt8(expr)) (тип B)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.B,
        when=lambda n: _fn_name(n) in ("bool_or", "every"),
        rewrite=_rewrite_bool_or,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_fn_bit_and",
        title="bit_and(x) → groupBitAnd(x) (тип B)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.B,
        when=lambda n: _fn_name(n) == "bit_and",
        rewrite=_rewrite_rename("groupBitAnd"),
        message=None,
    ),
    Rule(
        rule_id="pg_ch_fn_bit_or",
        title="bit_or(x) → groupBitOr(x) (тип B)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.B,
        when=lambda n: _fn_name(n) == "bit_or",
        rewrite=_rewrite_rename("groupBitOr"),
        message=None,
    ),
    Rule(
        rule_id="pg_ch_fn_bit_xor",
        title="bit_xor(x) → groupBitXor(x) (тип B)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.B,
        when=lambda n: _fn_name(n) == "bit_xor",
        rewrite=_rewrite_rename("groupBitXor"),
        message=None,
    ),
    Rule(
        rule_id="pg_ch_fn_string_agg",
        title="string_agg(expr, sep) → arrayStringConcat(groupArray(expr), sep) (тип B)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.B,
        when=lambda n: _fn_name(n) == "string_agg",
        rewrite=_rewrite_string_agg,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_fn_avg",
        title="avg(expr) — Float64 vs numeric (тип C)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.C,
        when=lambda n: _fn_name(n) == "avg",
        rewrite=None,
        message=(
            "avg() в PGSQL для integer/bigint возвращает numeric (произвольная точность); "
            "в CH — Float64, что может привести к потере точности на больших значениях."
        ),
    ),
    Rule(
        rule_id="pg_ch_fn_stddev_family",
        title="stddev/variance-семейство — Float64 vs numeric (тип C)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.C,
        when=lambda n: _fn_name(n) in (
            "stddev", "stddev_samp", "stddev_pop",
            "variance", "var_samp", "var_pop",
        ),
        rewrite=None,
        message=(
            "Тип результата различается: PGSQL возвращает numeric (произвольная точность); "
            "CH — Float64, точность может различаться на больших выборках. "
            "CH-имена: stddevSamp / stddevPop / varSamp / varPop "
            "(snake_case-синонимы также распознаются)."
        ),
    ),
    Rule(
        rule_id="pg_ch_fn_array_agg",
        title="array_agg(expr) → groupArray(expr) (тип D)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.D,
        when=lambda n: _fn_name(n) == "array_agg",
        rewrite=_rewrite_array_agg,
        message=(
            "array_agg в PGSQL сохраняет NULL-элементы; CH groupArray пропускает NULL. "
            "Для сохранения: groupArray(toNullable(expr)). "
            "Порядок элементов не гарантирован без явного arraySort() или ORDER BY."
        ),
    ),
    Rule(
        rule_id="pg_ch_fn_percentile_cont",
        title="percentile_cont(f) WITHIN GROUP (ORDER BY x) → quantile(f)(x) (тип D)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.D,
        when=lambda n: _fn_name(n) == "percentile_cont",
        rewrite=_rewrite_percentile_cont,
        message=(
            "Синтаксис параметрического агрегата отличается: "
            "PGSQL percentile_cont(f) WITHIN GROUP (ORDER BY x); "
            "CH quantile(f)(x) — параметр f в первых скобках, аргумент x во вторых. "
            "Клауза WITHIN GROUP не используется."
        ),
    ),
    Rule(
        rule_id="pg_ch_fn_percentile_disc",
        title="percentile_disc(f) WITHIN GROUP (ORDER BY x) → quantileExact(f)(x) (тип D)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.D,
        when=lambda n: _fn_name(n) == "percentile_disc",
        rewrite=_rewrite_percentile_disc,
        message=(
            "Синтаксис параметрического агрегата отличается: "
            "PGSQL percentile_disc(f) WITHIN GROUP (ORDER BY x); "
            "CH quantileExact(f)(x) — дискретная квантиль, параметр f в первых скобках. "
            "Клауза WITHIN GROUP не используется."
        ),
    ),
    Rule(
        rule_id="pg_ch_fn_mode",
        title="mode() WITHIN GROUP (ORDER BY x) → arrayElement(topK(1)(x), 1) (тип D)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.D,
        when=lambda n: _fn_name(n) == "mode",
        rewrite=_rewrite_mode,
        message=(
            "Нет точного аналога в ClickHouse. "
            "Преобразовано в arrayElement(topK(1)(x), 1): "
            "topK — вероятностный алгоритм, не гарантирует точного режима на малых выборках. "
            "Для точного результата используйте GROUP BY + COUNT(*) + argMax()."
        ),
    ),
    Rule(
        rule_id="pg_ch_fn_filter_clause",
        title="agg(expr) FILTER (WHERE cond) → aggIf(expr, cond) (тип D)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.D,
        when=lambda n: (
            isinstance(n, FunctionCall)
            and n.filter_where is not None
            and n.over is None   # только агрегатный контекст, не оконный
        ),
        rewrite=_rewrite_filter_clause,
        message=(
            "Клауза FILTER (WHERE ...) не поддерживается в CH для агрегатных функций. "
            "Преобразовано: условие перенесено в последний аргумент, "
            "функция переименована с суффиксом -If (sumIf, countIf, avgIf и т.д.). "
            "Для нераспознанных агрегатов выполните замену вручную."
        ),
    ),
    Rule(
        rule_id="pg_ch_fn_json_agg",
        title="json_agg / jsonb_agg / json_object_agg / jsonb_object_agg (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.E,
        when=lambda n: _fn_name(n) in (
            "json_agg", "jsonb_agg",
            "json_object_agg", "jsonb_object_agg",
        ),
        rewrite=None,
        message=(
            "нет прямого аналога в ClickHouse. "
            "Частичный суррогат: toJSONString(groupArray(x)) для json_agg; "
            "для json_object_agg — groupArray([key, value]) + toJSONString()."
        ),
    ),
]

for _rule in _AGG_FN_RULES:
    default_translator.register(_rule)
