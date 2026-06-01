from __future__ import annotations

from typing import Callable, Optional

from src.ast.metadata import Position, Span
from src.ast.node import Node
from src.ast.nodes import (
    AlterRoleStmt,
    ArrayConstructor,
    BeginStmt,
    BetweenExpr,
    BinaryOp,
    Cast,
    CaseExpr,
    ColumnConstraint,
    ColumnDef,
    CommitStmt,
    CommonTableExpr,
    CopyStmt,
    CreateDatabaseStmt,
    CreateFunctionStmt,
    CreateIndexStmt,
    CreateRoleStmt,
    CreateTableStmt,
    CreateUserStmt,
    CreateViewStmt,
    DefaultValues,
    DistinctClause,
    EngineSpec,
    FrameBound,
    FrameSpec,
    FunctionCall,
    GrantStmt,
    GroupByClause,
    Identifier,
    IndexColumn,
    InsertStmt,
    JoinExpr,
    LikeClause,
    LikeExpr,
    Literal,
    LockTableStmt,
    MergeStmt,
    OrderByItem,
    ParamRef,
    PrepareTransactionStmt,
    RawStatement,
    RollbackStmt,
    SampleClause,
    SavepointStmt,
    Script,
    SelectStmt,
    SelectTarget,
    SetConstraintsStmt,
    SetOpClause,
    SetTransactionStmt,
    SettingAssignment,
    SimilarToExpr,
    StarExpr,
    SubqueryExpr,
    SubqueryRef,
    TableConstraint,
    TableFunctionRef,
    TableRef,
    TtlClause,
    TtlRule,
    TupleConstructor,
    TypeRef,
    UnaryOp,
    ValuesClause,
    WhenBranch,
    WindowDef,
    WindowSpec,
    WithClause,
    WithFillSpec,
)


class _Writer:
    __slots__ = ("_buf", "_offset", "_line", "_col")

    def __init__(self) -> None:
        self._buf: list[str] = []
        self._offset = 0
        self._line = 1
        self._col = 1

    def write(self, text: str) -> None:
        if not text:
            return
        self._buf.append(text)
        for ch in text:
            self._offset += 1
            if ch == "\n":
                self._line += 1
                self._col = 1
            else:
                self._col += 1

    def pos(self) -> Position:
        return Position(self._offset, self._line, self._col)

    def result(self) -> str:
        return "".join(self._buf)


class ClickHouseEmitter:

    def __init__(self, indent: int = 4) -> None:
        self._wr = _Writer()
        self._indent = indent
        self._level = 0

    def emit(self, node: Node) -> None:
        self._emit(node)

    def result(self) -> str:
        return self._wr.result()


    def _w(self, text: str) -> None:
        self._wr.write(text)

    def _nl(self) -> None:
        self._wr.write("\n")

    def _ind(self, extra: int = 0) -> None:
        self._wr.write(" " * (self._indent * self._level + extra))

    def _pos(self) -> Position:
        return self._wr.pos()


    def _emit(self, node: Node) -> None:
        start = self._pos()
        kind = getattr(node, "node_kind", type(node).__name__)
        method: Optional[Callable] = getattr(self, f"_emit_{kind}", None)
        if method is None:
            self._w(f"/* UNSUPPORTED: {kind} */")
        else:
            method(node)
        span = Span(start, self._pos())
        node.output_span = span
        for ann in getattr(node, "annotations", []):
            if ann.output_span is None:
                ann.output_span = span

    def _emit_list(
        self,
        items: list,
        sep: str = ", ",
        *,
        inline: bool = True,
        newline_sep: Optional[str] = None,
    ) -> None:
        for i, item in enumerate(items):
            if i:
                if newline_sep is not None:
                    self._w(newline_sep)
                else:
                    self._w(sep)
            self._emit(item)


    def _emit_Identifier(self, n: Identifier) -> None:
        if n.quoted:
            escaped = n.name.replace("`", "``")
            self._w(f"`{escaped}`")
        else:
            self._w(n.name)

    def _emit_Literal(self, n: Literal) -> None:
        if n.explicit_type:
            self._emit(n.explicit_type)
            self._w(" ")
        kind = n.literal_kind
        if kind in ("int", "float"):
            self._w(n.raw if n.raw is not None else str(n.value))
        elif kind == "string":
            raw = n.raw if n.raw is not None else str(n.value)
            self._w("'" + raw.replace("\\", "\\\\").replace("'", "\\'") + "'")
        elif kind == "bool":
            self._w("true" if n.value else "false")
        elif kind == "null":
            self._w("NULL")
        elif kind in ("date", "timestamp"):
            raw = n.raw if n.raw is not None else str(n.value)
            self._w("'" + raw + "'")
        elif kind == "interval":
            self._w(n.raw if n.raw is not None else str(n.value))
        else:
            self._w(n.raw if n.raw is not None else repr(n.value))

    def _emit_ColumnRef(self, n) -> None:
        parts = [p for p in (n.database, n.schema, n.table, n.column) if p is not None]
        for i, part in enumerate(parts):
            if i:
                self._w(".")
            self._emit(part)

    def _emit_StarExpr(self, n: StarExpr) -> None:
        if n.table:
            self._emit(n.table)
            self._w(".")
        self._w("*")

    def _emit_TypeRef(self, n: TypeRef) -> None:
        dims = n.array_dims or 0
        for _ in range(dims):
            self._w("Array(")
        self._w(n.name)
        if n.params:
            self._w("(")
            self._emit_list(n.params)
            self._w(")")
        for _ in range(dims):
            self._w(")")

    def _emit_BinaryOp(self, n: BinaryOp) -> None:
        lpar = isinstance(n.left, BinaryOp)
        if lpar:
            self._w("(")
        self._emit(n.left)
        if lpar:
            self._w(")")
        self._w(f" {n.op} ")
        rpar = isinstance(n.right, BinaryOp)
        if rpar:
            self._w("(")
        self._emit(n.right)
        if rpar:
            self._w(")")

    def _emit_UnaryOp(self, n: UnaryOp) -> None:
        if n.position == "prefix":
            self._w(n.op)
            if n.op[-1:].isalpha():
                self._w(" ")
            self._emit(n.operand)
        else:
            self._emit(n.operand)
            self._w(n.op)

    def _emit_FunctionCall(self, n: FunctionCall) -> None:
        self._emit(n.name)
        if n.parameters:
            self._w("(")
            self._emit_list(n.parameters)
            self._w(")")
        self._w("(")
        if n.distinct:
            self._w("DISTINCT ")
        if n.star and not n.args:
            self._w("*")
        elif n.args:
            self._emit_list(n.args)
        if n.order_by:
            if n.args or n.star:
                self._w(" ")
            self._w("ORDER BY ")
            self._emit_list(n.order_by)
        self._w(")")
        if n.over:
            self._w(" OVER ")
            self._emit_WindowSpec_inline(n.over)

    def _emit_Cast(self, n: Cast) -> None:
        if n.style in ("cast", "postfix"):
            self._w("CAST(")
            self._emit(n.expression)
            self._w(" AS ")
            self._emit(n.target_type)
            self._w(")")
        elif n.style == "typed_fn":
            self._emit(n.target_type)
            self._w("(")
            self._emit(n.expression)
            self._w(")")
        elif n.style == "typed_literal":
            self._emit(n.target_type)
            self._w(" ")
            self._emit(n.expression)
        else:
            self._w("CAST(")
            self._emit(n.expression)
            self._w(" AS ")
            self._emit(n.target_type)
            self._w(")")

    def _emit_CaseExpr(self, n: CaseExpr) -> None:
        self._w("CASE")
        if n.arg:
            self._w(" ")
            self._emit(n.arg)
        for br in n.branches:
            self._w(" WHEN ")
            self._emit(br.condition)
            self._w(" THEN ")
            self._emit(br.result)
        if n.else_expr:
            self._w(" ELSE ")
            self._emit(n.else_expr)
        self._w(" END")

    def _emit_WhenBranch(self, n: WhenBranch) -> None:
        self._w("WHEN ")
        self._emit(n.condition)
        self._w(" THEN ")
        self._emit(n.result)

    def _emit_ArrayConstructor(self, n: ArrayConstructor) -> None:
        self._w("[")
        self._emit_list(n.elements)
        self._w("]")

    def _emit_TupleConstructor(self, n: TupleConstructor) -> None:
        if n.syntax == "row_kw":
            self._w("tuple(")
            self._emit_list(n.elements)
            self._w(")")
        else:
            self._w("(")
            self._emit_list(n.elements)
            self._w(")")

    def _emit_SubqueryExpr(self, n: SubqueryExpr) -> None:
        prefix = {
            "exists":     "EXISTS ",
            "not_exists": "NOT EXISTS ",
        }.get(n.kind, "")
        self._w(prefix + "(")
        self._emit(n.query)
        self._w(")")

    def _emit_ParamRef(self, n: ParamRef) -> None:
        if n.number is not None:
            self._w(f"${n.number}")
        elif n.name is not None:
            self._w("{" + n.name + "}")
        else:
            self._w("?")

    def _emit_BetweenExpr(self, n: BetweenExpr) -> None:
        self._emit(n.expr)
        kw = " NOT BETWEEN " if n.negated else " BETWEEN "
        self._w(kw)
        if n.symmetric:
            self._w("SYMMETRIC ")
        self._emit(n.low)
        self._w(" AND ")
        self._emit(n.high)

    def _emit_LikeExpr(self, n: LikeExpr) -> None:
        self._emit(n.string)
        neg = " NOT" if n.negated else ""
        op  = " ILIKE " if n.case_insensitive else " LIKE "
        self._w(neg + op)
        self._emit(n.pattern)
        if n.escape:
            self._w(" ESCAPE ")
            self._emit(n.escape)

    def _emit_SimilarToExpr(self, n: SimilarToExpr) -> None:
        self._emit(n.string)
        kw = " NOT SIMILAR TO " if n.negated else " SIMILAR TO "
        self._w(kw)
        self._emit(n.pattern)
        if n.escape:
            self._w(" ESCAPE ")
            self._emit(n.escape)


    def _emit_OrderByItem(self, n: OrderByItem) -> None:
        self._emit(n.expression)
        if n.direction:
            self._w(f" {n.direction}")
        if n.nulls:
            self._w(f" NULLS {n.nulls}")
        if n.collate:
            self._w(f" COLLATE '{n.collate}'")
        if n.with_fill:
            wf = n.with_fill
            self._w(" WITH FILL")
            if wf.from_value:
                self._w(" FROM ")
                self._emit(wf.from_value)
            if wf.to_value:
                self._w(" TO ")
                self._emit(wf.to_value)
            if wf.step:
                self._w(" STEP ")
                self._emit(wf.step)

    def _emit_WithFillSpec(self, n: WithFillSpec) -> None:
        self._w("WITH FILL")
        if n.from_value:
            self._w(" FROM ")
            self._emit(n.from_value)
        if n.to_value:
            self._w(" TO ")
            self._emit(n.to_value)
        if n.step:
            self._w(" STEP ")
            self._emit(n.step)

    def _emit_FrameBound(self, n: FrameBound) -> None:
        _FB = {
            "UNBOUNDED_PRECEDING": "UNBOUNDED PRECEDING",
            "UNBOUNDED_FOLLOWING": "UNBOUNDED FOLLOWING",
            "CURRENT_ROW":         "CURRENT ROW",
        }
        label = _FB.get(n.kind)
        if label:
            self._w(label)
        elif n.kind == "N_PRECEDING":
            self._emit(n.offset)
            self._w(" PRECEDING")
        elif n.kind == "N_FOLLOWING":
            self._emit(n.offset)
            self._w(" FOLLOWING")
        else:
            self._w(n.kind)

    def _emit_FrameSpec(self, n: FrameSpec) -> None:
        self._w(n.unit)
        if n.end:
            self._w(" BETWEEN ")
            self._emit(n.start)
            self._w(" AND ")
            self._emit(n.end)
        else:
            self._w(" ")
            self._emit(n.start)

    def _emit_WindowSpec_inline(self, n: WindowSpec) -> None:
        self._w("(")
        need_space = False
        if n.existing_name:
            self._emit(n.existing_name)
            need_space = True
        if n.partition_by:
            if need_space:
                self._w(" ")
            self._w("PARTITION BY ")
            self._emit_list(n.partition_by)
            need_space = True
        if n.order_by:
            if need_space:
                self._w(" ")
            self._w("ORDER BY ")
            self._emit_list(n.order_by)
            need_space = True
        if n.frame:
            if need_space:
                self._w(" ")
            self._emit(n.frame)
        self._w(")")

    def _emit_WindowSpec(self, n: WindowSpec) -> None:
        self._emit_WindowSpec_inline(n)

    def _emit_WindowDef(self, n: WindowDef) -> None:
        self._emit(n.name)
        self._w(" AS ")
        self._emit_WindowSpec_inline(n.spec)

    def _emit_DistinctClause(self, n: DistinctClause) -> None:
        if n.kind == "distinct":
            self._w("DISTINCT")
        elif n.kind == "distinct_on":
            self._w("DISTINCT ON (")
            self._emit_list(n.on)
            self._w(")")

    def _emit_WithClause(self, n: WithClause) -> None:
        self._w("WITH ")
        if n.recursive:
            self._w("RECURSIVE ")
        self._emit_list(n.ctes)

    def _emit_CommonTableExpr(self, n: CommonTableExpr) -> None:
        self._emit(n.name)
        if n.columns:
            self._w(" (")
            self._emit_list(n.columns)
            self._w(")")
        if n.materialized is True:
            self._w(" AS MATERIALIZED (")
        elif n.materialized is False:
            self._w(" AS NOT MATERIALIZED (")
        else:
            self._w(" AS (")
        self._level += 1
        self._nl()
        self._ind()
        self._emit(n.query)
        self._level -= 1
        self._nl()
        self._ind()
        self._w(")")

    def _emit_GroupByClause(self, n: GroupByClause) -> None:
        kind = n.kind
        if kind == "rollup":
            self._w("ROLLUP (")
            self._emit_list(n.items)
            self._w(")")
        elif kind == "cube":
            self._w("CUBE (")
            self._emit_list(n.items)
            self._w(")")
        elif kind == "grouping_sets":
            self._w("GROUPING SETS (")
            self._emit_list(n.items)
            self._w(")")
        else:
            self._emit_list(n.items)

    def _emit_SetOpClause(self, n: SetOpClause) -> None:
        q = f" {n.quantifier}" if n.quantifier else ""
        self._w(f"{n.op}{q}")

    def _emit_SampleClause(self, n: SampleClause) -> None:
        self._emit(n.ratio)
        if n.offset:
            self._w(" OFFSET ")
            self._emit(n.offset)

    def _emit_SettingAssignment(self, n: SettingAssignment) -> None:
        self._w(n.name)
        self._w(" = ")
        self._emit(n.value)

    def _emit_SelectTarget(self, n: SelectTarget) -> None:
        self._emit(n.expression)
        if n.alias:
            self._w(" AS ")
            self._emit(n.alias)

    def _emit_TableRef(self, n: TableRef) -> None:
        parts = [p for p in (n.database, n.schema, n.name) if p is not None]
        for i, part in enumerate(parts):
            if i:
                self._w(".")
            self._emit(part)
        if n.alias:
            self._w(" AS ")
            self._emit(n.alias)
        if n.ch_sample:
            self._w(" SAMPLE ")
            self._emit(n.ch_sample.ratio)
            if n.ch_sample.offset:
                self._w(" OFFSET ")
                self._emit(n.ch_sample.offset)

    def _emit_JoinExpr(self, n: JoinExpr) -> None:
        _JOIN_KW = {
            "inner":         "INNER JOIN",
            "left":          "LEFT JOIN",
            "right":         "RIGHT JOIN",
            "full":          "FULL JOIN",
            "cross":         "CROSS JOIN",
            "natural_inner": "NATURAL JOIN",
            "semi":          "LEFT SEMI JOIN",
            "anti":          "LEFT ANTI JOIN",
            "asof":          "ASOF JOIN",
        }
        self._emit(n.left)
        kw = _JOIN_KW.get(n.kind, n.kind.upper() + " JOIN")
        self._nl()
        self._ind()
        self._w(kw + " ")
        self._emit(n.right)
        if n.on:
            self._w(" ON ")
            self._emit(n.on)
        elif n.using:
            self._w(" USING (")
            self._emit_list(n.using)
            self._w(")")

    def _emit_SubqueryRef(self, n: SubqueryRef) -> None:
        self._w("(")
        self._level += 1
        self._nl()
        self._ind()
        self._emit(n.query)
        self._level -= 1
        self._nl()
        self._ind()
        self._w(")")
        if n.alias:
            self._w(" AS ")
            self._emit(n.alias)

    def _emit_TableFunctionRef(self, n: TableFunctionRef) -> None:
        self._emit(n.call)
        if n.alias:
            self._w(" AS ")
            self._emit(n.alias)

    def _emit_ColumnConstraint(self, n: ColumnConstraint) -> None:
        kind = n.kind
        if kind == "not_null":
            self._w("NOT NULL")
        elif kind == "null":
            self._w("NULL")
        elif kind == "default":
            self._w("DEFAULT ")
            self._emit(n.expression)
        elif kind == "check":
            self._w("CHECK (")
            self._emit(n.expression)
            self._w(")")
        elif kind == "primary_key":
            self._w("PRIMARY KEY")
        elif kind == "unique":
            self._w("UNIQUE")
        elif kind == "generated_stored":
            self._w("MATERIALIZED ")
            if n.expression:
                self._emit(n.expression)
        elif kind == "generated_virtual":
            self._w("ALIAS ")
            if n.expression:
                self._emit(n.expression)
        elif kind == "generated_identity":
            self._w("DEFAULT generateUUIDv4()")
        elif kind == "references":
            self._w("REFERENCES ")
            if n.ref_table:
                self._emit(n.ref_table)
            if n.ref_columns:
                self._w(" (")
                self._emit_list(n.ref_columns)
                self._w(")")
            if n.match:
                self._w(f" MATCH {n.match}")
            if n.on_delete:
                self._w(f" ON DELETE {n.on_delete}")
            if n.on_update:
                self._w(f" ON UPDATE {n.on_update}")
        else:
            self._w(kind.upper())

    def _emit_ColumnDef(self, n: ColumnDef) -> None:
        self._emit(n.name)
        self._w(" ")
        self._emit(n.type)
        for constraint in n.constraints:
            self._w(" ")
            self._emit(constraint)
        if n.codec:
            self._w(" CODEC(")
            for i, codec in enumerate(n.codec):
                if i:
                    self._w(", ")
                self._emit(codec.name)
                if codec.args:
                    self._w("(")
                    self._emit_list(codec.args)
                    self._w(")")
            self._w(")")
        if n.ttl:
            self._w(" TTL ")
            self._emit(n.ttl)

    def _emit_TableConstraint(self, n: TableConstraint) -> None:
        if n.name:
            self._w(f"CONSTRAINT {n.name} ")
        kind = n.kind
        if kind == "primary_key":
            self._w("PRIMARY KEY (")
            self._emit_list(n.columns)
            self._w(")")
        elif kind == "unique":
            self._w("UNIQUE (")
            self._emit_list(n.columns)
            self._w(")")
        elif kind == "check":
            self._w("CHECK (")
            self._emit(n.expression)
            self._w(")")
        elif kind == "foreign_key":
            self._w("FOREIGN KEY (")
            self._emit_list(n.columns)
            self._w(")")
            if n.ref_table:
                self._w(" REFERENCES ")
                self._emit(n.ref_table)
            if n.ref_columns:
                self._w(" (")
                self._emit_list(n.ref_columns)
                self._w(")")
            if n.match:
                self._w(f" MATCH {n.match}")
            if n.on_delete:
                self._w(f" ON DELETE {n.on_delete}")
            if n.on_update:
                self._w(f" ON UPDATE {n.on_update}")
        else:
            self._w(kind.upper())
            if n.columns:
                self._w(" (")
                self._emit_list(n.columns)
                self._w(")")

    def _emit_LikeClause(self, n: LikeClause) -> None:
        self._w("AS ")
        self._emit(n.source)

    def _emit_EngineSpec(self, n: EngineSpec) -> None:
        self._w(f"ENGINE = {n.name}")
        if n.args:
            self._w("(")
            self._emit_list(n.args)
            self._w(")")

    def _emit_TtlClause(self, n: TtlClause) -> None:
        self._w("TTL ")
        for i, rule in enumerate(n.rules):
            if i:
                self._w(",\n    ")
            self._emit(rule.expression)
            if rule.action and rule.action != "DELETE":
                self._w(f" {rule.action}")
                if rule.target:
                    self._w(f" '{rule.target}'")

    def _emit_TtlRule(self, n: TtlRule) -> None:
        self._emit(n.expression)
        if n.action and n.action != "DELETE":
            self._w(f" {n.action}")
            if n.target:
                self._w(f" '{n.target}'")

    def _emit_IndexColumn(self, n: IndexColumn) -> None:
        self._emit(n.expression)
        if n.direction:
            self._w(f" {n.direction}")
        if n.nulls:
            self._w(f" NULLS {n.nulls}")

    def _emit_OnConflictClause(self, n) -> None:
        self._w("ON CONFLICT")
        if n.target is not None:
            self._w(" (")
            self._emit(n.target)
            self._w(")")
        if n.action == "nothing":
            self._w(" DO NOTHING")
        elif n.action == "update":
            self._w(" DO UPDATE SET ")
            for i, upd in enumerate(n.updates):
                if i:
                    self._w(", ")
                self._emit(upd)
            if n.where is not None:
                self._w(" WHERE ")
                self._emit(n.where)
        else:
            self._w(f" DO {n.action.upper()}")

    def _emit_DefaultValues(self, n: DefaultValues) -> None:
        self._w("DEFAULT VALUES")

    def _emit_Script(self, n: Script) -> None:
        for i, stmt in enumerate(n.statements):
            if i:
                self._w(";\n\n")
            self._emit(stmt)
        if n.statements:
            self._w(";")

    def _emit_RawStatement(self, n: RawStatement) -> None:
        self._w(n.text)

    def _emit_SelectStmt(self, n: SelectStmt) -> None:
        ind = " " * (self._indent * self._level)

        # WITH
        if n.with_clause:
            wc = n.with_clause
            self._w("WITH ")
            if wc.recursive:
                self._w("RECURSIVE ")
            for i, cte in enumerate(wc.ctes):
                if i:
                    self._w(f",\n{ind}     ")
                self._emit(cte.name)
                if cte.columns:
                    self._w(" (")
                    self._emit_list(cte.columns)
                    self._w(")")
                if cte.materialized is True:
                    self._w(" AS MATERIALIZED (")
                elif cte.materialized is False:
                    self._w(" AS NOT MATERIALIZED (")
                else:
                    self._w(" AS (")
                self._level += 1
                self._nl()
                self._ind()
                self._emit(cte.query)
                self._level -= 1
                self._nl()
                self._ind()
                self._w(")")
            self._nl()
            self._ind()

        # SELECT [DISTINCT]
        self._w("SELECT")
        if n.distinct:
            dc = n.distinct
            if dc.kind == "distinct":
                self._w(" DISTINCT")
            elif dc.kind == "distinct_on":
                self._w(" DISTINCT ON (")
                self._emit_list(dc.on)
                self._w(")")

        # Target list
        if n.targets:
            for i, tgt in enumerate(n.targets):
                if i:
                    self._w(",")
                self._nl()
                self._ind(extra=self._indent)
                self._emit(tgt)
        else:
            self._w(" *")

        # FROM
        if n.from_items:
            self._nl()
            self._ind()
            self._w("FROM ")
            for i, item in enumerate(n.from_items):
                if i:
                    self._w(f",\n{ind}     ")
                self._emit(item)

        # SAMPLE at SELECT level (CH-specific)
        if n.sample:
            self._nl()
            self._ind()
            self._w("SAMPLE ")
            self._emit(n.sample.ratio)
            if n.sample.offset:
                self._w(" OFFSET ")
                self._emit(n.sample.offset)

        # WHERE
        if n.where:
            self._nl()
            self._ind()
            self._w("WHERE ")
            self._emit(n.where)

        # GROUP BY
        if n.group_by:
            self._nl()
            self._ind()
            self._w("GROUP BY ")
            self._emit(n.group_by)

        # HAVING
        if n.having:
            self._nl()
            self._ind()
            self._w("HAVING ")
            self._emit(n.having)

        # WINDOW definitions
        if n.windows:
            self._nl()
            self._ind()
            self._w("WINDOW ")
            for i, wd in enumerate(n.windows):
                if i:
                    self._w(f",\n{ind}       ")
                self._emit(wd)

        # UNION / INTERSECT / EXCEPT
        if n.set_op:
            sop = n.set_op
            q = f" {sop.quantifier}" if sop.quantifier else ""
            self._nl()
            self._ind()
            self._w(f"{sop.op}{q}")
            self._nl()
            self._ind()
            self._emit(sop.right)

        # ORDER BY
        if n.order_by:
            self._nl()
            self._ind()
            self._w("ORDER BY ")
            self._emit_list(n.order_by)

        # LIMIT
        if n.limit is not None:
            self._nl()
            self._ind()
            self._w("LIMIT ")
            self._emit(n.limit)
            if n.limit_with_ties:
                self._w(" WITH TIES")

        # OFFSET
        if n.offset is not None:
            self._nl()
            self._ind()
            self._w("OFFSET ")
            self._emit(n.offset)

        # SETTINGS (CH)
        if n.settings:
            self._nl()
            self._ind()
            self._w("SETTINGS ")
            self._emit_list(n.settings)

    def _emit_InsertStmt(self, n: InsertStmt) -> None:
        self._w("INSERT INTO ")
        self._emit(n.target)
        if n.columns:
            self._w(" (")
            self._emit_list(n.columns)
            self._w(")")
        if n.ch_format:
            self._w(f" FORMAT {n.ch_format}")
        if n.source is None:
            pass
        elif isinstance(n.source, ValuesClause):
            self._nl()
            self._w("VALUES")
            for i, row in enumerate(n.source.rows):
                if i:
                    self._w(",")
                self._nl()
                self._w("    (")
                self._emit_list(row)
                self._w(")")
        elif isinstance(n.source, SelectStmt):
            self._nl()
            self._emit(n.source)
        elif isinstance(n.source, DefaultValues):
            self._nl()
            self._w("DEFAULT VALUES")
        if n.on_conflict:
            self._nl()
            self._emit(n.on_conflict)

    def _emit_ValuesClause(self, n: ValuesClause) -> None:
        self._w("VALUES")
        for i, row in enumerate(n.rows):
            if i:
                self._w(",")
            self._nl()
            self._w("    (")
            self._emit_list(row)
            self._w(")")

    def _emit_CreateTableStmt(self, n: CreateTableStmt) -> None:
        self._w("CREATE ")
        if n.temporary:
            self._w("TEMPORARY ")
        self._w("TABLE ")
        if n.if_not_exists:
            self._w("IF NOT EXISTS ")
        self._emit(n.table)

        # LIKE (AS source_table — CH syntax)
        if n.like_clause:
            self._nl()
            self._emit(n.like_clause)
            return

        # Column list + table constraints
        all_defs = list(n.columns) + list(n.table_constraints)
        if all_defs:
            self._nl()
            self._w("(")
            self._level += 1
            for i, item in enumerate(all_defs):
                self._nl()
                self._ind()
                self._emit(item)
                if i < len(all_defs) - 1:
                    self._w(",")
            self._level -= 1
            self._nl()
            self._w(")")

        if n.engine:
            self._nl()
            self._emit(n.engine)

        if n.order_by_key:
            self._nl()
            self._w("ORDER BY ")
            if len(n.order_by_key) == 1:
                self._emit(n.order_by_key[0])
            else:
                self._w("(")
                self._emit_list(n.order_by_key)
                self._w(")")

        if n.primary_key:
            self._nl()
            self._w("PRIMARY KEY ")
            if len(n.primary_key) == 1:
                self._emit(n.primary_key[0])
            else:
                self._w("(")
                self._emit_list(n.primary_key)
                self._w(")")

        if n.partition_by:
            self._nl()
            self._w("PARTITION BY ")
            self._emit(n.partition_by)

        if n.sample_by:
            self._nl()
            self._w("SAMPLE BY ")
            self._emit(n.sample_by)

        if n.ttl:
            self._nl()
            self._emit(n.ttl)

        if n.settings:
            self._nl()
            self._w("SETTINGS ")
            self._emit_list(n.settings)

    def _emit_CreateViewStmt(self, n: CreateViewStmt) -> None:
        self._w("CREATE ")
        if n.or_replace:
            self._w("OR REPLACE ")
        if n.is_materialized:
            self._w("MATERIALIZED VIEW ")
        else:
            self._w("VIEW ")
        if n.if_not_exists:
            self._w("IF NOT EXISTS ")
        if n.name:
            self._emit(n.name)
        if n.to_table:
            self._w(" TO ")
            self._emit(n.to_table)
        if n.query:
            self._w(" AS")
            self._nl()
            self._emit(n.query)
        if n.is_materialized and n.populate:
            self._nl()
            self._w("POPULATE")


    def _emit_CreateIndexStmt(self, n: CreateIndexStmt) -> None:
        self._w("ALTER TABLE ")
        if n.table:
            self._emit(n.table)
        self._w(" ADD INDEX ")
        if n.name:
            self._emit(n.name)
        self._w(" (")
        self._emit_list(n.columns)
        self._w(")")
        if n.index_type:
            self._w(f" TYPE {n.index_type}")
        if n.granularity is not None:
            self._w(f" GRANULARITY {n.granularity}")


    def _emit_CreateFunctionStmt(self, n: CreateFunctionStmt) -> None:
        self._w("CREATE ")
        if n.or_replace:
            self._w("OR REPLACE ")
        self._w("FUNCTION ")
        if n.name:
            self._emit(n.name)
        if n.ch_lambda_body:
            self._w(" AS (")
            for i, arg in enumerate(n.args):
                if i:
                    self._w(", ")
                if arg.name:
                    self._emit(arg.name)
            self._w(") -> ")
            self._emit(n.ch_lambda_body)
        else:
            body = n.body or ""
            lang = n.language or "unknown"
            self._w(f"\n/* PG function (language={lang}) — rewrite for ClickHouse:\n")
            self._w(f"{body}\n*/")


    def _emit_CreateDatabaseStmt(self, n: CreateDatabaseStmt) -> None:
        self._w("CREATE DATABASE ")
        if n.if_not_exists:
            self._w("IF NOT EXISTS ")
        if n.name:
            self._emit(n.name)
        if n.engine:
            self._w(f" ENGINE = {n.engine}")


    def _emit_CreateUserStmt(self, n: CreateUserStmt) -> None:
        self._w("CREATE USER ")
        if n.if_not_exists:
            self._w("IF NOT EXISTS ")
        if n.name:
            self._emit(n.name)
        if n.password:
            self._w(f" IDENTIFIED WITH plaintext_password BY '{n.password}'")

    def _emit_CreateRoleStmt(self, n: CreateRoleStmt) -> None:
        self._w("CREATE ROLE ")
        if n.if_not_exists:
            self._w("IF NOT EXISTS ")
        if n.name:
            self._emit(n.name)

    def _emit_AlterRoleStmt(self, n: AlterRoleStmt) -> None:
        self._w("ALTER USER ")
        if n.name:
            self._emit(n.name)
        if n.password:
            self._w(f" IDENTIFIED WITH plaintext_password BY '{n.password}'")


    def _emit_GrantStmt(self, n: GrantStmt) -> None:
        verb = "GRANT" if n.is_grant else "REVOKE"
        to_from = "TO" if n.is_grant else "FROM"
        if n.is_role_grant:
            self._w(f"{verb} ")
            self._emit_list(n.roles)
            self._w(f" {to_from} ")
            self._emit_list(n.grantees)
        else:
            self._w(f"{verb} ")
            self._w(", ".join(n.privileges) if n.privileges else "ALL")
            obj_type = n.object_type or ""
            self._w(f" ON {obj_type} " if obj_type else " ON ")
            self._emit_list(n.objects)
            self._w(f" {to_from} ")
            self._emit_list(n.grantees)
        if n.with_grant:
            self._w(" WITH GRANT OPTION")
        if n.with_admin:
            self._w(" WITH ADMIN OPTION")


    def _emit_BeginStmt(self, n: BeginStmt) -> None:
        self._w("BEGIN TRANSACTION")

    def _emit_CommitStmt(self, n: CommitStmt) -> None:
        self._w("COMMIT")

    def _emit_RollbackStmt(self, n: RollbackStmt) -> None:
        self._w("ROLLBACK")

    def _emit_SavepointStmt(self, n: SavepointStmt) -> None:
        _SP = {
            "savepoint":   f"SAVEPOINT {n.name}",
            "release":     f"RELEASE SAVEPOINT {n.name}",
            "rollback_to": f"ROLLBACK TO SAVEPOINT {n.name}",
        }
        self._w(_SP.get(n.action, f"SAVEPOINT {n.action.upper()} {n.name}"))

    def _emit_SetTransactionStmt(self, n: SetTransactionStmt) -> None:
        if n.scope == "session":
            self._w("SET SESSION CHARACTERISTICS AS TRANSACTION")
        elif n.scope == "local":
            self._w("SET LOCAL TRANSACTION")
        else:
            self._w("SET TRANSACTION")
        parts: list[str] = []
        if n.isolation_level:
            parts.append(f"ISOLATION LEVEL {n.isolation_level}")
        if n.read_only is True:
            parts.append("READ ONLY")
        elif n.read_only is False:
            parts.append("READ WRITE")
        if n.deferrable is True:
            parts.append("DEFERRABLE")
        elif n.deferrable is False:
            parts.append("NOT DEFERRABLE")
        if parts:
            self._w(" " + ", ".join(parts))

    def _emit_SetConstraintsStmt(self, n: SetConstraintsStmt) -> None:
        self._w(f"SET CONSTRAINTS ALL {n.mode}")

    def _emit_LockTableStmt(self, n: LockTableStmt) -> None:
        self._w("LOCK TABLE")
        if n.mode:
            self._w(f" IN {n.mode} MODE")

    def _emit_PrepareTransactionStmt(self, n: PrepareTransactionStmt) -> None:
        pid = f"'{n.prepared_id}'" if n.prepared_id else "''"
        if n.action == "commit":
            self._w(f"COMMIT PREPARED {pid}")
        elif n.action == "rollback":
            self._w(f"ROLLBACK PREPARED {pid}")
        else:
            self._w(f"PREPARE TRANSACTION {pid}")


    def _emit_CopyStmt(self, n: CopyStmt) -> None:
        if n.ch_from_infile:
            self._w("INSERT INTO ")
            if n.table:
                self._emit(n.table)
            if n.columns:
                self._w(" (")
                self._emit_list(n.columns)
                self._w(")")
            self._w(f" FROM INFILE '{n.ch_from_infile}'")
            if n.ch_format:
                self._w(f" FORMAT {n.ch_format}")
        elif n.ch_into_outfile:
            if n.query:
                self._emit(n.query)
            self._w(f" INTO OUTFILE '{n.ch_into_outfile}'")
            if n.ch_format:
                self._w(f" FORMAT {n.ch_format}")
        else:
            self._w("/* COPY: no direct equivalent in ClickHouse */")

    def _emit_MergeStmt(self, n: MergeStmt) -> None:
        self._w("/* MERGE: no equivalent in ClickHouse */")
