"""
FastAPI-сервис для трансляции SQL: PostgreSQL -> ClickHouse.
Запуск из корня проекта (с активированным .venv): uvicorn sql_translator.api.app:app --host 0.0.0.0 --port 8000
"""
from __future__ import annotations

from typing import Optional

from fastapi import Body, FastAPI, HTTPException, Query
from pydantic import BaseModel

from sql_translator.emitters.clickhouse import emit_sql
from sql_translator.parser import parse_sql

app = FastAPI(title="SQL Translator", version="1.0.0")

class Position(BaseModel):
    offset: int
    line: int
    column: int


class Span(BaseModel):
    start: Position
    end: Position


class AnnotationOut(BaseModel):
    kind: str
    comment: str
    span: Optional[Span] = None


class TranslationResponse(BaseModel):
    sql: str
    annotations: list[AnnotationOut]


@app.post("/translate", response_model=TranslationResponse)
async def translate(
    source_dialect: str = Query(default="postgres"),
    target_dialect: str = Query(default="clickhouse"),
    body: bytes = Body(..., media_type="text/plain"),
) -> TranslationResponse:
    """Принимает SQL-текст, возвращает переведённый SQL и аннотации"""
    sql_text = body.decode("utf-8")

    try:
        script = parse_sql(sql_text, dialect=source_dialect)
    except Exception as exc:
        raise HTTPException(status_code=400, detail=f"Parse error: {exc}") from exc

    if target_dialect == "clickhouse":
        translated = script.translate_to_clickhouse()
    else:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported target dialect: {target_dialect!r}",
        )

    output_sql = emit_sql(translated)
    records = translated.collect_annotations(space="output")

    return TranslationResponse(
        sql=output_sql,
        annotations=[
            AnnotationOut(
                kind=r.kind.value,
                comment=r.comment,
                span=Span(
                    start=Position(
                        offset=r.span.start.offset,
                        line=r.span.start.line,
                        column=r.span.start.column,
                    ),
                    end=Position(
                        offset=r.span.end.offset,
                        line=r.span.end.line,
                        column=r.span.end.column,
                    ),
                )
                if r.span is not None
                else None,
            )
            for r in records
        ],
    )
