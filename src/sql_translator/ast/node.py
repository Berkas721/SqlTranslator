from __future__ import annotations
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional
from uuid import uuid4

from .metadata import Annotation, AnnotationRecord, Dialect, Kind, SourceComment, Span
from .registry import TranslateContext, Translator, default_translator

_MISSING = object()


@dataclass(slots=True)
class Node:
    node_kind: str = field(init=False)
    node_id:   str = field(default_factory=lambda: uuid4().hex[:8])

    source_span: Optional[Span] = None   # исходный фрагмент (заполняет парсер)
    output_span: Optional[Span] = None   # выходной фрагмент (заполняет эмиттер)

    comments:    list[SourceComment] = field(default_factory=list)
    annotations: list[Annotation]    = field(default_factory=list)

    dialect: Dialect = Dialect.COMMON

    extensions: dict[str, dict[str, Any]] = field(default_factory=dict)

    def children(self) -> list[Node]:
        """Непосредственные дочерние узлы."""
        out: list[Node] = []
        for f in self.__dataclass_fields__:
            v = getattr(self, f, None)   # None для неинициализированных слотов
            if isinstance(v, Node):
                out.append(v)
            elif isinstance(v, list):
                out.extend(x for x in v if isinstance(x, Node))
        return out

    def walk(self) -> Iterable[tuple[Optional[Node], Node]]:
        """Итератор в глубину: yields (parent, node)."""
        yield (None, self)
        stack: list[tuple[Optional[Node], Node]] = [
            (self, c) for c in self.children()
        ]
        while stack:
            parent, node = stack.pop()
            yield (parent, node)
            stack.extend((node, c) for c in node.children())

    def translate_to(
        self,
        target: Dialect,
        translator: Translator = default_translator,
        ctx: Optional[TranslateContext] = None,
    ) -> Node:
        """Возвращает новое поддерево, полученное рекурсивным применением
        правил преобразования к каждому узлу (post-order).

        Алгоритм:
          1. Создаётся мелкая копия текущего узла;
          2. Рекурсивно транслируются потомки копии;
          3. К узлу с уже транслированными потомками применяются правила
             из реестра translator (см. registry.py);
          4. На узле выставляется dialect=target и накапливаются аннотации;
          5. Результат возвращается вверх.
        """
        if ctx is None:
            ctx = TranslateContext(
                source_dialect=self.dialect,
                target_dialect=target,
                translator=translator,
            )
        clone = self._clone_shallow()
        clone._translate_children(target, translator, ctx)
        return translator.apply(clone, target, ctx)

    def translate_to_postgres(
        self,
        translator: Translator = default_translator,
    ) -> Node:
        raise NotImplementedError("translate_to_postgres not implemented yet")

    def translate_to_clickhouse(
        self,
        translator: Translator = default_translator,
    ) -> Node:
        from .rules import clickhouse as _  # noqa: F401
        return self.translate_to(Dialect.CLICKHOUSE, translator)

    def collect_annotations(
        self,
        space: str = "output",
        kinds: Optional[set[Kind]] = None,
    ) -> list[AnnotationRecord]:
        """Возвращает все аннотации преобразования в этом поддереве в виде
        плоского списка записей (тип, комментарий, координаты).

        Args:
          space: 'output' — координаты в выходном SQL (после эмиссии),
                 'source' — координаты в исходном SQL.
          kinds: опциональный фильтр по типам (например, {Kind.C, Kind.D, Kind.E}).
        """
        records: list[AnnotationRecord] = []
        for _, node in self.walk():
            for ann in node.annotations:
                if kinds is not None and ann.kind not in kinds:
                    continue
                span = ann.output_span if space == "output" else ann.source_span
                records.append(AnnotationRecord(
                    kind=ann.kind,
                    comment=ann.message or ann.title,
                    span=span,
                    rule_id=ann.rule_id,
                    title=ann.title,
                    node_id=node.node_id,
                    node_kind=node.node_kind,
                ))
        records.sort(key=lambda r: r.span.start.offset if r.span else float("inf"))
        return records

    def _clone_shallow(self) -> Node:
        """Мелкая копия узла для использования в translate_to.
        """
        cls = type(self)
        clone = object.__new__(cls)
        for fname in self.__dataclass_fields__:
            if fname == "node_id":
                object.__setattr__(clone, fname, uuid4().hex[:8])
                continue
            if fname == "annotations":
                object.__setattr__(clone, fname, [])
                continue
            val = getattr(self, fname, _MISSING)
            if val is _MISSING:
                continue
            if isinstance(val, list):
                object.__setattr__(clone, fname, list(val))
            else:
                object.__setattr__(clone, fname, val)
        return clone

    def _translate_children(
        self,
        target: Dialect,
        translator: Translator,
        ctx: TranslateContext,
    ) -> None:
        """Рекурсивная трансляция потомков на месте (изменяет копию узла).

        Обходит все слоты: Node-значения заменяются их транслированными версиями,
        list-поля обновляются только если содержат хотя бы один Node-элемент.
        Нe-Node поля (Span, str, Dialect, Annotation, SourceComment, …) не трогаются.
        """
        for fname in self.__dataclass_fields__:
            val = getattr(self, fname, _MISSING)
            if val is _MISSING:
                continue
            if isinstance(val, Node):
                object.__setattr__(
                    self, fname, val.translate_to(target, translator, ctx)
                )
            elif isinstance(val, list) and any(isinstance(x, Node) for x in val):
                object.__setattr__(self, fname, [
                    x.translate_to(target, translator, ctx) if isinstance(x, Node) else x
                    for x in val
                ])
