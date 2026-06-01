from __future__ import annotations
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Callable, Optional

from .metadata import Annotation, Dialect, Kind

if TYPE_CHECKING:
    from .node import Node

@dataclass(slots=True)
class Rule:
    rule_id:   str
    title:     str
    source:    Dialect            # диалект, с которого преобразует
    target:    Dialect            # диалект, на который преобразует
    node_kind: str                # к какому типу узла применимо
    kind:      Kind               # тип преобразования (A/B/C/D/E)
    when:      Callable[[Node], bool] = lambda n: True
    rewrite:   Optional[Callable[[Node, TranslateContext], Node]] = None
    message:   Optional[str] = None


@dataclass(slots=True)
class TranslateContext:
    """Разделяемое состояние на время одной трансляции дерева."""
    source_dialect: Dialect
    target_dialect: Dialect
    translator:     Translator
    counters:       dict[str, int] = field(default_factory=dict)


class Translator:
    """Глобальный реестр правил + движок применения."""
    def __init__(self) -> None:
        self._rules: dict[tuple[Dialect, Dialect, str], list[Rule]] = {}

    def register(self, rule: Rule) -> None:
        key = (rule.source, rule.target, rule.node_kind)
        self._rules.setdefault(key, []).append(rule)

    def rules_for(
        self,
        src: Dialect,
        tgt: Dialect,
        kind: str,
    ) -> list[Rule]:
        exact  = self._rules.get((src, tgt, kind), [])
        common = self._rules.get((Dialect.COMMON, tgt, kind), [])
        return exact + common

    def apply(
        self,
        node: Node,
        target: Dialect,
        ctx: TranslateContext,
    ) -> Node:
        """Применяет все подходящие правила к узлу.

        Обход потомков — ответственность Node.translate_to (см. node.py).

        Если для данного node_kind зарегистрировано хотя бы одно правило,
        но ни одно не сработало, добавляется аннотация Kind.F — «неизвестный
        инструменту элемент синтаксиса». Для node_kind без правил (SelectStmt
        и т.п.) аннотация F не добавляется.
        """
        current = node
        applicable_rules = self.rules_for(current.dialect, target, current.node_kind)
        matched = False
        for rule in applicable_rules:
            if rule.when(current):
                matched = True
                if rule.rewrite is not None:
                    current = rule.rewrite(current, ctx)
                if rule.message is not None or rule.kind in (Kind.C, Kind.D, Kind.E):
                    current.annotations.append(Annotation(
                        kind=rule.kind,
                        rule_id=rule.rule_id,
                        title=rule.title,
                        message=rule.message,
                        source_span=node.source_span,
                    ))
        if not matched and applicable_rules and node.dialect == Dialect.POSTGRES:
            current.annotations.append(Annotation(
                kind=Kind.F,
                rule_id="pg_ch.fallback",
                title="Неизвестный элемент синтаксиса",
                message="неизвестный инструменту элемент синтаксиса",
                source_span=node.source_span,
            ))
        current.dialect = (
            target if current.dialect != Dialect.COMMON else Dialect.COMMON
        )
        return current


# Глобальный экземпляр — к нему обращается Node.translate_to по умолчанию
default_translator = Translator()
