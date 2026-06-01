"""Конвертер pglast AST -> AST нашей разработки"""
from __future__ import annotations

import bisect
import warnings
from typing import Optional

import pglast
import pglast.ast as pg

from src.ast import (
    # Метаданные
    Dialect, Position, Span,
    # Узлы
    Node, Script,
    # Операторы
    Statement, SelectStmt, InsertStmt, CreateTableStmt,
    CreateViewStmt, CreateIndexStmt, CreateFunctionStmt, CreateDatabaseStmt,
    CreateUserStmt, CreateRoleStmt, GrantStmt, AlterRoleStmt,
    CopyStmt, MergeStmt, LockTableStmt, SetConstraintsStmt,
    BeginStmt, CommitStmt, RollbackStmt, SavepointStmt,
    SetTransactionStmt, PrepareTransactionStmt, RawStatement,
    SelectTarget, ValuesClause, DefaultValues,
    # Выражения
    Expression,
    Identifier, Literal, ColumnRef, StarExpr, TypeRef,
    BinaryOp, UnaryOp, FunctionCall, Cast,
    CaseExpr, WhenBranch, ArrayConstructor, TupleConstructor,
    SubqueryExpr, ParamRef, BetweenExpr,
    LikeExpr, SimilarToExpr,
    # FROM
    FromItem, TableRef, JoinExpr, SubqueryRef, TableFunctionRef,
    # Клаузы SELECT
    WithClause, CommonTableExpr, DistinctClause, GroupByClause,
    OrderByItem, SetOpClause, FetchClause, LockingClause,
    WindowDef, WindowSpec, FrameSpec, FrameBound,
    # DDL
    ColumnDef, ColumnConstraint, TableConstraint, LikeClause,
    OnConflictClause, SettingAssignment, ExcludeElement,
    IndexColumn, FunctionArg,
)

# Frame-опции (parsenodes.h)
_FO_NONDEFAULT     = 0x00001
_FO_RANGE          = 0x00002
_FO_ROWS           = 0x00004
_FO_GROUPS         = 0x00008
_FO_BETWEEN        = 0x00010
_FO_START_UNB_PRE  = 0x00020
_FO_END_UNB_PRE    = 0x00040
_FO_START_UNB_FOL  = 0x00080
_FO_END_UNB_FOL    = 0x00100
_FO_START_CURR     = 0x00200
_FO_END_CURR       = 0x00400
_FO_START_OFF_PRE  = 0x00800
_FO_END_OFF_PRE    = 0x01000
_FO_START_OFF_FOL  = 0x02000
_FO_END_OFF_FOL    = 0x04000
_FO_EXCL_CURR_ROW  = 0x08000
_FO_EXCL_GROUP     = 0x10000
_FO_EXCL_TIES      = 0x20000

# Нормализация типов pg_catalog
_PG_TYPE_NORM: dict[str, str | tuple[str, str]] = {
    "int2":        "SMALLINT",
    "int4":        "INTEGER",
    "int8":        "BIGINT",
    "float4":      "REAL",
    "float8":      "DOUBLE PRECISION",
    "bool":        "BOOLEAN",
    "bpchar":      "CHAR",
    "timestamptz": ("TIMESTAMP", "WITH TIME ZONE"),
    "timetz":      ("TIME",      "WITH TIME ZONE"),
}

# SQLValueFunction names
_SVF_NAMES: dict[str, str] = {
    "SVFOP_CURRENT_DATE":        "CURRENT_DATE",
    "SVFOP_CURRENT_TIME":        "CURRENT_TIME",
    "SVFOP_CURRENT_TIME_N":      "CURRENT_TIME",
    "SVFOP_CURRENT_TIMESTAMP":   "CURRENT_TIMESTAMP",
    "SVFOP_CURRENT_TIMESTAMP_N": "CURRENT_TIMESTAMP",
    "SVFOP_CURRENT_USER":        "CURRENT_USER",
    "SVFOP_SESSION_USER":        "SESSION_USER",
    "SVFOP_USER":                "USER",
    "SVFOP_LOCALTIME":           "LOCALTIME",
    "SVFOP_LOCALTIME_N":         "LOCALTIME",
    "SVFOP_LOCALTIMESTAMP":      "LOCALTIMESTAMP",
    "SVFOP_LOCALTIMESTAMP_N":    "LOCALTIMESTAMP",
}

_LOCK_MODE = {1: "KEY_SHARE", 2: "SHARE", 3: "NO_KEY_UPDATE", 4: "UPDATE"}

_JOIN_KIND = {0: "inner", 1: "left", 2: "full", 3: "right", 4: "semi", 5: "anti"}

_FK_ACTION = {"a": "NO ACTION", "r": "RESTRICT", "c": "CASCADE",
              "n": "SET NULL",  "d": "SET DEFAULT"}
_FK_MATCH  = {"f": "FULL", "p": "PARTIAL", "s": "SIMPLE"}

_STORAGE_MAP = {"p": "PLAIN", "e": "EXTERNAL", "x": "EXTENDED", "m": "MAIN"}

_TABLE_LIKE_OPTS: dict[int, str] = {
    1:   "COMMENTS",
    4:   "CONSTRAINTS",
    8:   "DEFAULTS",
    16:  "GENERATED",
    32:  "IDENTITY",
    64:  "INDEXES",
    128: "STATISTICS",
    256: "STORAGE",
}
_TABLE_LIKE_ALL = 0x7FFFFFFF

# LockStmt mode values (проверено эмпирически в pglast)
_LOCK_TABLE_MODE: dict[int, str] = {
    1: "ACCESS SHARE",
    2: "ROW SHARE",
    3: "ROW EXCLUSIVE",
    4: "SHARE UPDATE EXCLUSIVE",
    5: "SHARE",
    6: "SHARE ROW EXCLUSIVE",
    7: "EXCLUSIVE",
    8: "ACCESS EXCLUSIVE",
}

# FunctionParameter mode -> наша строка
_FUNC_PARAM_MODE: dict[str, str] = {
    "FUNC_PARAM_DEFAULT":  "IN",
    "FUNC_PARAM_IN":       "IN",
    "FUNC_PARAM_OUT":      "OUT",
    "FUNC_PARAM_INOUT":    "INOUT",
    "FUNC_PARAM_VARIADIC": "VARIADIC",
    "FUNC_PARAM_TABLE":    "TABLE",
}
# ASCII-значения символов режима
_FUNC_PARAM_MODE_CHR: dict[int, str] = {
    100: "IN",        # 'd' (DEFAULT)
    105: "IN",        # 'i'
    111: "OUT",       # 'o'
    98:  "INOUT",     # 'b'
    118: "VARIADIC",  # 'v'
    116: "TABLE",     # 't'
}

# IndexElem ordering
_SORTBY_DIR  = {1: "ASC", 2: "DESC"}
_SORTBY_NULS = {1: "FIRST", 2: "LAST"}

# ObjectType prefix для GRANT
_OBJECT_TYPE_PREFIX = "OBJECT_"

def parse_sql(sql: str, dialect: str = "postgres") -> Script:
    """Разобрать SQL-строку и вернуть дерево AST нашей разработки.

    Args:
        sql:     SQL-текст (может содержать несколько операторов через `;`).
        dialect: Диалект источника. Сейчас поддерживается только ``"postgres"``.

    Returns:
        :class:`~src.ast.Script` с dialect=POSTGRES.

    Raises:
        ValueError: если dialect не поддерживается.
        pglast.Error: при синтаксической ошибке в SQL.
    """
    if dialect != "postgres":
        raise ValueError(f"Unsupported dialect: {dialect!r}. Only 'postgres' is supported.")

    raw_stmts = pglast.parse_sql(sql)
    conv = PglastConverter(sql)

    if raw_stmts is None:
        return conv._make(Script, source_text=sql)

    statements: list[Statement] = []
    for rs in raw_stmts:
        stmt = conv._dispatch_stmt(rs.stmt)
        if rs.stmt_location is not None:
            end = rs.stmt_location + (rs.stmt_len or 0)
            stmt.source_span = conv._span(rs.stmt_location, end or None)
        statements.append(stmt)

    return conv._make(Script, statements=statements, source_text=sql)

class PglastConverter:
    """Преобразует pglast AST в AST нашей разработки"""
    def __init__(self, source_text: str) -> None:
        self._text = source_text
        self._line_starts: list[int] = [0]
        for i, ch in enumerate(source_text):
            if ch == "\n":
                self._line_starts.append(i + 1)
    
    # Утилиты

    def _make(self, cls: type, **kwargs) -> object:
        """Создать узел, выставить node_kind и dialect=POSTGRES"""
        obj = cls(**kwargs)
        obj.node_kind = cls.__name__
        obj.dialect = Dialect.POSTGRES
        return obj

    def _pos(self, offset: int) -> Position:
        line = bisect.bisect_right(self._line_starts, offset)
        col  = offset - self._line_starts[line - 1] + 1
        return Position(offset=offset, line=line, column=col)

    def _span(self, start: Optional[int], end: Optional[int] = None) -> Optional[Span]:
        if start is None:
            return None
        p_start = self._pos(start)
        p_end   = self._pos(end) if end is not None else p_start
        return Span(start=p_start, end=p_end)

    def _ident(self, name: str, quoted: bool = False) -> Identifier:
        return self._make(Identifier, name=name, quoted=quoted)

    def _alias(self, alias_node) -> Optional[Identifier]:
        if alias_node is None:
            return None
        return self._ident(alias_node.aliasname)

    def _col_aliases(self, alias_node) -> list[Identifier]:
        if alias_node is None or alias_node.colnames is None:
            return []
        return [self._ident(s.sval) for s in alias_node.colnames]

    def _sval(self, node) -> str:
        return node.sval

    def _defelem_sval(self, opt) -> Optional[str]:
        """Безопасно извлечь строковое значение из DefElem.arg"""
        val = getattr(opt, "arg", None)
        if val is None:
            return None
        if hasattr(val, "sval"):
            return val.sval
        if hasattr(val, "ival"):
            return str(val.ival)
        if hasattr(val, "boolval"):
            return str(val.boolval)
        return str(val)

    def _defelem_ival(self, opt) -> Optional[int]:
        """Безопасно извлечь целочисленное значение из DefElem.arg"""
        val = getattr(opt, "arg", None)
        if val is None:
            return None
        if hasattr(val, "ival"):
            return val.ival
        return None

    def _int_val(self, v) -> Optional[int]:
        if v is None:
            return None
        if hasattr(v, "ival"):
            return v.ival
        if isinstance(v, int):
            return v
        return None

    # Диспетчер выражений
    _EXPR_DISPATCH: dict[str, str] = {
        "A_Const":          "_conv_a_const",
        "ColumnRef":        "_conv_col_ref",
        "A_Expr":           "_conv_a_expr",
        "BoolExpr":         "_conv_bool_expr",
        "NullTest":         "_conv_null_test",
        "BooleanTest":      "_conv_bool_test",
        "FuncCall":         "_conv_func_call",
        "TypeCast":         "_conv_type_cast",
        "CaseExpr":         "_conv_case_expr",
        "SubLink":          "_conv_sub_link",
        "ParamRef":         "_conv_param_ref",
        "RowExpr":          "_conv_row_expr",
        "A_ArrayExpr":      "_conv_a_array_expr",
        "CoalesceExpr":     "_conv_coalesce_expr",
        "MinMaxExpr":       "_conv_min_max_expr",
        "SQLValueFunction": "_conv_sql_value_func",
        "A_Indirection":    "_conv_a_indirection",
        "GroupingFunc":     "_conv_grouping_func",
        "SetToDefault":     "_conv_set_to_default",
    }

    def _conv_expr(self, node) -> Expression:
        if node is None:
            return None
        name = type(node).__name__
        method = self._EXPR_DISPATCH.get(name)
        if method:
            return getattr(self, method)(node)
        warnings.warn(
            f"PglastConverter: unknown expression node type {name!r}; "
            f"converting to raw Literal",
            stacklevel=2,
        )
        return self._make(Literal, value=repr(node), literal_kind="raw")

    # Конкретные конвертеры выражений

    def _conv_a_const(self, node: pg.A_Const) -> Literal:
        if node.isnull:
            return self._make(Literal, value=None, literal_kind="null")
        val = node.val
        vname = type(val).__name__
        if vname == "Integer":
            return self._make(Literal, value=val.ival, literal_kind="int",
                              source_span=self._span(getattr(node, "location", None)))
        if vname == "Float":
            return self._make(Literal, value=float(val.fval), literal_kind="float",
                              raw=val.fval,
                              source_span=self._span(getattr(node, "location", None)))
        if vname == "String":
            return self._make(Literal, value=val.sval, literal_kind="string",
                              quote_style="single",
                              source_span=self._span(getattr(node, "location", None)))
        if vname == "Boolean":
            return self._make(Literal, value=val.boolval, literal_kind="bool",
                              source_span=self._span(getattr(node, "location", None)))
        return self._make(Literal, value=repr(val), literal_kind="raw")

    def _conv_col_ref(self, node: pg.ColumnRef) -> ColumnRef | StarExpr:
        fields = node.fields
        loc = self._span(getattr(node, "location", None))

        if len(fields) == 1 and type(fields[0]).__name__ == "A_Star":
            return self._make(StarExpr, source_span=loc)
        if len(fields) == 2 and type(fields[-1]).__name__ == "A_Star":
            return self._make(StarExpr,
                              table=self._ident(fields[0].sval),
                              source_span=loc)

        names = [f.sval for f in fields]
        n = len(names)
        if n == 1:
            db, sc, tb, col = None, None, None, names[0]
        elif n == 2:
            db, sc, tb, col = None, None, names[0], names[1]
        elif n == 3:
            db, sc, tb, col = None, names[0], names[1], names[2]
        elif n >= 4:
            db, sc, tb, col = names[0], names[1], names[2], names[3]
        else:
            db, sc, tb, col = None, None, None, names[-1] if names else ""
        return self._make(
            ColumnRef,
            database=self._ident(db) if db else None,
            schema  =self._ident(sc) if sc else None,
            table   =self._ident(tb) if tb else None,
            column  =self._ident(col) if col else None,
            source_span=loc,
        )

    def _extract_like_pattern_escape(self, rexpr) -> tuple:
        """Определить, является ли rexpr вызовом *_escape(pattern, escape).

        Возвращает ``(pattern_node, escape_node)``. Если ESCAPE нет —
        ``(rexpr, None)``.
        """
        if rexpr is None:
            return None, None
        if type(rexpr).__name__ == "FuncCall":
            parts = [s.sval for s in (rexpr.funcname or [])]
            fname = parts[-1] if parts else ""
            if "escape" in fname.lower():
                args = list(rexpr.args or [])
                if len(args) >= 2:
                    return args[0], args[1]
        return rexpr, None

    def _conv_a_expr(self, node: pg.A_Expr) -> Expression:
        kind_val = node.kind.value
        op_name  = node.name[0].sval if node.name else "?"
        loc      = self._span(getattr(node, "location", None))

        # BETWEEN (10=BETWEEN, 11=NOT BETWEEN, 12=BETWEEN SYMMETRIC, 13=NOT BETWEEN SYMMETRIC)
        if kind_val in (10, 11, 12, 13):
            rexpr = node.rexpr
            return self._make(
                BetweenExpr,
                expr     =self._conv_expr(node.lexpr),
                low      =self._conv_expr(rexpr[0]),
                high     =self._conv_expr(rexpr[1]),
                negated  =kind_val in (11, 13),
                symmetric=kind_val in (12, 13),
                source_span=loc,
            )

        # IN / NOT IN
        if kind_val == 6:
            is_not = (op_name == "<>")
            items = [self._conv_expr(e) for e in (node.rexpr or [])]
            return self._make(
                BinaryOp,
                op   ="NOT IN" if is_not else "IN",
                left =self._conv_expr(node.lexpr),
                right=self._make(TupleConstructor, elements=items),
                source_span=loc,
            )

        # ANY / ALL
        if kind_val in (1, 2):
            suffix = " ANY" if kind_val == 1 else " ALL"
            return self._make(
                BinaryOp,
                op   =op_name + suffix,
                left =self._conv_expr(node.lexpr),
                right=self._conv_expr(node.rexpr),
                source_span=loc,
            )

        # NULLIF
        if kind_val == 5:
            return self._make(
                FunctionCall,
                name=self._ident("NULLIF"),
                args=[self._conv_expr(node.lexpr), self._conv_expr(node.rexpr)],
                source_span=loc,
            )

        # LIKE / NOT LIKE
        if kind_val == 7:
            negated = op_name.startswith("!")
            pat_raw, esc_raw = self._extract_like_pattern_escape(node.rexpr)
            return self._make(
                LikeExpr,
                string          =self._conv_expr(node.lexpr),
                pattern         =self._conv_expr(pat_raw),
                escape          =self._conv_expr(esc_raw) if esc_raw is not None else None,
                negated         =negated,
                case_insensitive=False,
                source_span     =loc,
            )

        # ILIKE / NOT ILIKE
        if kind_val == 8:
            negated = op_name.startswith("!")
            pat_raw, esc_raw = self._extract_like_pattern_escape(node.rexpr)
            return self._make(
                LikeExpr,
                string          =self._conv_expr(node.lexpr),
                pattern         =self._conv_expr(pat_raw),
                escape          =self._conv_expr(esc_raw) if esc_raw is not None else None,
                negated         =negated,
                case_insensitive=True,
                source_span     =loc,
            )

        # SIMILAR TO / NOT SIMILAR TO (9)
        if kind_val == 9:
            negated = op_name.startswith("!")
            pat_raw, esc_raw = self._extract_like_pattern_escape(node.rexpr)
            return self._make(
                SimilarToExpr,
                string =self._conv_expr(node.lexpr),
                pattern=self._conv_expr(pat_raw),
                escape =self._conv_expr(esc_raw) if esc_raw is not None else None,
                negated=negated,
                source_span=loc,
            )

        op_map = {
            3: "IS DISTINCT FROM",
            4: "IS NOT DISTINCT FROM",
        }
        op_str = op_map.get(kind_val, op_name)

        return self._make(
            BinaryOp,
            op   =op_str,
            left =self._conv_expr(node.lexpr) if node.lexpr is not None else None,
            right=self._conv_expr(node.rexpr) if node.rexpr is not None else None,
            source_span=loc,
        )

    def _conv_bool_expr(self, node: pg.BoolExpr) -> Expression:
        boolop = node.boolop.value
        loc    = self._span(getattr(node, "location", None))

        if boolop == 2:  # NOT_EXPR
            return self._make(
                UnaryOp,
                op="NOT", position="prefix",
                operand=self._conv_expr(node.args[0]),
                source_span=loc,
            )

        op_str = "AND" if boolop == 0 else "OR"
        args = [self._conv_expr(a) for a in node.args]
        result = args[0]
        for arg in args[1:]:
            result = self._make(BinaryOp, op=op_str, left=result, right=arg,
                                source_span=loc)
        return result

    def _conv_null_test(self, node: pg.NullTest) -> UnaryOp:
        op = "IS NULL" if node.nulltesttype.value == 0 else "IS NOT NULL"
        return self._make(
            UnaryOp, op=op, position="postfix",
            operand=self._conv_expr(node.arg),
            source_span=self._span(getattr(node, "location", None)),
        )

    def _conv_bool_test(self, node: pg.BooleanTest) -> UnaryOp:
        _BT = {0: "IS TRUE", 1: "IS NOT TRUE", 2: "IS FALSE",
               3: "IS NOT FALSE", 4: "IS UNKNOWN", 5: "IS NOT UNKNOWN"}
        op = _BT.get(node.booltesttype.value, "IS ?")
        return self._make(
            UnaryOp, op=op, position="postfix",
            operand=self._conv_expr(node.arg),
            source_span=self._span(getattr(node, "location", None)),
        )

    def _conv_func_call(self, node: pg.FuncCall) -> FunctionCall:
        parts = [s.sval for s in (node.funcname or [])]
        fn_name = self._ident(parts[-1]) if parts else self._ident("?")
        if len(parts) > 1 and parts[0] != "pg_catalog":
            fn_name = self._ident(".".join(parts))

        args = [self._conv_expr(a) for a in (node.args or [])]
        order_by = [self._conv_sort_by(s) for s in (node.agg_order or [])]
        over = self._conv_window_spec(node.over) if node.over else None
        filter_where = self._conv_expr(node.agg_filter) if node.agg_filter else None

        return self._make(
            FunctionCall,
            name        =fn_name,
            args        =args,
            distinct    =bool(node.agg_distinct),
            star        =bool(node.agg_star),
            variadic    =bool(node.func_variadic),
            order_by    =order_by,
            filter_where=filter_where,
            over        =over,
            source_span =self._span(getattr(node, "location", None)),
        )

    def _conv_type_cast(self, node: pg.TypeCast) -> Cast:
        return self._make(
            Cast,
            expression =self._conv_expr(node.arg),
            target_type=self._conv_typename(node.typeName),
            style      ="cast",
            source_span=self._span(getattr(node, "location", None)),
        )

    def _conv_case_expr(self, node: pg.CaseExpr) -> CaseExpr:
        branches = []
        for w in (node.args or []):
            branches.append(self._make(
                WhenBranch,
                condition=self._conv_expr(w.expr),
                result   =self._conv_expr(w.result),
            ))
        return self._make(
            CaseExpr,
            arg      =self._conv_expr(node.arg) if node.arg else None,
            branches =branches,
            else_expr=self._conv_expr(node.defresult) if node.defresult else None,
            source_span=self._span(getattr(node, "location", None)),
        )

    def _conv_sub_link(self, node: pg.SubLink) -> Expression:
        slt = node.subLinkType.value
        query = self._conv_select(node.subselect)

        if slt == 0:  # EXISTS
            return self._make(SubqueryExpr, kind="exists", query=query,
                              source_span=self._span(getattr(node, "location", None)))
        if slt == 2:  # ANY / IN
            op_name = node.operName[0].sval if node.operName else None
            return self._make(SubqueryExpr, kind="any", query=query,
                              outer_op=op_name,
                              source_span=self._span(getattr(node, "location", None)))
        if slt == 1:  # ALL
            op_name = node.operName[0].sval if node.operName else None
            return self._make(SubqueryExpr, kind="all", query=query,
                              outer_op=op_name,
                              source_span=self._span(getattr(node, "location", None)))
        if slt == 6:  # ARRAY subquery
            return self._make(ArrayConstructor,
                              elements=[self._make(SubqueryExpr, kind="scalar", query=query)],
                              syntax="array_kw")
        # Scalar (EXPR_SUBLINK=4)
        return self._make(SubqueryExpr, kind="scalar", query=query,
                          source_span=self._span(getattr(node, "location", None)))

    def _conv_param_ref(self, node: pg.ParamRef) -> ParamRef:
        return self._make(ParamRef,
                          number=getattr(node, "number", None),
                          source_span=self._span(getattr(node, "location", None)))

    def _conv_row_expr(self, node: pg.RowExpr) -> TupleConstructor:
        args = [self._conv_expr(a) for a in (node.args or [])]
        syntax = "row_kw" if getattr(node, "row_format", None) != 2 else "parens"
        return self._make(TupleConstructor, elements=args, syntax=syntax,
                          source_span=self._span(getattr(node, "location", None)))

    def _conv_a_array_expr(self, node) -> ArrayConstructor:
        elems = [self._conv_expr(e) for e in (node.elements or [])]
        return self._make(ArrayConstructor, elements=elems, syntax="array_kw",
                          source_span=self._span(getattr(node, "location", None)))

    def _conv_coalesce_expr(self, node) -> FunctionCall:
        args = [self._conv_expr(a) for a in (node.args or [])]
        return self._make(FunctionCall,
                          name=self._ident("COALESCE"), args=args,
                          source_span=self._span(getattr(node, "location", None)))

    def _conv_min_max_expr(self, node) -> FunctionCall:
        fn = "GREATEST" if node.op.value == 0 else "LEAST"
        args = [self._conv_expr(a) for a in (node.args or [])]
        return self._make(FunctionCall,
                          name=self._ident(fn), args=args,
                          source_span=self._span(getattr(node, "location", None)))

    def _conv_sql_value_func(self, node) -> FunctionCall:
        fn_name = _SVF_NAMES.get(node.op.name, node.op.name)
        return self._make(FunctionCall,
                          name=self._ident(fn_name),
                          source_span=self._span(getattr(node, "location", None)))

    def _conv_a_indirection(self, node) -> Expression:
        base = self._conv_expr(node.arg)
        result = base
        for step in (node.indirection or []):
            sname = type(step).__name__
            if sname == "String":
                field = self._ident(step.sval)
                if isinstance(result, ColumnRef):
                    result = self._make(ColumnRef,
                                        database=result.database,
                                        schema  =result.schema,
                                        table   =result.table,
                                        column  =field)
                else:
                    result = self._make(BinaryOp, op=".", left=result, right=field)
            elif sname == "A_Indices":
                idx = self._conv_expr(step.uidx) if step.uidx is not None else None
                if step.is_slice:
                    lo = self._conv_expr(step.lidx) if step.lidx is not None else None
                    result = self._make(BinaryOp, op="[:]",
                                        left=result,
                                        right=self._make(TupleConstructor,
                                                         elements=[lo, idx]))
                else:
                    result = self._make(BinaryOp, op="[]", left=result, right=idx)
        return result

    def _conv_grouping_func(self, node) -> FunctionCall:
        args = [self._conv_expr(a) for a in (node.args or [])]
        return self._make(FunctionCall,
                          name=self._ident("GROUPING"), args=args,
                          source_span=self._span(getattr(node, "location", None)))

    def _conv_set_to_default(self, node) -> Literal:
        return self._make(Literal, value="DEFAULT", literal_kind="raw")

    # Конвертеры FROM-элементов

    def _conv_from_item(self, node) -> FromItem:
        name = type(node).__name__
        if name == "RangeVar":
            return self._conv_range_var(node)
        if name == "JoinExpr":
            return self._conv_join_expr(node)
        if name == "RangeSubselect":
            return self._conv_range_subselect(node)
        if name == "RangeFunction":
            return self._conv_range_function(node)
        warnings.warn(f"PglastConverter: unknown FROM item type {name!r}", stacklevel=2)
        return self._make(TableRef, name=self._ident(repr(node)))

    def _conv_range_var(self, node: pg.RangeVar) -> TableRef:
        return self._make(
            TableRef,
            database       =self._ident(node.catalogname) if node.catalogname else None,
            schema         =self._ident(node.schemaname)  if node.schemaname  else None,
            name           =self._ident(node.relname),
            alias          =self._alias(node.alias),
            column_aliases =self._col_aliases(node.alias),
            only           =not bool(getattr(node, "inh", True)),
            source_span    =self._span(getattr(node, "location", None)),
        )

    def _conv_join_expr(self, node: pg.JoinExpr) -> JoinExpr:
        jtype = node.jointype.value
        kind = _JOIN_KIND.get(jtype, "inner")
        if getattr(node, "isNatural", False) and jtype == 0:
            kind = "natural_inner"

        using: list[Identifier] = []
        if node.usingClause:
            using = [self._ident(s.sval) for s in node.usingClause]

        return self._make(
            JoinExpr,
            kind   =kind,
            left   =self._conv_from_item(node.larg),
            right  =self._conv_from_item(node.rarg),
            on     =self._conv_expr(node.quals) if node.quals else None,
            using  =using,
            lateral=bool(getattr(node, "lateral", False)),
        )

    def _conv_range_subselect(self, node: pg.RangeSubselect) -> SubqueryRef:
        return self._make(
            SubqueryRef,
            query         =self._conv_select(node.subquery),
            alias         =self._alias(node.alias),
            column_aliases=self._col_aliases(node.alias),
            lateral       =bool(getattr(node, "lateral", False)),
        )

    def _conv_range_function(self, node) -> TableFunctionRef:
        func_call = self._conv_func_call(node.functions[0][0])
        return self._make(
            TableFunctionRef,
            call           =func_call,
            alias          =self._alias(node.alias),
            column_aliases =self._col_aliases(node.alias),
            with_ordinality=bool(getattr(node, "ordinality", False)),
            lateral        =bool(getattr(node, "lateral", False)),
        )

    # Клаузы

    def _conv_sort_by(self, node: pg.SortBy) -> OrderByItem:
        dir_val  = node.sortby_dir.value
        null_val = node.sortby_nulls.value
        return self._make(
            OrderByItem,
            expression=self._conv_expr(node.node),
            direction =("ASC" if dir_val == 1 else "DESC") if dir_val in (1, 2) else None,
            nulls     =("FIRST" if null_val == 1 else "LAST") if null_val in (1, 2) else None,
        )

    def _conv_window_spec(self, node: pg.WindowDef) -> WindowSpec:
        part_by  = [self._conv_expr(e) for e in (node.partitionClause or [])]
        order_by = [self._conv_sort_by(s) for s in (node.orderClause or [])]
        frame    = self._decode_frame(
            node.frameOptions or 0,
            getattr(node, "startOffset", None),
            getattr(node, "endOffset", None),
        )
        existing = self._ident(node.refname) if node.refname else None
        return self._make(
            WindowSpec,
            existing_name=existing,
            partition_by =part_by,
            order_by     =order_by,
            frame        =frame,
        )

    def _decode_frame(self, fo: int, start_node, end_node) -> Optional[FrameSpec]:
        if not (fo & _FO_NONDEFAULT):
            return None

        unit = "ROWS" if (fo & _FO_ROWS) else ("GROUPS" if (fo & _FO_GROUPS) else "RANGE")
        start = self._decode_frame_bound(fo, start_node, is_start=True)
        end   = self._decode_frame_bound(fo, end_node, is_start=False) \
                if (fo & _FO_BETWEEN) else None

        exclude = None
        if fo & _FO_EXCL_CURR_ROW: exclude = "CURRENT_ROW"
        elif fo & _FO_EXCL_GROUP:  exclude = "GROUP"
        elif fo & _FO_EXCL_TIES:   exclude = "TIES"

        return self._make(FrameSpec, unit=unit, start=start, end=end, exclude=exclude)

    def _decode_frame_bound(self, fo: int, offset_node, is_start: bool) -> FrameBound:
        if is_start:
            if fo & _FO_START_UNB_PRE:   kind = "UNBOUNDED_PRECEDING"
            elif fo & _FO_START_UNB_FOL: kind = "UNBOUNDED_FOLLOWING"
            elif fo & _FO_START_CURR:    kind = "CURRENT_ROW"
            elif fo & _FO_START_OFF_PRE: kind = "N_PRECEDING"
            elif fo & _FO_START_OFF_FOL: kind = "N_FOLLOWING"
            else:                         kind = "CURRENT_ROW"
        else:
            if fo & _FO_END_UNB_FOL:    kind = "UNBOUNDED_FOLLOWING"
            elif fo & _FO_END_UNB_PRE:  kind = "UNBOUNDED_PRECEDING"
            elif fo & _FO_END_CURR:     kind = "CURRENT_ROW"
            elif fo & _FO_END_OFF_PRE:  kind = "N_PRECEDING"
            elif fo & _FO_END_OFF_FOL:  kind = "N_FOLLOWING"
            else:                        kind = "CURRENT_ROW"
        offset = self._conv_expr(offset_node) if offset_node is not None else None
        return self._make(FrameBound, kind=kind, offset=offset)

    def _conv_with_clause(self, node) -> Optional[WithClause]:
        if node is None:
            return None
        ctes = [self._conv_cte(c) for c in (node.ctes or [])]
        return self._make(WithClause, recursive=bool(node.recursive), ctes=ctes)

    def _conv_cte(self, node) -> CommonTableExpr:
        mat_val = getattr(node, "ctematerialized", None)
        materialized = None
        if mat_val is not None:
            mat_int = mat_val.value if hasattr(mat_val, "value") else mat_val
            if mat_int == 1:   materialized = True
            elif mat_int == 2: materialized = False
        return self._make(
            CommonTableExpr,
            name        =self._ident(node.ctename),
            query       =self._conv_select(node.ctequery),
            materialized=materialized,
        )

    def _conv_locking_clause(self, node) -> LockingClause:
        mode = _LOCK_MODE.get(node.strength.value, "UPDATE")
        wait_val = getattr(node, "waitPolicy", None)
        wait = None
        if wait_val is not None:
            w = wait_val.value if hasattr(wait_val, "value") else wait_val
            if w == 1:   wait = "SKIP_LOCKED"
            elif w == 2: wait = "NOWAIT"
        tables = [self._conv_range_var(r) for r in (node.lockedRels or [])]
        return self._make(LockingClause, mode=mode, tables=tables, wait=wait)

    def _conv_on_conflict(self, node) -> OnConflictClause:
        action_val = node.action.value
        action = "nothing" if action_val == 1 else "update"
        target = None
        if node.infer:
            if getattr(node.infer, "conname", None):
                target = self._make(Literal, value=node.infer.conname,
                                    literal_kind="string")
            elif getattr(node.infer, "indexElems", None):
                items = [
                    self._ident(e.name) if getattr(e, "name", None)
                    else self._conv_expr(e.expr)
                    for e in node.infer.indexElems
                ]
                target = self._make(TupleConstructor, elements=items)
        updates = []
        for rt in (node.targetList or []):
            updates.append(self._make(
                SettingAssignment,
                name =rt.name or "",
                value=self._conv_expr(rt.val),
            ))
        where = self._conv_expr(
            node.whereClause if hasattr(node, "whereClause") else None
        )
        return self._make(OnConflictClause,
                          target=target, action=action,
                          updates=updates, where=where)

    # DDL — типы и столбцы

    def _conv_typename(self, node) -> TypeRef:
        names = [s.sval for s in (node.names or [])]
        if names and names[0] == "pg_catalog":
            schema = None
            raw_name = names[-1]
        elif len(names) > 1:
            schema = names[0]
            raw_name = names[-1]
        else:
            schema = None
            raw_name = names[0] if names else ""

        norm = _PG_TYPE_NORM.get(raw_name)
        if isinstance(norm, tuple):
            type_name, time_zone = norm
        elif isinstance(norm, str):
            type_name, time_zone = norm, None
        else:
            type_name = raw_name.upper() if raw_name else ""
            time_zone = None

        params = [self._conv_expr(m) for m in (node.typmods or [])]
        array_dims = len(node.arrayBounds) if node.arrayBounds else 0

        return self._make(
            TypeRef,
            name      =type_name,
            schema    =schema,
            params    =params,
            array_dims=array_dims,
            time_zone =time_zone,
            source_span=self._span(getattr(node, "location", None)),
        )

    def _conv_column_def(self, node) -> ColumnDef:
        constraints = [c for c in
                       [self._conv_constraint_col(cn) for cn in (node.constraints or [])]
                       if c is not None]
        storage_char = getattr(node, "storage", "\x00") or "\x00"
        storage = _STORAGE_MAP.get(storage_char)
        collation = node.collClause.arg[0].sval \
                    if node.collClause and node.collClause.arg else None
        return self._make(
            ColumnDef,
            name       =self._ident(node.colname),
            type       =self._conv_typename(node.typeName),
            constraints=constraints,
            collation  =collation,
            storage    =storage,
            source_span=self._span(getattr(node, "location", None)),
        )

    def _conv_constraint_col(self, node) -> Optional[ColumnConstraint]:
        ct = node.contype.value
        name = getattr(node, "conname", None)
        loc  = self._span(getattr(node, "location", None))

        if ct == 0:  # CONSTR_NULL
            return self._make(ColumnConstraint, kind="null", name=name, source_span=loc)
        if ct == 1:  # CONSTR_NOTNULL
            return self._make(ColumnConstraint, kind="not_null", name=name, source_span=loc)
        if ct == 2:  # CONSTR_DEFAULT
            return self._make(ColumnConstraint, kind="default", name=name,
                              expression=self._conv_expr(node.raw_expr), source_span=loc)
        if ct == 3:  # CONSTR_IDENTITY
            mode = "ALWAYS" if getattr(node, "generated_when", "") == "a" else "BY_DEFAULT"
            return self._make(ColumnConstraint, kind="generated_identity",
                              name=name, identity_mode=mode, source_span=loc)
        if ct == 4:  # CONSTR_GENERATED
            return self._make(ColumnConstraint, kind="generated_stored",
                              name=name,
                              expression=self._conv_expr(node.raw_expr),
                              source_span=loc)
        if ct == 5:  # CONSTR_CHECK
            return self._make(ColumnConstraint, kind="check", name=name,
                              expression=self._conv_expr(node.raw_expr), source_span=loc)
        if ct == 6:  # CONSTR_PRIMARY
            return self._make(ColumnConstraint, kind="primary_key", name=name, source_span=loc)
        if ct == 7:  # CONSTR_UNIQUE
            nulls_dist = getattr(node, "nulls_not_distinct", None)
            nulls_distinct = not nulls_dist if nulls_dist is not None else None
            return self._make(ColumnConstraint, kind="unique", name=name,
                              nulls_distinct=nulls_distinct, source_span=loc)
        if ct == 9:  # CONSTR_FOREIGN
            ref_table = self._conv_range_var(node.pktable) if node.pktable else None
            ref_cols  = [self._ident(s.sval) for s in (node.pk_attrs or [])]
            del_char  = getattr(node, "fk_del_action", "a") or "a"
            upd_char  = getattr(node, "fk_upd_action", "a") or "a"
            match_char = getattr(node, "fk_matchtype", "s") or "s"
            return self._make(
                ColumnConstraint, kind="references", name=name,
                ref_table  =ref_table,
                ref_columns=ref_cols,
                on_delete  =_FK_ACTION.get(del_char),
                on_update  =_FK_ACTION.get(upd_char),
                match      =_FK_MATCH.get(match_char),
                deferrable =bool(getattr(node, "deferrable", False)),
                initially  ="DEFERRED" if getattr(node, "initdeferred", False) else None,
                source_span=loc,
            )
        return None

    def _conv_constraint_table(self, node) -> Optional[TableConstraint]:
        ct   = node.contype.value
        name = getattr(node, "conname", None)
        loc  = self._span(getattr(node, "location", None))

        if ct == 5:  # CHECK
            return self._make(TableConstraint, kind="check", name=name,
                              expression=self._conv_expr(node.raw_expr), source_span=loc)
        if ct == 6:  # PRIMARY KEY
            cols = [self._ident(s.sval) for s in (node.keys or [])]
            inc  = [self._ident(s.sval) for s in (getattr(node, "including", None) or [])]
            return self._make(TableConstraint, kind="primary_key", name=name,
                              columns=cols, include_columns=inc, source_span=loc)
        if ct == 7:  # UNIQUE
            cols = [self._ident(s.sval) for s in (node.keys or [])]
            inc  = [self._ident(s.sval) for s in (getattr(node, "including", None) or [])]
            nulls_dist = getattr(node, "nulls_not_distinct", None)
            return self._make(TableConstraint, kind="unique", name=name,
                              columns=cols, include_columns=inc,
                              nulls_distinct=not nulls_dist if nulls_dist else None,
                              source_span=loc)
        if ct == 9:  # FOREIGN KEY
            cols      = [self._ident(s.sval) for s in (node.fk_attrs or [])]
            ref_table = self._conv_range_var(node.pktable) if node.pktable else None
            ref_cols  = [self._ident(s.sval) for s in (node.pk_attrs or [])]
            del_char  = getattr(node, "fk_del_action", "a") or "a"
            upd_char  = getattr(node, "fk_upd_action", "a") or "a"
            return self._make(
                TableConstraint, kind="foreign_key", name=name,
                columns    =cols,
                ref_table  =ref_table,
                ref_columns=ref_cols,
                on_delete  =_FK_ACTION.get(del_char),
                on_update  =_FK_ACTION.get(upd_char),
                source_span=loc,
            )
        if ct == 8:  # EXCLUDE
            excl_elements = []
            for pair in (getattr(node, "exclusions", None) or []):
                if isinstance(pair, (list, tuple)) and len(pair) >= 2:
                    index_elem, op_list = pair[0], pair[1]
                    excl_elements.append(
                        self._conv_exclude_element(index_elem, op_list)
                    )
            return self._make(TableConstraint, kind="exclude", name=name,
                              exclude_elements=excl_elements, source_span=loc)
        return None

    def _conv_exclude_element(self, index_elem, op_list) -> ExcludeElement:
        """Конвертировать пару (IndexElem, [оператор]) -> ExcludeElement"""
        if getattr(index_elem, "name", None):
            expr = self._make(ColumnRef, column=self._ident(index_elem.name))
        elif getattr(index_elem, "expr", None):
            expr = self._conv_expr(index_elem.expr)
        else:
            expr = self._make(Literal, value="?", literal_kind="raw")

        if op_list:
            op_parts = [s.sval for s in op_list if hasattr(s, "sval")]
            op_str = ".".join(op_parts) if op_parts else "="
        else:
            op_str = "="
        return self._make(ExcludeElement, expression=expr, operator=op_str)

    def _conv_like_clause(self, node) -> LikeClause:
        source = self._conv_range_var(node.relation)

        opts_val = getattr(node, "options", 0)
        if hasattr(opts_val, "value"):
            opts_val = opts_val.value
        opts_val = opts_val or 0

        if opts_val == 0:
            including, excluding = [], []
        elif opts_val >= _TABLE_LIKE_ALL:
            including, excluding = ["ALL"], []
        else:
            including = [label for bit, label in _TABLE_LIKE_OPTS.items()
                         if opts_val & bit]
            excluding = []
        return self._make(LikeClause, source=source,
                          including=including, excluding=excluding)

    # DDL — вспомогательные конвертеры индексных элементов и аргументов функций

    def _conv_index_elem(self, node) -> IndexColumn:
        """IndexElem -> IndexColumn"""
        if getattr(node, "name", None):
            expr = self._make(ColumnRef, column=self._ident(node.name))
        elif getattr(node, "expr", None):
            expr = self._conv_expr(node.expr)
        else:
            expr = self._make(Literal, value="?", literal_kind="raw")

        dir_node  = getattr(node, "ordering", None)
        null_node = getattr(node, "nulls_ordering", None)

        dir_val  = (dir_node.value  if hasattr(dir_node,  "value") else dir_node)  or 0
        null_val = (null_node.value if hasattr(null_node, "value") else null_node) or 0

        direction = _SORTBY_DIR.get(dir_val)
        nulls     = _SORTBY_NULS.get(null_val)

        collate = None
        if getattr(node, "collation", None):
            collate = ".".join(s.sval for s in node.collation if hasattr(s, "sval"))

        opclass = None
        if getattr(node, "opclass", None):
            opclass = ".".join(s.sval for s in node.opclass if hasattr(s, "sval"))

        return self._make(IndexColumn, expression=expr, opclass=opclass,
                          direction=direction, nulls=nulls, collate=collate)

    def _conv_function_param(self, node) -> FunctionArg:
        """FunctionParameter -> FunctionArg"""
        mode_node = getattr(node, "mode", None)
        mode = "IN"
        if mode_node is not None:
            if hasattr(mode_node, "name"):
                mode = _FUNC_PARAM_MODE.get(mode_node.name, "IN")
            elif isinstance(mode_node, int):
                mode = _FUNC_PARAM_MODE_CHR.get(mode_node, "IN")

        name = self._ident(node.name) if getattr(node, "name", None) else None
        arg_type = self._conv_typename(node.argType) if getattr(node, "argType", None) else None
        default  = self._conv_expr(node.defexpr)  if getattr(node, "defexpr", None) else None

        return self._make(FunctionArg, name=name, type=arg_type, mode=mode, default=default)

    # Диспетчер операторов

    def _dispatch_stmt(self, node) -> Statement:
        name = type(node).__name__
        if name == "SelectStmt":
            return self._conv_select(node)
        if name == "InsertStmt":
            return self._conv_insert(node)
        if name == "CreateStmt":
            return self._conv_create_table(node)
        if name == "ViewStmt":
            return self._conv_create_view(node)
        if name == "CreateTableAsStmt":
            return self._conv_create_table_as(node)
        if name == "IndexStmt":
            return self._conv_create_index(node)
        if name == "CreateFunctionStmt":
            return self._conv_create_function(node)
        if name == "CreatedbStmt":
            return self._conv_create_database(node)
        if name == "CreateRoleStmt":
            return self._conv_create_role(node)
        if name == "GrantStmt":
            return self._conv_grant(node)
        if name == "GrantRoleStmt":
            return self._conv_grant_role(node)
        if name == "AlterRoleStmt":
            return self._conv_alter_role(node)
        if name == "CopyStmt":
            return self._conv_copy(node)
        if name == "MergeStmt":
            return self._conv_merge(node)
        if name == "LockStmt":
            return self._conv_lock_table(node)
        if name == "ConstraintsSetStmt":
            return self._conv_set_constraints(node)
        if name == "TransactionStmt":
            return self._conv_transaction(node)
        if name == "VariableSetStmt":
            return self._conv_variable_set(node)
        warnings.warn(
            f"PglastConverter: unsupported statement type {name!r}; "
            f"wrapping in RawStatement",
            stacklevel=2,
        )
        return self._make(RawStatement, text=repr(node), origin_dialect=Dialect.POSTGRES)

    # Конвертеры операторов — DML

    def _conv_select(self, node) -> SelectStmt:
        op_val = node.op.value if node.op else 0

        if op_val != 0:
            return self._conv_set_op(node)

        targets = []
        for rt in (node.targetList or []):
            targets.append(self._make(
                SelectTarget,
                expression=self._conv_expr(rt.val),
                alias     =self._ident(rt.name) if rt.name else None,
            ))

        distinct   = self._conv_distinct(node.distinctClause)
        from_items = [self._conv_from_item(f) for f in (node.fromClause or [])]

        group_by = None
        if node.groupClause:
            group_by = self._make(
                GroupByClause,
                kind ="distinct" if getattr(node, "groupDistinct", False) else "ordinary",
                items=[self._conv_expr(e) for e in node.groupClause],
            )

        windows = []
        for wd in (node.windowClause or []):
            if wd.name:
                windows.append(self._make(
                    WindowDef,
                    name=self._ident(wd.name),
                    spec=self._conv_window_spec(wd),
                ))

        order_by = [self._conv_sort_by(s) for s in (node.sortClause or [])]
        limit  = self._conv_expr(node.limitCount)  if node.limitCount  else None
        offset = self._conv_expr(node.limitOffset) if node.limitOffset else None

        fetch = None
        if node.limitOption and node.limitOption.value == 2:
            fetch = self._make(FetchClause, count=limit, with_ties=True)
            limit = None

        locking = [self._conv_locking_clause(lc) for lc in (node.lockingClause or [])]

        return self._make(
            SelectStmt,
            with_clause=self._conv_with_clause(node.withClause),
            distinct   =distinct,
            targets    =targets,
            from_items =from_items,
            where      =self._conv_expr(node.whereClause) if node.whereClause else None,
            group_by   =group_by,
            having     =self._conv_expr(node.havingClause) if node.havingClause else None,
            windows    =windows,
            order_by   =order_by,
            limit      =limit,
            offset     =offset,
            fetch      =fetch,
            locking    =locking,
        )

    def _conv_distinct(self, distinct_clause) -> Optional[DistinctClause]:
        if not distinct_clause:
            return None
        if len(distinct_clause) == 1 and distinct_clause[0] is None:
            return self._make(DistinctClause, kind="distinct")
        return self._make(DistinctClause, kind="distinct_on",
                          on=[self._conv_expr(e) for e in distinct_clause])

    def _conv_set_op(self, node) -> SelectStmt:
        op_val = node.op.value
        op_map = {1: "UNION", 2: "INTERSECT", 3: "EXCEPT"}

        left  = self._conv_select(node.larg)
        right = self._conv_select(node.rarg)

        set_op = self._make(
            SetOpClause,
            op        =op_map.get(op_val, "UNION"),
            quantifier="ALL" if getattr(node, "all", False) else "DISTINCT",
            right     =right,
        )

        last = self._find_chain_tail(left)
        last.set_op = set_op
        return left

    def _find_chain_tail(self, stmt: SelectStmt) -> SelectStmt:
        current = stmt
        while current.set_op is not None:
            current = current.set_op.right
        return current

    def _conv_insert(self, node) -> InsertStmt:
        target = self._conv_range_var(node.relation)
        alias  = self._alias(node.relation.alias) if node.relation.alias else None
        columns = [self._ident(rt.name) for rt in (node.cols or [])]

        source = None
        if node.selectStmt:
            sel = node.selectStmt
            if sel.valuesLists:
                rows = [[self._conv_expr(e) for e in row] for row in sel.valuesLists]
                source = self._make(ValuesClause, rows=rows)
            elif sel.targetList:
                source = self._conv_select(sel)
            else:
                source = self._make(DefaultValues)
        else:
            source = self._make(DefaultValues)

        on_conflict = self._conv_on_conflict(node.onConflictClause) \
                      if node.onConflictClause else None

        returning = []
        for rt in (node.returningList or []):
            returning.append(self._make(
                SelectTarget,
                expression=self._conv_expr(rt.val),
                alias     =self._ident(rt.name) if rt.name else None,
            ))

        overriding = None
        if node.override and node.override.value:
            overriding = "SYSTEM" if node.override.value == 2 else "USER"

        return self._make(
            InsertStmt,
            with_clause=self._conv_with_clause(node.withClause),
            target     =target,
            alias      =alias,
            columns    =columns,
            overriding =overriding,
            source     =source,
            on_conflict=on_conflict,
            returning  =returning,
        )

    # Конвертеры операторов — DDL

    def _conv_create_table(self, node) -> CreateTableStmt:
        table = self._conv_range_var(node.relation)

        columns: list[ColumnDef]    = []
        table_constraints: list     = []
        like_clause                 = None

        for elt in (node.tableElts or []):
            elt_type = type(elt).__name__
            if elt_type == "ColumnDef":
                columns.append(self._conv_column_def(elt))
            elif elt_type == "Constraint":
                tc = self._conv_constraint_table(elt)
                if tc is not None:
                    table_constraints.append(tc)
            elif elt_type == "TableLikeClause":
                like_clause = self._conv_like_clause(elt)

        tablespace = getattr(node, "tablespacename", None)
        on_commit_raw = getattr(node, "oncommit", None)
        on_commit_map = {1: "DROP", 2: "DELETE_ROWS", 3: "PRESERVE_ROWS"}
        on_commit = on_commit_map.get(
            on_commit_raw.value if on_commit_raw and hasattr(on_commit_raw, "value")
            else (on_commit_raw or 0)
        )
        access_method = getattr(node, "accessMethod", None)
        persistence   = getattr(node.relation, "relpersistence", "p") or "p"
        temporary = persistence == "t"
        unlogged  = persistence == "u"

        inherits = [self._conv_range_var(r)
                    for r in (getattr(node, "inhRelations", None) or [])]

        return self._make(
            CreateTableStmt,
            if_not_exists    =bool(getattr(node, "if_not_exists", False)),
            temporary        =temporary,
            unlogged         =unlogged,
            table            =table,
            columns          =columns,
            table_constraints=table_constraints,
            like_clause      =like_clause,
            inherits         =inherits,
            tablespace       =tablespace,
            on_commit        =on_commit,
            using_method     =access_method,
        )

    def _conv_create_view(self, node) -> CreateViewStmt:
        """ViewStmt -> CreateViewStmt (обычное представление)"""
        name  = self._conv_range_var(node.view)
        query = self._conv_select(node.query)

        column_names: list[Identifier] = []
        if getattr(node, "aliases", None):
            column_names = [self._ident(s.sval) for s in node.aliases]

        # WITH CHECK OPTION: 0=нет, 1=LOCAL, 2=CASCADED
        wco = getattr(node, "withCheckOption", 0)
        if hasattr(wco, "value"):
            wco = wco.value
        check_option = {1: "LOCAL", 2: "CASCADED"}.get(wco)

        security_barrier = False
        security_invoker = False
        for opt in (getattr(node, "options", None) or []):
            dn = getattr(opt, "defname", "")
            if dn == "security_barrier":
                security_barrier = True
            elif dn == "security_invoker":
                security_invoker = True

        persistence = getattr(node.view, "relpersistence", "p") or "p"

        return self._make(
            CreateViewStmt,
            is_materialized =False,
            or_replace      =bool(getattr(node, "replace", False)),
            temporary       =persistence == "t",
            recursive       =bool(getattr(node, "isRecursive", False)),
            name            =name,
            column_names    =column_names,
            query           =query,
            check_option    =check_option,
            security_barrier=security_barrier,
            security_invoker=security_invoker,
            source_span     =self._span(getattr(node, "location", None)),
        )

    def _conv_create_table_as(self, node) -> CreateViewStmt:
        """CreateTableAsStmt -> CreateViewStmt(is_materialized=True/False)"""
        objtype_node = getattr(node, "objtype", None)
        objtype_name = objtype_node.name if (objtype_node and hasattr(objtype_node, "name")) else ""
        is_mat = "MATVIEW" in objtype_name

        into = node.into
        name  = self._conv_range_var(into.rel)
        query = self._conv_select(node.query)

        column_names: list[Identifier] = []
        if getattr(into, "colNames", None):
            column_names = [self._ident(s.sval) for s in into.colNames]

        skip_data = bool(getattr(into, "skipData", False))
        with_data = (not skip_data) if is_mat else None

        return self._make(
            CreateViewStmt,
            is_materialized=is_mat,
            if_not_exists  =bool(getattr(node, "if_not_exists", False)),
            name           =name,
            column_names   =column_names,
            query          =query,
            with_data      =with_data,
            source_span    =self._span(getattr(node, "location", None)),
        )

    def _conv_create_index(self, node) -> CreateIndexStmt:
        """IndexStmt -> CreateIndexStmt"""
        name  = self._ident(node.idxname) if node.idxname else None
        table = self._conv_range_var(node.relation)

        columns = [self._conv_index_elem(e) for e in (node.indexParams or [])]

        include: list[Identifier] = []
        for e in (getattr(node, "indexIncludingParams", None) or []):
            if getattr(e, "name", None):
                include.append(self._ident(e.name))

        nulls_nd = getattr(node, "nulls_not_distinct", None)
        nulls_distinct = (not nulls_nd) if nulls_nd is not None else None

        return self._make(
            CreateIndexStmt,
            if_not_exists =bool(getattr(node, "if_not_exists", False)),
            unique        =bool(getattr(node, "unique", False)),
            concurrently  =bool(getattr(node, "concurrent", False)),
            name          =name,
            table         =table,
            using_method  =getattr(node, "accessMethod", None) or None,
            columns       =columns,
            include       =include,
            where         =self._conv_expr(node.whereClause) if node.whereClause else None,
            nulls_distinct=nulls_distinct,
            source_span   =self._span(getattr(node, "location", None)),
        )

    def _conv_create_function(self, node) -> CreateFunctionStmt:
        """CreateFunctionStmt (pglast) -> CreateFunctionStmt (наш)"""
        parts = [s.sval for s in (node.funcname or [])]
        if len(parts) > 1:
            name = self._make(TableRef,
                              schema=self._ident(parts[-2]),
                              name  =self._ident(parts[-1]))
        else:
            name = self._make(TableRef,
                              name=self._ident(parts[0] if parts else ""))

        args = [self._conv_function_param(p) for p in (node.parameters or [])]

        return_type_node = getattr(node, "returnType", None)
        returns = self._conv_typename(return_type_node) if return_type_node else None

        language   = None
        body       = None
        volatility = None

        for opt in (node.options or []):
            dname = getattr(opt, "defname", "") or ""
            val   = getattr(opt, "arg", None)

            if dname == "language":
                language = val.sval if hasattr(val, "sval") else str(val)
            elif dname == "as":
                if isinstance(val, (list, tuple)) and val:
                    body = val[0].sval if hasattr(val[0], "sval") else str(val[0])
                elif hasattr(val, "sval"):
                    body = val.sval
                else:
                    body = str(val) if val is not None else None
            elif dname == "volatility":
                body_s = val.sval if hasattr(val, "sval") else str(val)
                volatility = body_s.upper()

        return self._make(
            CreateFunctionStmt,
            or_replace =bool(getattr(node, "replace", False)),
            name       =name,
            args       =args,
            returns    =returns,
            language   =language,
            body       =body,
            volatility =volatility,
            source_span=self._span(getattr(node, "location", None)),
        )

    def _conv_create_database(self, node) -> CreateDatabaseStmt:
        """CreatedbStmt -> CreateDatabaseStmt"""
        name = self._ident(node.dbname)

        owner = template = encoding = lc_collate = lc_ctype = locale = None

        for opt in (node.options or []):
            dname = getattr(opt, "defname", "") or ""
            sval  = self._defelem_sval(opt)
            if dname == "owner":
                owner = self._ident(sval) if sval else None
            elif dname == "template":
                template = sval
            elif dname == "encoding":
                encoding = sval
            elif dname == "lc_collate":
                lc_collate = sval
            elif dname == "lc_ctype":
                lc_ctype = sval
            elif dname in ("locale", "locale_provider"):
                if dname == "locale":
                    locale = sval

        return self._make(
            CreateDatabaseStmt,
            if_not_exists=bool(getattr(node, "if_not_exists", False)),
            name         =name,
            owner        =owner,
            template     =template,
            encoding     =encoding,
            lc_collate   =lc_collate,
            lc_ctype     =lc_ctype,
            locale       =locale,
            source_span  =self._span(getattr(node, "location", None)),
        )

    def _conv_create_role(self, node) -> Statement:
        """CreateRoleStmt (pglast) -> CreateRoleStmt / CreateUserStmt.

        pglast.CreateRoleStmt.stmt_type:
          ROLESTMT_ROLE=0, ROLESTMT_USER=1, ROLESTMT_GROUP=2
        """
        stmt_type_node = getattr(node, "stmt_type", None)
        stmt_type_val  = 0
        if stmt_type_node is not None:
            stmt_type_val = stmt_type_node.value \
                            if hasattr(stmt_type_node, "value") else int(stmt_type_node)

        role_name    = self._ident(node.role)
        password     = None
        if_not_exists = False
        options_dict: dict = {}

        for opt in (node.options or []):
            dname = getattr(opt, "defname", "") or ""
            val   = getattr(opt, "arg", None)

            if dname == "password":
                password = val.sval if val and hasattr(val, "sval") else None
            elif dname == "isreplication":
                options_dict["replication"] = True
            elif dname == "canlogin":
                ival = self._int_val(val)
                options_dict["login"] = bool(ival) if ival is not None else True
            elif dname in ("superuser", "nosuperuser", "createdb", "nocreatedb",
                           "createrole", "nocreaterole", "login", "nologin",
                           "inherit", "noinherit", "bypassrls", "nobypassrls"):
                options_dict[dname] = True
            elif dname == "validUntil":
                sval = self._defelem_sval(opt)
                if sval:
                    options_dict["valid_until"] = sval

        loc = self._span(getattr(node, "location", None))

        # ROLESTMT_USER
        if stmt_type_val == 1:
            return self._make(
                CreateUserStmt,
                name         =role_name,
                if_not_exists=if_not_exists,
                password     =password,
                options      =options_dict,
                source_span  =loc,
            )
        # ROLESTMT_ROLE (0) или ROLESTMT_GROUP (2)
        return self._make(
            CreateRoleStmt,
            name         =role_name,
            if_not_exists=if_not_exists,
            options      =options_dict,
            source_span  =loc,
        )

    def _conv_grant(self, node) -> GrantStmt:
        """GrantStmt (pglast) -> GrantStmt (привилегии на объекты)"""
        is_grant = bool(getattr(node, "is_grant", True))

        # Привилегии
        privileges: list[str] = []
        for priv in (node.privileges or []):
            pname = getattr(priv, "priv_name", None)
            privileges.append(pname if pname else "ALL")

        # Тип объекта
        objtype_node = getattr(node, "objtype", None)
        obj_type_str = None
        if objtype_node is not None:
            raw = objtype_node.name if hasattr(objtype_node, "name") else str(objtype_node)
            obj_type_str = raw.replace(_OBJECT_TYPE_PREFIX, "").replace("_", " ")

        # Объекты
        objects: list[TableRef] = []
        for obj in (node.objects or []):
            oname = type(obj).__name__
            if oname == "RangeVar":
                objects.append(self._conv_range_var(obj))
            elif oname == "String":
                objects.append(self._make(TableRef, name=self._ident(obj.sval)))
            elif oname == "List":
                # Квалифицированное имя: [schema, name]
                parts = [s.sval for s in obj if hasattr(s, "sval")]
                if parts:
                    schema = self._ident(parts[-2]) if len(parts) > 1 else None
                    objects.append(self._make(TableRef,
                                              schema=schema,
                                              name  =self._ident(parts[-1])))

        grantees: list[Identifier] = self._conv_role_specs(
            getattr(node, "grantees", None) or []
        )

        return self._make(
            GrantStmt,
            is_grant    =is_grant,
            privileges  =privileges,
            object_type =obj_type_str,
            objects     =objects,
            grantees    =grantees,
            with_grant  =bool(getattr(node, "grant_option", False)),
            is_role_grant=False,
            source_span =self._span(getattr(node, "location", None)),
        )

    def _conv_grant_role(self, node) -> GrantStmt:
        """GrantRoleStmt (pglast) -> GrantStmt(is_role_grant=True)"""
        is_grant = bool(getattr(node, "is_grant", True))

        roles: list[Identifier] = []
        for r in (getattr(node, "granted_roles", None) or []):
            pname = getattr(r, "priv_name", None) or getattr(r, "rolename", None)
            if pname:
                roles.append(self._ident(pname))

        grantees: list[Identifier] = self._conv_role_specs(
            getattr(node, "grantee_roles", None) or []
        )

        return self._make(
            GrantStmt,
            is_grant    =is_grant,
            is_role_grant=True,
            roles       =roles,
            grantees    =grantees,
            with_admin  =bool(getattr(node, "admin_opt", False)),
            source_span =self._span(getattr(node, "location", None)),
        )

    def _conv_role_specs(self, role_specs) -> list[Identifier]:
        """Конвертировать список RoleSpec -> list[Identifier]"""
        result: list[Identifier] = []
        for gs in role_specs:
            rolename = getattr(gs, "rolename", None)
            roletype = getattr(gs, "roletype", None)
            if rolename:
                result.append(self._ident(rolename))
            elif roletype is not None:
                rtype_name = roletype.name if hasattr(roletype, "name") else str(roletype)
                if "PUBLIC" in rtype_name:
                    result.append(self._ident("PUBLIC"))
                elif "CURRENT_USER" in rtype_name:
                    result.append(self._ident("CURRENT_USER"))
                elif "SESSION_USER" in rtype_name:
                    result.append(self._ident("SESSION_USER"))
        return result

    def _conv_alter_role(self, node) -> AlterRoleStmt:
        """AlterRoleStmt (pglast) -> AlterRoleStmt"""
        role_node = getattr(node, "role", None)
        role_name: Optional[Identifier] = None
        if role_node:
            rn = getattr(role_node, "rolename", None)
            if rn:
                role_name = self._ident(rn)

        password = None
        settings: list[SettingAssignment] = []

        for opt in (getattr(node, "options", None) or []):
            dname = getattr(opt, "defname", "") or ""
            val   = getattr(opt, "arg", None)
            if dname == "password":
                password = val.sval if val and hasattr(val, "sval") else None
            elif val is not None:
                try:
                    expr = self._conv_expr(val)
                except Exception:
                    sval = self._defelem_sval(opt)
                    expr = self._make(Literal, value=sval, literal_kind="string")
                settings.append(self._make(SettingAssignment, name=dname, value=expr))

        return self._make(
            AlterRoleStmt,
            name       =role_name,
            password   =password,
            settings   =settings,
            source_span=self._span(getattr(node, "location", None)),
        )

    def _conv_copy(self, node) -> CopyStmt:
        """CopyStmt (pglast) -> CopyStmt"""
        is_from   = bool(getattr(node, "is_from", False))
        direction = "FROM" if is_from else "TO"

        table  = self._conv_range_var(node.relation) if node.relation else None
        query  = self._conv_select(node.query)       if node.query    else None
        columns = [self._ident(c.sval) for c in (getattr(node, "attlist", None) or [])
                   if hasattr(c, "sval")]

        filename   = getattr(node, "filename", None)
        is_program = bool(getattr(node, "is_program", False))
        program    = filename if is_program else None
        if is_program:
            filename = None

        stdin  = is_from  and not filename and not is_program
        stdout = not is_from and not filename and not is_program

        # Опции COPY WITH (...)
        fmt = delimiter = encoding = null_str = None
        quote_char = escape_char = on_error = log_verbosity = None
        header: Optional[bool] = None
        header_match = False
        freeze: Optional[bool] = None
        reject_limit: Optional[int] = None
        force_quote: list[Identifier] = []
        force_not_null: list[Identifier] = []
        force_null: list[Identifier] = []
        where: Optional[Expression] = None

        for opt in (node.options or []):
            dname = (getattr(opt, "defname", "") or "").lower()
            val   = getattr(opt, "arg", None)

            sval = None
            if val is not None:
                if hasattr(val, "sval"):
                    sval = val.sval
                elif hasattr(val, "ival"):
                    sval = str(val.ival)

            if dname == "format":
                fmt = sval
            elif dname == "delimiter":
                delimiter = sval
            elif dname == "header":
                if sval and sval.lower() == "match":
                    header_match = True
                elif sval:
                    header = sval.lower() not in ("false", "0", "f", "off", "no")
                else:
                    header = True
            elif dname == "encoding":
                encoding = sval
            elif dname == "null":
                null_str = sval
            elif dname == "quote":
                quote_char = sval
            elif dname == "escape":
                escape_char = sval
            elif dname == "freeze":
                freeze = True
            elif dname == "on_error":
                on_error = sval
            elif dname == "reject_limit":
                reject_limit = self._int_val(val)
            elif dname == "log_verbosity":
                log_verbosity = sval
            elif dname == "force_quote":
                if isinstance(val, (list, tuple)):
                    force_quote = [self._ident(c.sval)
                                   for c in val if hasattr(c, "sval")]
            elif dname == "force_not_null":
                if isinstance(val, (list, tuple)):
                    force_not_null = [self._ident(c.sval)
                                      for c in val if hasattr(c, "sval")]
            elif dname == "force_null":
                if isinstance(val, (list, tuple)):
                    force_null = [self._ident(c.sval)
                                  for c in val if hasattr(c, "sval")]

        where = self._conv_expr(getattr(node, "whereClause", None))

        return self._make(
            CopyStmt,
            direction   =direction,
            table       =table,
            columns     =columns,
            query       =query,
            filename    =filename,
            stdin       =stdin,
            stdout      =stdout,
            program     =program,
            format      =fmt,
            delimiter   =delimiter,
            header      =header,
            encoding    =encoding,
            null_str    =null_str,
            quote_char  =quote_char,
            escape_char =escape_char,
            on_error    =on_error,
            reject_limit=reject_limit,
            where       =where,
            freeze      =freeze,
            header_match=header_match,
            force_quote =force_quote,
            force_not_null=force_not_null,
            force_null  =force_null,
            log_verbosity=log_verbosity,
            source_span =self._span(getattr(node, "location", None)),
        )

    def _conv_merge(self, node) -> MergeStmt:
        """MergeStmt (pglast) -> MergeStmt (заглушка)"""
        return self._make(MergeStmt,
                          source_span=self._span(getattr(node, "location", None)))

    # Конвертеры операторов — TCL и прочие

    def _conv_transaction(self, node) -> Statement:
        kind_name = node.kind.name
        loc = self._span(getattr(node, "location", None))

        if kind_name in ("TRANS_STMT_BEGIN", "TRANS_STMT_START"):
            return self._make(BeginStmt, source_span=loc)
        if kind_name in ("TRANS_STMT_COMMIT", "TRANS_STMT_END"):
            return self._make(CommitStmt, source_span=loc)
        if kind_name == "TRANS_STMT_ROLLBACK":
            return self._make(RollbackStmt, source_span=loc)

        # SAVEPOINT / RELEASE / ROLLBACK TO
        if kind_name == "TRANS_STMT_SAVEPOINT":
            sp = getattr(node, "savepoint_name", "") or ""
            return self._make(SavepointStmt, action="savepoint", name=sp,
                              source_span=loc)
        if kind_name == "TRANS_STMT_RELEASE":
            sp = getattr(node, "savepoint_name", "") or ""
            return self._make(SavepointStmt, action="release", name=sp,
                              source_span=loc)
        if kind_name == "TRANS_STMT_ROLLBACK_TO":
            sp = getattr(node, "savepoint_name", "") or ""
            return self._make(SavepointStmt, action="rollback_to", name=sp,
                              source_span=loc)

        # PREPARE TRANSACTION / COMMIT PREPARED / ROLLBACK PREPARED
        if kind_name == "TRANS_STMT_PREPARE":
            return self._make(PrepareTransactionStmt,
                              action="prepare",
                              prepared_id=getattr(node, "gid", None),
                              source_span=loc)
        if kind_name == "TRANS_STMT_COMMIT_PREPARED":
            return self._make(PrepareTransactionStmt,
                              action="commit",
                              prepared_id=getattr(node, "gid", None),
                              source_span=loc)
        if kind_name == "TRANS_STMT_ROLLBACK_PREPARED":
            return self._make(PrepareTransactionStmt,
                              action="rollback",
                              prepared_id=getattr(node, "gid", None),
                              source_span=loc)

        return self._make(RawStatement,
                          text=f"-- TRANSACTION {kind_name}",
                          origin_dialect=Dialect.POSTGRES)

    def _conv_variable_set(self, node) -> Statement:
        """VariableSetStmt -> SetTransactionStmt или RawStatement"""
        var_name  = getattr(node, "name", "") or ""
        kind_node = getattr(node, "kind", None)
        kind_val  = kind_node.value if hasattr(kind_node, "value") else (kind_node or 0)

        if kind_val == 3:
            isolation = None
            read_only = None
            deferrable = None
            is_local = bool(getattr(node, "is_local", False))
            if "SESSION" in var_name.upper():
                scope = "session"
            elif is_local:
                scope = "local"
            else:
                scope = "transaction"

            for opt in (getattr(node, "args", None) or []):
                dname = (getattr(opt, "defname", "") or "").lower()
                val   = getattr(opt, "arg", None)
                if dname == "transaction_isolation":
                    inner = getattr(val, "val", None) if val else None
                    s = (inner.sval if inner and hasattr(inner, "sval") else "") or ""
                    isolation = s.upper()
                elif dname == "transaction_read_only":
                    inner = getattr(val, "val", None) if val else None
                    ival  = inner.ival if inner and hasattr(inner, "ival") else None
                    read_only = bool(ival) if ival is not None else None
                elif dname == "transaction_deferrable":
                    inner = getattr(val, "val", None) if val else None
                    ival  = inner.ival if inner and hasattr(inner, "ival") else None
                    deferrable = bool(ival) if ival is not None else None

            return self._make(
                SetTransactionStmt,
                isolation_level=isolation,
                read_only      =read_only,
                deferrable     =deferrable,
                scope          =scope,
                source_span    =self._span(getattr(node, "location", None)),
            )

        return self._make(
            RawStatement,
            text          =f"-- SET {var_name}",
            origin_dialect=Dialect.POSTGRES,
        )

    def _conv_lock_table(self, node) -> LockTableStmt:
        """LockStmt -> LockTableStmt"""
        mode_node = getattr(node, "mode", None)
        mode_val  = mode_node.value if hasattr(mode_node, "value") else (mode_node or 8)
        mode = _LOCK_TABLE_MODE.get(mode_val, "ACCESS EXCLUSIVE")
        return self._make(LockTableStmt, mode=mode,
                          source_span=self._span(getattr(node, "location", None)))

    def _conv_set_constraints(self, node) -> SetConstraintsStmt:
        """ConstraintsSetStmt -> SetConstraintsStmt"""
        deferred = bool(getattr(node, "deferred", False))
        return self._make(SetConstraintsStmt,
                          mode="DEFERRED" if deferred else "IMMEDIATE",
                          source_span=self._span(getattr(node, "location", None)))
