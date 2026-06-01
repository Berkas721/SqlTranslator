"""ClickHouse SQL emitter: AST → SQL text.

Usage:
    from src.emitters.clickhouse import emit_sql

    ch_script = parse_sql(sql).translate_to_clickhouse()
    sql_text = emit_sql(ch_script)
"""
from .emitter import ClickHouseEmitter

__all__ = ["ClickHouseEmitter", "emit_sql"]


def emit_sql(node, indent: int = 4) -> str:
    """Convert a ClickHouse-dialect AST node (or Script) to SQL text.

    Also fills ``node.output_span`` (and recursively all descendant spans)
    so that ``collect_annotations(space='output')`` returns correct coordinates.

    Args:
        node: Any Node — typically a Script or a single Statement.
        indent: spaces per indentation level (default 4).

    Returns:
        SQL string.
    """
    em = ClickHouseEmitter(indent=indent)
    em.emit(node)
    return em.result()
