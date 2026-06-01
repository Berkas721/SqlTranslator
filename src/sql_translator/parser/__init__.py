"""Парсер SQL → AST нашей разработки.

    from src.parser import parse_sql
    script = parse_sql("SELECT 1", dialect="postgres")
"""
from .from_pglast import parse_sql

__all__ = ["parse_sql"]
