"""Правила преобразования арифметических и битовых операторов: PostgreSQL → ClickHouse.
"""
from __future__ import annotations

from src.ast.metadata import Dialect, Kind
from src.ast.nodes import BetweenExpr, BinaryOp, FunctionCall, Identifier, UnaryOp
from src.ast.registry import Rule, TranslateContext, default_translator


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


def _rewrite_pow(n, ctx: TranslateContext):
    """^ (возведение в степень в PG) → pow(a, b)."""
    return _make_fn(n.dialect, "pow", n.left, n.right)


def _rewrite_bitxor(n, ctx: TranslateContext):
    """# (побитовый XOR в PG) → bitXor(a, b)."""
    return _make_fn(n.dialect, "bitXor", n.left, n.right)


def _rewrite_sqrt(n, ctx: TranslateContext):
    """|/ x (квадратный корень) → sqrt(x)."""
    return _make_fn(n.dialect, "sqrt", n.operand)


def _rewrite_cbrt(n, ctx: TranslateContext):
    """||/ x (кубический корень) → cbrt(x)."""
    return _make_fn(n.dialect, "cbrt", n.operand)


def _rewrite_factorial(n, ctx: TranslateContext):
    """x ! (постфиксный факториал) → factorial(x)."""
    return _make_fn(n.dialect, "factorial", n.operand)


_ARITH_RULES: list[Rule] = [
    Rule(
        rule_id="pg_ch_binop_base",
        title="BinaryOp (базовый проход, тип A)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="BinaryOp",
        kind=Kind.A,
        when=lambda n: True,
        rewrite=None,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_binop_add",
        title="+ (переполнение, тип C)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="BinaryOp",
        kind=Kind.C,
        when=lambda n: isinstance(n, BinaryOp) and n.op == "+",
        rewrite=None,
        message=(
            "PostgreSQL бросает ошибку при выходе за границы типа; "
            "ClickHouse использует модульную арифметику (wraparound). "
            "Используйте явный CAST или проверку диапазона."
        ),
    ),
    Rule(
        rule_id="pg_ch_binop_sub",
        title="- (переполнение, тип C)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="BinaryOp",
        kind=Kind.C,
        when=lambda n: isinstance(n, BinaryOp) and n.op == "-",
        rewrite=None,
        message=(
            "PostgreSQL бросает ошибку при выходе за границы типа; "
            "ClickHouse использует модульную арифметику (wraparound). "
            "Используйте явный CAST или проверку диапазона."
        ),
    ),
    Rule(
        rule_id="pg_ch_binop_mul",
        title="* (переполнение, тип C)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="BinaryOp",
        kind=Kind.C,
        when=lambda n: isinstance(n, BinaryOp) and n.op == "*",
        rewrite=None,
        message=(
            "PostgreSQL бросает ошибку при выходе за границы типа; "
            "ClickHouse использует модульную арифметику (wraparound). "
            "Используйте явный CAST или проверку диапазона."
        ),
    ),
    Rule(
        rule_id="pg_ch_binop_div",
        title="/ (семантика деления, тип C)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="BinaryOp",
        kind=Kind.C,
        when=lambda n: isinstance(n, BinaryOp) and n.op == "/",
        rewrite=None,
        message=(
            "Деление: PGSQL возвращает 0 при целочисленном делении (5/2=2), "
            "CH — дробный результат (5/2=2.5); деление на 0 в CH возвращает 0 "
            "(не бросает ошибку). Используйте intDiv() для целочисленного деления."
        ),
    ),
    Rule(
        rule_id="pg_ch_binop_mod",
        title="% (остаток от деления, тип C)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="BinaryOp",
        kind=Kind.C,
        when=lambda n: isinstance(n, BinaryOp) and n.op == "%",
        rewrite=None,
        message=(
            "Остаток: PGSQL бросает ошибку при делении на 0; CH возвращает 0. "
            "Знак результата может различаться для отрицательных операндов."
        ),
    ),
    Rule(
        rule_id="pg_ch_binop_pow",
        title="^ (возведение в степень PG) → pow(a, b) в CH (тип D)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="BinaryOp",
        kind=Kind.D,
        when=lambda n: isinstance(n, BinaryOp) and n.op == "^",
        rewrite=_rewrite_pow,
        message=(
            "В PGSQL ^ — возведение в степень; в CH ^ — побитовый XOR. "
            "Автоматически преобразовано в pow(a, b)."
        ),
    ),
    Rule(
        rule_id="pg_ch_binop_bitxor",
        title="# (побитовый XOR PG) → bitXor(a, b) в CH (тип D)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="BinaryOp",
        kind=Kind.D,
        when=lambda n: isinstance(n, BinaryOp) and n.op == "#",
        rewrite=_rewrite_bitxor,
        message=(
            "В PGSQL # — побитовый XOR; в CH оператор # не определён. "
            "Автоматически преобразовано в bitXor(a, b)."
        ),
    ),
    Rule(
        rule_id="pg_ch_binop_is_distinct",
        title="IS DISTINCT FROM / IS NOT DISTINCT FROM (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="BinaryOp",
        kind=Kind.E,
        when=lambda n: isinstance(n, BinaryOp) and n.op in (
            "IS DISTINCT FROM", "IS NOT DISTINCT FROM"
        ),
        rewrite=None,
        message=(
            "нет аналога в ClickHouse. "
            "В PG IS DISTINCT FROM обрабатывает NULL как обычное значение. "
            "Суррогат: ifNull(a, sentinel) != ifNull(b, sentinel), "
            "но требует выбора значения-замены для NULL."
        ),
    ),
    Rule(
        rule_id="pg_ch_unaryop_base",
        title="UnaryOp (базовый проход, тип A)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="UnaryOp",
        kind=Kind.A,
        when=lambda n: True,
        rewrite=None,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_unaryop_sqrt",
        title="|/ x (квадратный корень PG) → sqrt(x) в CH (тип B)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="UnaryOp",
        kind=Kind.B,
        when=lambda n: isinstance(n, UnaryOp) and n.op == "|/",
        rewrite=_rewrite_sqrt,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_unaryop_cbrt",
        title="||/ x (кубический корень PG) → cbrt(x) в CH (тип B)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="UnaryOp",
        kind=Kind.B,
        when=lambda n: isinstance(n, UnaryOp) and n.op == "||/",
        rewrite=_rewrite_cbrt,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_unaryop_factorial",
        title="x ! (постфиксный факториал PG) → factorial(x) в CH (тип B)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="UnaryOp",
        kind=Kind.B,
        when=lambda n: isinstance(n, UnaryOp) and n.op == "!" and n.position == "postfix",
        rewrite=_rewrite_factorial,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_unaryop_abs",
        title="@ x (модуль числа PG, тип E: нет операторной формы в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="UnaryOp",
        kind=Kind.E,
        when=lambda n: isinstance(n, UnaryOp) and n.op == "@",
        rewrite=None,
        message=(
            "нет аналога в ClickHouse в виде оператора. "
            "Замените на функцию abs(x)."
        ),
    ),
    Rule(
        rule_id="pg_ch_between_base",
        title="BetweenExpr (базовый проход, тип A)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="BetweenExpr",
        kind=Kind.A,
        when=lambda n: True,
        rewrite=None,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_between_symmetric",
        title="BETWEEN SYMMETRIC (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="BetweenExpr",
        kind=Kind.E,
        when=lambda n: isinstance(n, BetweenExpr) and n.symmetric,
        rewrite=None,
        message=(
            "нет аналога в ClickHouse. "
            "PGSQL BETWEEN SYMMETRIC меняет местами границы, если lower > upper. "
            "Суррогат: (x BETWEEN least(a, b) AND greatest(a, b))."
        ),
    ),
]

for _rule in _ARITH_RULES:
    default_translator.register(_rule)
