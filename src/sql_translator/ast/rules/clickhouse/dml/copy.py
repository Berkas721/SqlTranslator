"""Правила преобразования COPY: PostgreSQL → ClickHouse.
"""
from __future__ import annotations

from src.ast.metadata import Dialect, Kind
from src.ast.registry import Rule, TranslateContext, default_translator

_E_MSG = "нет аналога в ClickHouse"


def _rewrite_copy_from_file(n, ctx: TranslateContext):
    """COPY table FROM 'filename' → INSERT INTO table FROM INFILE 'filename' FORMAT ..."""
    n.ch_from_infile = n.filename
    n.ch_format = n.format or "CSV"
    return n


def _rewrite_copy_from_stdin(n, ctx: TranslateContext):
    """COPY table FROM STDIN → INSERT INTO table FORMAT ... (без INFILE)."""
    n.ch_format = n.format or "CSV"
    return n


def _rewrite_copy_to_file(n, ctx: TranslateContext):
    """COPY {table|(query)} TO 'filename' → SELECT ... INTO OUTFILE 'filename' FORMAT ..."""
    n.ch_into_outfile = n.filename
    n.ch_format = n.format or "CSV"
    return n


_COPY_RULES: list[Rule] = [
    Rule(
        rule_id="pg_ch_copy_base",
        title="CopyStmt (базовый проход, тип A)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CopyStmt",
        kind=Kind.A,
        when=lambda n: True,
        rewrite=None,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_copy_from_file",
        title="COPY table FROM 'filename' → INSERT INTO table FROM INFILE 'filename' FORMAT ... (тип B)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CopyStmt",
        kind=Kind.B,
        when=lambda n: n.direction == "FROM" and n.filename is not None,
        rewrite=_rewrite_copy_from_file,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_copy_from_stdin",
        title="COPY table FROM STDIN → INSERT INTO table FORMAT ... (тип B)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CopyStmt",
        kind=Kind.B,
        when=lambda n: n.direction == "FROM" and n.stdin,
        rewrite=_rewrite_copy_from_stdin,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_copy_to_file",
        title="COPY {table|(query)} TO 'filename' → SELECT ... INTO OUTFILE 'filename' FORMAT ... (тип B)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CopyStmt",
        kind=Kind.B,
        when=lambda n: n.direction == "TO" and n.filename is not None,
        rewrite=_rewrite_copy_to_file,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_copy_options_session",
        title="DELIMITER|QUOTE|ESCAPE|NULL|HEADER|ENCODING → настройки сессии (тип B)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CopyStmt",
        kind=Kind.B,
        when=lambda n: any([
            n.delimiter,
            n.quote_char,
            n.escape_char,
            n.null_str,
            n.header is not None,
            n.encoding,
        ]),
        rewrite=None,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_copy_format",
        title="FORMAT format_name (тип D)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CopyStmt",
        kind=Kind.D,
        when=lambda n: n.format is not None,
        rewrite=None,
        message=(
            "Наборы форматов не пересекаются полностью: PGSQL — text, csv, binary; "
            "CH — 70+ форматов. Бинарный PGSQL несовместим с форматами CH."
        ),
    ),
    Rule(
        rule_id="pg_ch_copy_on_error",
        title="ON_ERROR / REJECT_LIMIT → настройки сессии (тип D)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CopyStmt",
        kind=Kind.D,
        when=lambda n: n.on_error is not None or n.reject_limit is not None,
        rewrite=None,
        message=(
            "В CH пороги задаются настройкой сессии "
            "(input_format_allow_errors_num / input_format_allow_errors_ratio), "
            "не внутри команды."
        ),
    ),
    Rule(
        rule_id="pg_ch_copy_program",
        title="FROM/TO PROGRAM 'command' (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CopyStmt",
        kind=Kind.E,
        when=lambda n: n.program is not None,
        rewrite=None,
        message=_E_MSG,
    ),
    Rule(
        rule_id="pg_ch_copy_where",
        title="WHERE condition в COPY FROM (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CopyStmt",
        kind=Kind.E,
        when=lambda n: n.where is not None,
        rewrite=None,
        message=_E_MSG,
    ),
    Rule(
        rule_id="pg_ch_copy_freeze",
        title="FREEZE (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CopyStmt",
        kind=Kind.E,
        when=lambda n: n.freeze is not None,
        rewrite=None,
        message=_E_MSG,
    ),
    Rule(
        rule_id="pg_ch_copy_header_match",
        title="HEADER MATCH (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CopyStmt",
        kind=Kind.E,
        when=lambda n: n.header_match,
        rewrite=None,
        message=_E_MSG,
    ),
    Rule(
        rule_id="pg_ch_copy_force_quote",
        title="FORCE_QUOTE { (cols) | * } (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CopyStmt",
        kind=Kind.E,
        when=lambda n: bool(n.force_quote),
        rewrite=None,
        message=_E_MSG,
    ),
    Rule(
        rule_id="pg_ch_copy_force_not_null",
        title="FORCE_NOT_NULL { (cols) } (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CopyStmt",
        kind=Kind.E,
        when=lambda n: bool(n.force_not_null),
        rewrite=None,
        message=_E_MSG,
    ),
    Rule(
        rule_id="pg_ch_copy_force_null",
        title="FORCE_NULL { (cols) } (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CopyStmt",
        kind=Kind.E,
        when=lambda n: bool(n.force_null),
        rewrite=None,
        message=_E_MSG,
    ),
    Rule(
        rule_id="pg_ch_copy_log_verbosity",
        title="LOG_VERBOSITY verbosity (тип E: нет аналога в CH)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CopyStmt",
        kind=Kind.E,
        when=lambda n: n.log_verbosity is not None,
        rewrite=None,
        message=_E_MSG,
    ),
]

for _rule in _COPY_RULES:
    default_translator.register(_rule)
