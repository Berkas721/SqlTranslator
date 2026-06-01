
from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, Union

from .metadata import Dialect
from .node import Node

@dataclass(slots=True)
class Statement(Node):
    """Базовый класс для всех SQL-операторов."""


@dataclass(slots=True)
class Expression(Node):
    """Базовый класс для всех SQL-выражений."""


@dataclass(slots=True)
class FromItem(Node):
    """Базовый класс для элементов FROM-клаузы."""


@dataclass(slots=True)
class Identifier(Expression):
    name:   str  = ""
    quoted: bool = False


@dataclass(slots=True)
class Literal(Expression):
    value:         object                   = None
    literal_kind:  str                      = ""
    # 'int' | 'float' | 'string' | 'bool' | 'null' | 'date' | 'timestamp' |
    # 'interval' | 'bit' | 'hex' | 'uuid'
    raw:           Optional[str]            = None
    explicit_type: Optional[TypeRef]        = None
    quote_style:   Optional[str]            = None
    # 'single' | 'E' | 'dollar' | 'U&'


@dataclass(slots=True)
class ColumnRef(Expression):
    database: Optional[Identifier] = None
    schema:   Optional[Identifier] = None
    table:    Optional[Identifier] = None
    column:   Optional[Identifier] = None


@dataclass(slots=True)
class StarExpr(Expression):
    table: Optional[Identifier] = None


@dataclass(slots=True)
class TypeRef(Node):
    """Ссылка на тип данных (не является Expression)."""
    name:       str                  = ""
    schema:     Optional[str]        = None
    params:     list[Expression]     = field(default_factory=list)
    array_dims: int                  = 0
    time_zone:  Optional[str]        = None
    modifiers:  list[str]            = field(default_factory=list)


@dataclass(slots=True)
class BinaryOp(Expression):
    op:    str              = ""
    left:  Expression       = None
    right: Expression       = None


@dataclass(slots=True)
class UnaryOp(Expression):
    op:       str        = ""
    position: str        = "prefix"   # 'prefix' | 'postfix'
    operand:  Expression = None


@dataclass(slots=True)
class FunctionCall(Expression):
    name:         Identifier            = None
    args:         list[Expression]      = field(default_factory=list)
    parameters:   list[Expression]      = field(default_factory=list)
    # CH: параметрические агрегаты — quantile(0.5)(x), topK(1)(x)
    distinct:     bool                  = False
    star:         bool                  = False
    variadic:     bool                  = False
    order_by:     list[OrderByItem]     = field(default_factory=list)
    within_group: list[OrderByItem]     = field(default_factory=list)
    filter_where: Optional[Expression]  = None
    over:         Optional[WindowSpec]  = None


@dataclass(slots=True)
class Cast(Expression):
    expression:  Expression = None
    target_type: TypeRef    = None
    style:       str        = "cast"
    # 'cast' | 'postfix' | 'typed_fn' | 'typed_literal'


@dataclass(slots=True)
class CaseExpr(Expression):
    arg:       Optional[Expression]  = None
    branches:  list[WhenBranch]      = field(default_factory=list)
    else_expr: Optional[Expression]  = None


@dataclass(slots=True)
class WhenBranch(Node):
    condition: Expression = None
    result:    Expression = None


@dataclass(slots=True)
class ArrayConstructor(Expression):
    elements: list[Expression] = field(default_factory=list)
    syntax:   str              = "array_kw"
    # 'bracket' | 'array_kw' | 'curly_literal'


@dataclass(slots=True)
class TupleConstructor(Expression):
    elements: list[Expression] = field(default_factory=list)
    names:    list[Identifier] = field(default_factory=list)
    syntax:   str              = "parens"
    # 'row_kw' | 'parens'


@dataclass(slots=True)
class SubqueryExpr(Expression):
    query:    SelectStmt        = None
    kind:     str               = "scalar"
    # 'scalar' | 'exists' | 'not_exists' | 'in' | 'not_in' | 'any' | 'all'
    outer_op: Optional[str]     = None


@dataclass(slots=True)
class ParamRef(Expression):
    number: Optional[int] = None
    name:   Optional[str] = None


@dataclass(slots=True)
class BetweenExpr(Expression):
    """expr [NOT] BETWEEN [SYMMETRIC] low AND high."""
    expr:      Expression = None
    low:       Expression = None
    high:      Expression = None
    negated:   bool = False    # NOT BETWEEN
    symmetric: bool = False    # BETWEEN SYMMETRIC


@dataclass(slots=True)
class LikeExpr(Expression):
    """expr [NOT] LIKE/ILIKE pattern [ESCAPE escape]."""
    string:           Expression          = None
    pattern:          Expression          = None
    escape:           Optional[Expression] = None
    negated:          bool                = False
    case_insensitive: bool                = False   # ILIKE


@dataclass(slots=True)
class SimilarToExpr(Expression):
    """expr [NOT] SIMILAR TO pattern [ESCAPE escape]."""
    string:  Expression          = None
    pattern: Expression          = None
    escape:  Optional[Expression] = None
    negated: bool                = False


@dataclass(slots=True)
class WithFillSpec(Node):
    """CH: WITH FILL в ORDER BY."""
    from_value: Optional[Expression] = None   # FROM value
    to_value:   Optional[Expression] = None   # TO value
    step:       Optional[Expression] = None   # STEP value


@dataclass(slots=True)
class OrderByItem(Node):
    expression: Expression              = None
    direction:  Optional[str]           = None   # 'ASC' | 'DESC'
    nulls:      Optional[str]           = None   # 'FIRST' | 'LAST'
    collate:    Optional[str]           = None
    with_fill:  Optional[WithFillSpec]  = None   # CH
    using_op:   Optional[str]           = None   # PG: ORDER BY expr USING operator


@dataclass(slots=True)
class FrameBound(Node):
    kind:   str                = ""
    # 'UNBOUNDED_PRECEDING' | 'UNBOUNDED_FOLLOWING' | 'CURRENT_ROW' |
    # 'N_PRECEDING' | 'N_FOLLOWING'
    offset: Optional[Expression] = None


@dataclass(slots=True)
class FrameSpec(Node):
    unit:    str                    = "ROWS"   # 'ROWS' | 'RANGE' | 'GROUPS'
    start:   FrameBound             = None
    end:     Optional[FrameBound]   = None
    exclude: Optional[str]          = None
    # 'CURRENT_ROW' | 'GROUP' | 'TIES' | 'NO_OTHERS'


@dataclass(slots=True)
class WindowSpec(Node):
    existing_name: Optional[Identifier]  = None
    partition_by:  list[Expression]      = field(default_factory=list)
    order_by:      list[OrderByItem]     = field(default_factory=list)
    frame:         Optional[FrameSpec]   = None


@dataclass(slots=True)
class WindowDef(Node):
    name: Identifier  = None
    spec: WindowSpec  = None


@dataclass(slots=True)
class DistinctClause(Node):
    kind: str              = "distinct"   # 'all' | 'distinct' | 'distinct_on'
    on:   list[Expression] = field(default_factory=list)


@dataclass(slots=True)
class WithClause(Node):
    recursive: bool                  = False
    ctes:      list[CommonTableExpr] = field(default_factory=list)


@dataclass(slots=True)
class CommonTableExpr(Node):
    name:         Identifier        = None
    columns:      list[Identifier]  = field(default_factory=list)
    query:        SelectStmt        = None
    materialized: Optional[bool]    = None


@dataclass(slots=True)
class GroupByClause(Node):
    kind:  str              = "ordinary"
    # 'ordinary' | 'rollup' | 'cube' | 'grouping_sets' | 'all' | 'distinct'
    items: list[Expression] = field(default_factory=list)


@dataclass(slots=True)
class SetOpClause(Node):
    op:         str         = ""          # 'UNION' | 'INTERSECT' | 'EXCEPT'
    quantifier: Optional[str] = None      # 'ALL' | 'DISTINCT'
    right:      SelectStmt  = None


@dataclass(slots=True)
class FetchClause(Node):
    first:     bool                 = True   # FIRST | NEXT
    count:     Optional[Expression] = None
    with_ties: bool                 = False


@dataclass(slots=True)
class LockingClause(Node):
    mode:   str              = ""
    # 'UPDATE' | 'NO_KEY_UPDATE' | 'SHARE' | 'KEY_SHARE'
    tables: list[TableRef]   = field(default_factory=list)
    wait:   Optional[str]    = None   # 'NOWAIT' | 'SKIP_LOCKED'


@dataclass(slots=True)
class SampleClause(Node):
    """CH: SAMPLE ratio [OFFSET offset]."""
    ratio:  Expression          = None
    offset: Optional[Expression] = None


@dataclass(slots=True)
class TableRef(FromItem):
    database:               Optional[Identifier]   = None
    schema:                 Optional[Identifier]   = None
    name:                   Identifier             = None
    alias:                  Optional[Identifier]   = None
    column_aliases:         list[Identifier]       = field(default_factory=list)
    only:                   bool                   = False
    descendants_star:       bool                   = False
    # PG: TABLESAMPLE method (arg [, ...]) [REPEATABLE (seed)]
    tablesample_method:     Optional[str]          = None
    tablesample_args:       list[Expression]       = field(default_factory=list)
    tablesample_repeatable: Optional[Expression]   = None
    # CH: SAMPLE ratio (заполняется B-правилом из tablesample)
    ch_sample:              Optional[SampleClause] = None


@dataclass(slots=True)
class JoinExpr(FromItem):
    kind:   str              = "inner"
    # 'inner' | 'left' | 'right' | 'full' | 'cross' | 'natural_inner' |
    # 'semi' | 'anti' | 'asof'
    left:   FromItem         = None
    right:  FromItem         = None
    on:     Optional[Expression] = None
    using:  list[Identifier]     = field(default_factory=list)
    lateral: bool                = False


@dataclass(slots=True)
class SubqueryRef(FromItem):
    query:          SelectStmt       = None
    alias:          Optional[Identifier] = None
    column_aliases: list[Identifier]     = field(default_factory=list)
    lateral:        bool                 = False


@dataclass(slots=True)
class TableFunctionRef(FromItem):
    call:            FunctionCall        = None
    alias:           Optional[Identifier] = None
    column_aliases:  list[Identifier]    = field(default_factory=list)
    with_ordinality: bool                = False
    lateral:         bool                = False


@dataclass(slots=True)
class SettingAssignment(Node):
    name:  str        = ""
    value: Expression = None


@dataclass(slots=True)
class ColumnConstraint(Node):
    kind:             str                    = ""
    # 'not_null' | 'null' | 'default' | 'check' | 'primary_key' | 'unique' |
    # 'references' | 'generated_identity' | 'generated_stored' | 'generated_virtual'
    name:             Optional[str]          = None
    expression:       Optional[Expression]   = None
    ref_table:        Optional[TableRef]     = None
    ref_columns:      list[Identifier]       = field(default_factory=list)
    on_delete:        Optional[str]          = None
    on_update:        Optional[str]          = None
    match:            Optional[str]          = None
    deferrable:       Optional[bool]         = None
    initially:        Optional[str]          = None
    nulls_distinct:   Optional[bool]         = None
    identity_mode:    Optional[str]          = None   # 'ALWAYS' | 'BY_DEFAULT'
    identity_options: list[SettingAssignment] = field(default_factory=list)


@dataclass(slots=True)
class ColumnDef(Node):
    name:        Identifier              = None
    type:        TypeRef                 = None
    constraints: list[ColumnConstraint] = field(default_factory=list)
    collation:   Optional[str]           = None
    comment:     Optional[str]           = None
    storage:     Optional[str]           = None   # PG: PLAIN/EXTERNAL/EXTENDED/MAIN
    compression: Optional[str]           = None   # PG: pglz/lz4
    codec:       list[FunctionCall]      = field(default_factory=list)   # CH
    ttl:         Optional[Expression]    = None   # CH


@dataclass(slots=True)
class ExcludeElement(Node):
    """PG: элемент EXCLUDE-ограничения."""
    expression: Expression = None
    operator:   str        = ""


@dataclass(slots=True)
class TableConstraint(Node):
    kind:             str                    = ""
    name:             Optional[str]          = None
    columns:          list[Identifier]       = field(default_factory=list)
    expression:       Optional[Expression]   = None
    ref_table:        Optional[TableRef]     = None
    ref_columns:      list[Identifier]       = field(default_factory=list)
    on_delete:        Optional[str]          = None
    on_update:        Optional[str]          = None
    match:            Optional[str]          = None
    deferrable:       Optional[bool]         = None
    initially:        Optional[str]          = None
    nulls_distinct:   Optional[bool]         = None
    include_columns:  list[Identifier]       = field(default_factory=list)
    exclude_elements: list[ExcludeElement]   = field(default_factory=list)


@dataclass(slots=True)
class LikeClause(Node):
    source:    TableRef   = None
    including: list[str]  = field(default_factory=list)
    excluding: list[str]  = field(default_factory=list)


@dataclass(slots=True)
class OnConflictClause(Node):
    """PG: ON CONFLICT ... DO ..."""
    target:  Optional[Expression]      = None   # conflict_target (столбец/ограничение)
    action:  str                       = "nothing"   # 'nothing' | 'update'
    updates: list[SettingAssignment]   = field(default_factory=list)
    where:   Optional[Expression]      = None


@dataclass(slots=True)
class EngineSpec(Node):
    name: str             = ""   # 'MergeTree' | 'ReplicatedMergeTree' | ...
    args: list[Expression] = field(default_factory=list)


@dataclass(slots=True)
class TtlRule(Node):
    expression:       Expression         = None
    action:           str                = "DELETE"
    # 'DELETE' | 'RECOMPRESS' | 'TO_VOLUME' | 'TO_DISK' | 'GROUP_BY'
    target:           Optional[str]      = None
    recompress_codec: list[FunctionCall] = field(default_factory=list)


@dataclass(slots=True)
class TtlClause(Node):
    rules: list[TtlRule] = field(default_factory=list)


@dataclass(slots=True)
class SelectTarget(Node):
    expression: Expression       = None
    alias:      Optional[Identifier] = None


# Псевдоним для источника данных INSERT
InsertSource = Union["ValuesClause", "SelectStmt", "DefaultValues"]


@dataclass(slots=True)
class ValuesClause(Node):
    rows: list[list[Expression]] = field(default_factory=list)


@dataclass(slots=True)
class DefaultValues(Node):
    pass


@dataclass(slots=True)
class RawStatement(Statement):
    """Резервный узел для непереводимых конструкций."""
    text:           str     = ""
    origin_dialect: Dialect = Dialect.POSTGRES


@dataclass(slots=True)
class SelectStmt(Statement):
    with_clause:  Optional[WithClause]      = None
    distinct:     Optional[DistinctClause]  = None
    targets:      list[SelectTarget]        = field(default_factory=list)
    from_items:   list[FromItem]            = field(default_factory=list)
    where:        Optional[Expression]      = None
    group_by:     Optional[GroupByClause]   = None
    having:       Optional[Expression]      = None
    windows:      list[WindowDef]           = field(default_factory=list)
    set_op:       Optional[SetOpClause]     = None
    order_by:     list[OrderByItem]         = field(default_factory=list)
    limit:        Optional[Expression]      = None
    offset:       Optional[Expression]      = None
    fetch:        Optional[FetchClause]     = None
    locking:      list[LockingClause]       = field(default_factory=list)
    # CH-специфика:
    sample:          Optional[SampleClause]   = None
    settings:        list[SettingAssignment]  = field(default_factory=list)
    limit_with_ties: bool                     = False   # LIMIT n WITH TIES


@dataclass(slots=True)
class InsertStmt(Statement):
    with_clause:    Optional[WithClause]        = None
    target:         TableRef                    = None
    alias:          Optional[Identifier]        = None
    columns:        list[Identifier]            = field(default_factory=list)
    overriding:     Optional[str]               = None   # 'SYSTEM' | 'USER'
    source:         Optional[InsertSource]      = None
    on_conflict:    Optional[OnConflictClause]  = None
    returning:      list[SelectTarget]          = field(default_factory=list)
    ch_format:      Optional[str]               = None
    ch_from_infile: Optional[str]               = None


@dataclass(slots=True)
class CreateTableStmt(Statement):
    if_not_exists:     bool                     = False
    temporary:         bool                     = False
    table:             TableRef                 = None
    columns:           list[ColumnDef]          = field(default_factory=list)
    table_constraints: list[TableConstraint]    = field(default_factory=list)
    like_clause:       Optional[LikeClause]     = None
    # CH-специфика:
    engine:            Optional[EngineSpec]     = None
    order_by_key:      list[Expression]         = field(default_factory=list)
    primary_key:       list[Expression]         = field(default_factory=list)
    partition_by:      Optional[Expression]     = None
    sample_by:         Optional[Expression]     = None
    ttl:               Optional[TtlClause]      = None
    settings:          list[SettingAssignment]  = field(default_factory=list)
    # PG-специфика:
    inherits:          list[TableRef]           = field(default_factory=list)
    tablespace:        Optional[str]            = None
    on_commit:         Optional[str]            = None
    using_method:      Optional[str]            = None
    unlogged:          bool                     = False

@dataclass(slots=True)
class IndexColumn(Node):
    """Столбец / выражение в определении индекса (CREATE INDEX ... ON t (here))."""
    expression: Expression    = None
    opclass:    Optional[str] = None
    direction:  Optional[str] = None   # 'ASC' | 'DESC'
    nulls:      Optional[str] = None   # 'FIRST' | 'LAST'
    collate:    Optional[str] = None


@dataclass(slots=True)
class FunctionArg(Node):
    """Аргумент объявления функции / процедуры."""
    name:    Optional[Identifier] = None
    type:    Optional[TypeRef]    = None
    mode:    str                  = "IN"   # 'IN' | 'OUT' | 'INOUT' | 'VARIADIC'
    default: Optional[Expression] = None


@dataclass(slots=True)
class CreateViewStmt(Statement):
    """CREATE [MATERIALIZED] VIEW."""
    is_materialized:  bool                 = False
    or_replace:       bool                 = False
    if_not_exists:    bool                 = False
    temporary:        bool                 = False
    recursive:        bool                 = False
    name:             Optional[TableRef]   = None
    # PG: CREATE VIEW name (col1, col2, ...) AS SELECT ...
    column_names:     list[Identifier]     = field(default_factory=list)
    query:            Optional[SelectStmt] = None
    # PG: WITH [LOCAL | CASCADED] CHECK OPTION
    check_option:     Optional[str]        = None
    # PG: WITH (security_barrier=..., security_invoker=...)
    security_barrier: bool                 = False
    security_invoker: bool                 = False
    # PG MATERIALIZED VIEW: WITH [NO] DATA
    with_data:        Optional[bool]       = None   # True=WITH DATA, False=WITH NO DATA
    # CH MATERIALIZED VIEW: TO target_table, POPULATE
    to_table:         Optional[TableRef]   = None
    populate:         bool                 = False


@dataclass(slots=True)
class CreateIndexStmt(Statement):
    """CREATE [UNIQUE] INDEX."""
    if_not_exists: bool                 = False
    unique:        bool                 = False
    concurrently:  bool                 = False
    name:          Optional[Identifier] = None
    table:         Optional[TableRef]   = None
    using_method:  Optional[str]        = None   # 'btree'|'hash'|'gist'|'spgist'|'gin'|'brin'|'bloom'
    columns:       list[IndexColumn]    = field(default_factory=list)
    include:       list[Identifier]     = field(default_factory=list)   # INCLUDE (col [...])
    where:         Optional[Expression] = None                          # WHERE predicate
    nulls_distinct: Optional[bool]      = None
    # CH data-skipping index specific:
    index_type:    Optional[str]        = None   # 'minmax'|'set'|'ngrambf_v1'|...
    granularity:   Optional[int]        = None


@dataclass(slots=True)
class CreateFunctionStmt(Statement):
    """CREATE [OR REPLACE] FUNCTION."""
    or_replace:     bool                 = False
    name:           Optional[TableRef]   = None   # qualified name (schema.func_name)
    args:           list[FunctionArg]    = field(default_factory=list)
    returns:        Optional[TypeRef]    = None
    language:       Optional[str]        = None   # 'sql' | 'plpgsql' | 'c' | ...
    body:           Optional[str]        = None   # raw body text ($$ ... $$)
    volatility:     Optional[str]        = None   # 'VOLATILE' | 'STABLE' | 'IMMUTABLE'
    # CH lambda form (AS (args) -> expr):
    ch_lambda_body: Optional[Expression] = None


@dataclass(slots=True)
class CreateDatabaseStmt(Statement):
    """CREATE DATABASE."""
    if_not_exists: bool                 = False
    name:          Optional[Identifier] = None
    owner:         Optional[Identifier] = None   # PG: OWNER
    template:      Optional[str]        = None   # PG: TEMPLATE
    encoding:      Optional[str]        = None   # PG: ENCODING
    lc_collate:    Optional[str]        = None   # PG: LC_COLLATE
    lc_ctype:      Optional[str]        = None   # PG: LC_CTYPE
    locale:        Optional[str]        = None   # PG: LOCALE
    # CH specific:
    engine:        Optional[str]        = None   # 'Atomic' | 'Replicated' | ...


@dataclass(slots=True)
class CreateUserStmt(Statement):
    """CREATE USER / CREATE ROLE WITH LOGIN."""
    name:          Optional[Identifier] = None
    if_not_exists: bool                 = False
    password:      Optional[str]        = None   # PG: WITH PASSWORD 'pwd'
    auth_method:   Optional[str]        = None   # PG: MD5/SCRAM; CH: sha256_password/...
    # Дополнительные опции (PG) — хранятся как пары ключ-значение
    options:       dict                 = field(default_factory=dict)


@dataclass(slots=True)
class GrantStmt(Statement):
    """GRANT/REVOKE privilege ON object TO/FROM grantee / GRANT role TO user."""
    is_grant:      bool                = True    # True=GRANT, False=REVOKE
    # Выдача/отзыв привилегий:
    privileges:    list[str]           = field(default_factory=list)
    object_type:   Optional[str]       = None    # 'TABLE' | 'DATABASE' | 'SEQUENCE' | ...
    objects:       list[TableRef]      = field(default_factory=list)
    grantees:      list[Identifier]    = field(default_factory=list)
    with_grant:    bool                = False   # WITH GRANT OPTION
    # Выдача/отзыв ролей (GRANT role TO user):
    is_role_grant: bool                = False
    roles:         list[Identifier]    = field(default_factory=list)
    with_admin:    bool                = False   # WITH ADMIN OPTION


@dataclass(slots=True)
class AlterRoleStmt(Statement):
    """ALTER ROLE / ALTER USER SET configuration_parameter."""
    name:        Optional[Identifier]      = None
    password:    Optional[str]             = None   # ALTER USER name PASSWORD 'pwd'
    auth_method: Optional[str]             = None   # CH: IDENTIFIED WITH method
    settings:    list[SettingAssignment]   = field(default_factory=list)


# Оставляем CreateRoleStmt как алиас для CREATE ROLE (без LOGIN):
@dataclass(slots=True)
class CreateRoleStmt(Statement):
    """CREATE ROLE (без опции LOGIN — не является полноценным пользователем)."""
    name:          Optional[Identifier] = None
    if_not_exists: bool                 = False
    options:       dict                 = field(default_factory=dict)


@dataclass(slots=True)
class MergeStmt(Statement):
    pass


@dataclass(slots=True)
class CopyStmt(Statement):
    """COPY table FROM/TO ... (PostgreSQL bulk-load/export)."""
    direction:      str                    = "FROM"   # 'FROM' | 'TO'
    table:          Optional[TableRef]     = None
    columns:        list[Identifier]       = field(default_factory=list)
    query:          Optional[SelectStmt]   = None    # COPY (query) TO ...
    filename:       Optional[str]          = None
    stdin:          bool                   = False   # FROM STDIN
    stdout:         bool                   = False   # TO STDOUT
    program:        Optional[str]          = None    # FROM/TO PROGRAM 'cmd'
    # Опции COPY WITH (...):
    format:         Optional[str]          = None    # FORMAT name
    delimiter:      Optional[str]          = None    # DELIMITER 'char'
    header:         Optional[bool]         = None    # HEADER [bool]
    encoding:       Optional[str]          = None    # ENCODING 'name'
    null_str:       Optional[str]          = None    # NULL 'string'
    quote_char:     Optional[str]          = None    # QUOTE 'char'
    escape_char:    Optional[str]          = None    # ESCAPE 'char'
    on_error:       Optional[str]          = None    # ON_ERROR stop|ignore
    reject_limit:   Optional[int]          = None    # REJECT_LIMIT n
    # PG-специфика (тип E):
    where:          Optional[Expression]   = None
    freeze:         Optional[bool]         = None
    header_match:   bool                   = False
    force_quote:    list[Identifier]       = field(default_factory=list)
    force_not_null: list[Identifier]       = field(default_factory=list)
    force_null:     list[Identifier]       = field(default_factory=list)
    log_verbosity:  Optional[str]          = None
    # CH-эквиваленты (заполняются rewrite-функциями правил):
    ch_from_infile:  Optional[str]         = None   # INSERT ... FROM INFILE 'path'
    ch_into_outfile: Optional[str]         = None   # SELECT ... INTO OUTFILE 'path'
    ch_format:       Optional[str]         = None   # FORMAT name


@dataclass(slots=True)
class BeginStmt(Statement):
    style: str = "begin"
    # 'begin' | 'start_transaction'


@dataclass(slots=True)
class CommitStmt(Statement):
    style: str = "commit"
    # 'commit' | 'end'


@dataclass(slots=True)
class RollbackStmt(Statement):
    style: str = "rollback"
    # 'rollback' | 'abort'


@dataclass(slots=True)
class SavepointStmt(Statement):
    action: str = "savepoint"
    # 'savepoint' | 'release' | 'rollback_to'
    name:   str = ""


@dataclass(slots=True)
class SetTransactionStmt(Statement):
    isolation_level: Optional[str]  = None
    # 'READ UNCOMMITTED' | 'READ COMMITTED' | 'REPEATABLE READ' | 'SERIALIZABLE'
    read_only:       Optional[bool] = None
    deferrable:      Optional[bool] = None
    scope:           str            = "transaction"
    # 'transaction' | 'session' | 'local'


@dataclass(slots=True)
class SetConstraintsStmt(Statement):
    mode: str = "DEFERRED"
    # 'DEFERRED' | 'IMMEDIATE'


@dataclass(slots=True)
class LockTableStmt(Statement):
    mode: Optional[str] = None
    # 'ACCESS SHARE' | 'ROW SHARE' | ... | 'ACCESS EXCLUSIVE'


@dataclass(slots=True)
class PrepareTransactionStmt(Statement):
    prepared_id: Optional[str] = None
    action:      str           = "prepare"
    # 'prepare' | 'commit' | 'rollback'


@dataclass(slots=True)
class Script(Node):
    """Весь SQL-скрипт — одна или несколько statement-конструкций."""
    statements:     list[Statement] = field(default_factory=list)
    dialect_target: Dialect         = Dialect.COMMON
    source_text:    Optional[str]   = None
