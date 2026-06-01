"""Правила преобразования условных выражений и функций: PostgreSQL → ClickHouse.

Глава 2.1.4.3 «Различия postgresql и clickhouse.docx».

Охват:
  CaseExpr     — CASE WHEN … END (порядок вычисления ветвей)
  FunctionCall — coalesce (семантика NULL), greatest/least (NULL-поведение),
                 decode (нет аналога)
"""
from __future__ import annotations

from src.ast.metadata import Dialect, Kind
from src.ast.nodes import CaseExpr, FunctionCall
from src.ast.registry import Rule, TranslateContext, default_translator


def _fn_name(n) -> str:
    """Безопасно возвращает нижний регистр имени функции."""
    if isinstance(n, FunctionCall) and n.name is not None:
        return n.name.name.lower()
    return ""


_COND_RULES: list[Rule] = [
    Rule(
        rule_id="pg_ch_case_short_circuit",
        title="CASE WHEN … END (порядок вычисления ветвей, тип C)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CaseExpr",
        kind=Kind.C,
        when=lambda n: True,
        rewrite=None,
        message=(
            "Порядок вычисления ветвей различается: "
            "PGSQL вычисляет WHEN-условия лениво (короткое замыкание) "
            "и гарантирует, что THEN-выражение вычисляется только если условие истинно; "
            "CH вычисляет все ветви заранее (eager evaluation). "
            "Выражения с побочными эффектами или делением на 0 в THEN могут вести себя иначе."
        ),
    ),


    Rule(
        rule_id="pg_ch_fn_base",
        title="FunctionCall (базовый проход, тип A)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.A,
        when=lambda n: True,
        rewrite=None,
        message=None,
    ),

    # Тип C: coalesce — различия в пропагации NULL и вычислении

    Rule(
        rule_id="pg_ch_fn_coalesce",
        title="coalesce(...) — семантика NULL и порядок вычисления (тип C)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.C,
        when=lambda n: _fn_name(n) == "coalesce",
        rewrite=None,
        message=(
            "coalesce в CH вычисляет все аргументы до выбора первого не-NULL "
            "(eager evaluation); в PGSQL вычисление останавливается на первом не-NULL. "
            "Аргументы с побочными эффектами или потенциальными ошибками "
            "(деление на 0, обращение к несуществующей строке) могут вести себя иначе. "
            "Рассмотрите замену на if(isNotNull(a), a, b)."
        ),
    ),

    # Тип D: greatest / least — обработка NULL

    Rule(
        rule_id="pg_ch_fn_greatest",
        title="greatest(...) — обработка NULL (тип D)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.D,
        when=lambda n: _fn_name(n) == "greatest",
        rewrite=None,
        message=(
            "greatest в PGSQL игнорирует NULL-аргументы и возвращает наибольший не-NULL; "
            "в CH NULL в аргументах приводит к NULL-результату (SQL-стандартное поведение). "
            "Используйте greatestIgnoreNull() из contrib или явный COALESCE."
        ),
    ),
    Rule(
        rule_id="pg_ch_fn_least",
        title="least(...) — обработка NULL (тип D)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.D,
        when=lambda n: _fn_name(n) == "least",
        rewrite=None,
        message=(
            "least в PGSQL игнорирует NULL-аргументы и возвращает наименьший не-NULL; "
            "в CH NULL в аргументах приводит к NULL-результату (SQL-стандартное поведение). "
            "Используйте leastIgnoreNull() из contrib или явный COALESCE."
        ),
    ),

    # Тип E: decode — нет аналога в CH

    Rule(
        rule_id="pg_ch_fn_decode",
        title="decode(str, format) (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="FunctionCall",
        kind=Kind.E,
        when=lambda n: _fn_name(n) == "decode",
        rewrite=None,
        message=(
            "нет аналога в ClickHouse. "
            "В PGSQL decode(string, format) декодирует бинарные данные (base64/hex/escape); "
            "в CH используйте base64Decode(), unhex() или reinterpretAsString() "
            "в зависимости от формата."
        ),
    ),
]

for _rule in _COND_RULES:
    default_translator.register(_rule)
