"""Правила преобразования числовых и математических функций: PostgreSQL → ClickHouse.
"""
from __future__ import annotations

from src.ast.metadata import Dialect, Kind
from src.ast.nodes import BinaryOp, FunctionCall, Identifier
from src.ast.registry import Rule, TranslateContext, default_translator


def _fn_name(n) -> str:
    if isinstance(n, FunctionCall) and n.name is not None:
        return n.name.name.lower()
    return ""


def _fn_nargs(n) -> int:
    return len(n.args) if isinstance(n, FunctionCall) else 0


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


def _rewrite_rename(new_name: str):
    def _rewrite(n, ctx: TranslateContext):
        n.name.name = new_name
        return n
    _rewrite.__name__ = f"_rewrite_to_{new_name}"
    return _rewrite


def _rewrite_log1(n, ctx: TranslateContext):
    """log(x) в PG — log10; заменяем на log10(x) в CH."""
    n.name.name = "log10"
    return n


def _rewrite_log2(n, ctx: TranslateContext):
    b_expr = n.args[0]   # основание
    x_expr = n.args[1]   # аргумент
    log_x = _make_fn(n.dialect, "log", x_expr)
    log_b = _make_fn(n.dialect, "log", b_expr)
    result = BinaryOp()
    result.node_kind = "BinaryOp"
    result.dialect = n.dialect
    result.op = "/"
    result.left = log_x
    result.right = log_b
    return result


_MATH_FN_RULES: list[Rule] = [
    Rule(
        rule_id="pg_ch_fn_power",
        title="power(x, y) → pow(x, y) (тип B)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.B,
        when=lambda n: _fn_name(n) == "power",
        rewrite=_rewrite_rename("pow"),
        message=None,
    ),
    Rule(
        rule_id="pg_ch_fn_mod",
        title="mod(x, y) → modulo(x, y) (тип B)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.B,
        when=lambda n: _fn_name(n) == "mod",
        rewrite=_rewrite_rename("modulo"),
        message=None,
    ),
    Rule(
        rule_id="pg_ch_fn_div",
        title="div(y, x) → intDiv(y, x) (тип B)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.B,
        when=lambda n: _fn_name(n) == "div",
        rewrite=_rewrite_rename("intDiv"),
        message=None,
    ),
    Rule(
        rule_id="pg_ch_fn_random",
        title="random() → randCanonical() (тип B)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.B,
        when=lambda n: _fn_name(n) == "random",
        rewrite=_rewrite_rename("randCanonical"),
        message=None,
    ),
    Rule(
        rule_id="pg_ch_fn_round",
        title="round(x[, n]) — режим округления (тип C)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.C,
        when=lambda n: _fn_name(n) == "round",
        rewrite=None,
        message=(
            "Режим округления различается: "
            "PGSQL round(numeric) — от нуля (half-up); round(double precision) — к чётному (half-to-even). "
            "CH round() — всегда к чётному (half-to-even). "
            "Для явного управления режимом используйте roundBankers(), roundHalfUp() и т.д."
        ),
    ),
    Rule(
        rule_id="pg_ch_fn_log1",
        title="log(x) — КРИТИЧНО: PGSQL log10, CH ln (тип D)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.D,
        when=lambda n: _fn_name(n) == "log" and _fn_nargs(n) == 1,
        rewrite=_rewrite_log1,
        message=(
            "КРИТИЧНО: log(x) в PGSQL — десятичный логарифм (log₁₀); "
            "log(x) в CH — натуральный логарифм (ln). "
            "log(100) в PGSQL = 2, в CH ≈ 4.605. "
            "Автоматически преобразовано в log10(x)."
        ),
    ),
    Rule(
        rule_id="pg_ch_fn_log2arg",
        title="log(b, x) — двухаргументная форма (тип D)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.D,
        when=lambda n: _fn_name(n) == "log" and _fn_nargs(n) == 2,
        rewrite=_rewrite_log2,
        message=(
            "Двухаргументная форма log(b, x) — логарифм по основанию b — "
            "в CH не поддерживается. "
            "Преобразовано в log(x) / log(b) через формулу смены основания."
        ),
    ),
    Rule(
        rule_id="pg_ch_fn_width_bucket",
        title="width_bucket(...) (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.E,
        when=lambda n: _fn_name(n) == "width_bucket",
        rewrite=None,
        message=(
            "нет аналога в ClickHouse. "
            "Суррогат: ceil((x - lo) / (hi - lo) * n) для равномерных корзин; "
            "для произвольных границ — arrayFirstIndex()."
        ),
    ),
    Rule(
        rule_id="pg_ch_fn_gcd_lcm",
        title="gcd / lcm (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.E,
        when=lambda n: _fn_name(n) in ("gcd", "lcm"),
        rewrite=None,
        message=(
            "нет аналога в ClickHouse. "
            "НОД/НОК не реализованы как встроенные функции; реализуйте через UDF."
        ),
    ),
    Rule(
        rule_id="pg_ch_fn_setseed",
        title="setseed(x) (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.E,
        when=lambda n: _fn_name(n) == "setseed",
        rewrite=None,
        message=(
            "нет аналога в ClickHouse. "
            "CH не поддерживает установку seed для генератора случайных чисел на уровне SQL."
        ),
    ),
]

for _rule in _MATH_FN_RULES:
    default_translator.register(_rule)
