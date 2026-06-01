from __future__ import annotations
from dataclasses import dataclass
from enum import Enum
from typing import Optional

@dataclass(frozen=True, slots=True)
class Position:
    offset: int   # смещение в символах от начала документа (0-based)
    line:   int
    column: int


@dataclass(frozen=True, slots=True)
class Span:
    start: Position
    end:   Position   # позиция после последнего символа фрагмента

    @property
    def length(self) -> int:
        return self.end.offset - self.start.offset


class CommentKind(Enum):
    LINE  = "--"
    BLOCK = "/* */"


class CommentPlacement(Enum):
    LEADING  = "leading"
    TRAILING = "trailing"
    INLINE   = "inline"


@dataclass(slots=True)
class SourceComment:
    text:      str
    kind:      CommentKind
    placement: CommentPlacement
    location:  Span


class Kind(Enum):
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"


@dataclass(slots=True)
class Annotation:
    kind:        Kind
    rule_id:     str
    title:       str
    message:     Optional[str] = None
    source_span: Optional[Span] = None
    output_span: Optional[Span] = None


@dataclass(slots=True, frozen=True)
class AnnotationRecord:
    """Плоская запись для коллекции аннотаций преобразования."""
    kind:      Kind
    comment:   str
    span:      Optional[Span]
    rule_id:   str
    title:     str
    node_id:   str
    node_kind: str


class Dialect(Enum):
    COMMON     = "common"
    POSTGRES   = "postgres"
    CLICKHOUSE = "clickhouse"
