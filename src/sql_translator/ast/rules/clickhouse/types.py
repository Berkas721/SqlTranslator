"""Правила преобразования TypeRef: PostgreSQL → ClickHouse.
"""
from __future__ import annotations

from src.ast.metadata import Dialect, Kind
from src.ast.nodes import Literal, TypeRef
from src.ast.registry import Rule, TranslateContext, default_translator


def _int_param(value: int) -> Literal:
    """Создать целочисленный Literal-узел для параметра типа (например, DateTime64(6))."""
    lit = Literal(value=value, literal_kind="int", raw=str(value))
    lit.node_kind = "Literal"
    lit.dialect = Dialect.CLICKHOUSE
    return lit


def _when_uuid(n: TypeRef) -> bool:
    return n.name.upper() == "UUID"

_RULE_UUID = Rule(
    rule_id="pg_ch_type_uuid",
    title="uuid → UUID (тип A: полное соответствие)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="TypeRef",
    kind=Kind.A,
    when=_when_uuid,
    rewrite=None,
    message=None,
)


def _rewrite_name(new_name: str):
    """Фабрика rewrite-функций, которые просто меняют TypeRef.name."""
    def _inner(n: TypeRef, ctx: TranslateContext) -> TypeRef:
        n.name = new_name
        n.schema = None
        return n
    return _inner


_RULE_REAL = Rule(
    rule_id="pg_ch_type_real",
    title="real / float4 → Float32 (тип B)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="TypeRef",
    kind=Kind.B,
    when=lambda n: n.name.upper() == "REAL",
    rewrite=_rewrite_name("Float32"),
    message=None,
)

_RULE_DOUBLE = Rule(
    rule_id="pg_ch_type_double",
    title="double precision / float8 → Float64 (тип B)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="TypeRef",
    kind=Kind.B,
    when=lambda n: n.name.upper() == "DOUBLE PRECISION",
    rewrite=_rewrite_name("Float64"),
    message=None,
)

_RULE_TIME = Rule(
    rule_id="pg_ch_type_time",
    title="time / time without time zone → Time (тип B)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="TypeRef",
    kind=Kind.B,
    when=lambda n: n.name.upper() == "TIME" and not n.time_zone,
    rewrite=_rewrite_name("Time"),
    message=None,
)


_RULE_SMALLINT = Rule(
    rule_id="pg_ch_type_smallint",
    title="smallint / int2 → Int16 (тип C)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="TypeRef",
    kind=Kind.C,
    when=lambda n: n.name.upper() == "SMALLINT",
    rewrite=_rewrite_name("Int16"),
    message=(
        "Диапазон совпадает; при переполнении PGSQL возбуждает ошибку, "
        "CH выполняет молчаливый wraparound по модулю."
    ),
)

_RULE_INTEGER = Rule(
    rule_id="pg_ch_type_integer",
    title="integer / int4 → Int32 (тип C)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="TypeRef",
    kind=Kind.C,
    when=lambda n: n.name.upper() == "INTEGER",
    rewrite=_rewrite_name("Int32"),
    message=(
        "То же, что и smallint: wraparound вместо ошибки в CH."
    ),
)

_RULE_BIGINT = Rule(
    rule_id="pg_ch_type_bigint",
    title="bigint / int8 → Int64 (тип C)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="TypeRef",
    kind=Kind.C,
    when=lambda n: n.name.upper() == "BIGINT",
    rewrite=_rewrite_name("Int64"),
    message=(
        "То же, что и smallint: wraparound вместо ошибки в CH."
    ),
)

_RULE_TEXT = Rule(
    rule_id="pg_ch_type_text",
    title="text → String (тип C)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="TypeRef",
    kind=Kind.C,
    when=lambda n: n.name.upper() == "TEXT",
    rewrite=_rewrite_name("String"),
    message=(
        "String хранит произвольные байты без валидации UTF-8; "
        "PGSQL text валидирует кодировку при вставке. "
        "Для корректного UTF-8 расхождение несущественно."
    ),
)


def _rewrite_varchar(n: TypeRef, ctx: TranslateContext) -> TypeRef:
    """character varying(n) / varchar(n) → String (параметр длины теряется)."""
    n.name = "String"
    n.schema = None
    n.params = []   # CH String не имеет ограничения длины
    return n


_RULE_VARCHAR = Rule(
    rule_id="pg_ch_type_varchar",
    title="character varying / varchar → String (тип C)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="TypeRef",
    kind=Kind.C,
    when=lambda n: n.name.upper() == "VARCHAR",
    rewrite=_rewrite_varchar,
    message=(
        "PGSQL ограничивает максимальную длину и выдаёт ошибку при превышении; "
        "CH String ограничений на длину не имеет — семантика ограничения теряется."
    ),
)

_RULE_BOOLEAN = Rule(
    rule_id="pg_ch_type_boolean",
    title="boolean → Bool (тип C)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="TypeRef",
    kind=Kind.C,
    when=lambda n: n.name.upper() == "BOOLEAN",
    rewrite=_rewrite_name("Bool"),
    message=(
        "В PGSQL boolean — трёхзначный (TRUE/FALSE/NULL); "
        "в CH Bool соответствует UInt8 и NULL требует обёртки Nullable(Bool)."
    ),
)

_RULE_JSON = Rule(
    rule_id="pg_ch_type_json",
    title="json → String (тип C)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="TypeRef",
    kind=Kind.C,
    when=lambda n: n.name.upper() == "JSON",
    rewrite=_rewrite_name("String"),
    message=(
        "PGSQL json хранит текст как есть; CH JSON-тип появился в 24.x как "
        "экспериментальный. Для совместимости чаще используется String + "
        "функции JSONExtract*."
    ),
)


def _rewrite_numeric(n: TypeRef, ctx: TranslateContext) -> TypeRef:
    """numeric(p,s) → Decimal(P,S); numeric без параметров → Decimal256."""
    n.schema = None
    if n.params:
        n.name = "Decimal"
    else:
        n.name = "Decimal256"
    return n


_RULE_NUMERIC = Rule(
    rule_id="pg_ch_type_numeric",
    title="numeric / decimal → Decimal / Decimal256 (тип D)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="TypeRef",
    kind=Kind.D,
    when=lambda n: n.name.upper() == "NUMERIC",
    rewrite=_rewrite_numeric,
    message=(
        "В CH максимальная точность — 76 значащих цифр (Decimal256); "
        "PGSQL numeric без параметров допускает до 131 072 цифр до запятой "
        "и 16 383 цифр после."
    ),
)


def _rewrite_char(n: TypeRef, ctx: TranslateContext) -> TypeRef:
    """character(n) / char(n) → FixedString(N), параметр длины сохраняется."""
    n.name = "FixedString"
    n.schema = None
    return n


_RULE_CHAR = Rule(
    rule_id="pg_ch_type_char",
    title="character / char → FixedString (тип D)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="TypeRef",
    kind=Kind.D,
    when=lambda n: n.name.upper() == "CHAR",
    rewrite=_rewrite_char,
    message=(
        "PGSQL хранит n символов Unicode и дополняет пробелами; "
        "CH хранит ровно N байт и дополняет нулевыми байтами (\\0)."
    ),
)


def _rewrite_timestamp(n: TypeRef, ctx: TranslateContext) -> TypeRef:
    """timestamp → DateTime64(6); если пользователь указал точность — сохраняем."""
    n.name = "DateTime64"
    n.schema = None
    n.time_zone = None
    if not n.params:
        n.params = [_int_param(6)]
    return n


_RULE_TIMESTAMP = Rule(
    rule_id="pg_ch_type_timestamp",
    title="timestamp without time zone → DateTime64(6) (тип D)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="TypeRef",
    kind=Kind.D,
    when=lambda n: n.name.upper() == "TIMESTAMP" and not n.time_zone,
    rewrite=_rewrite_timestamp,
    message=(
        "Диапазон PGSQL (4713 до н.э. – 294276 г.) существенно шире диапазона "
        "CH (1900-01-01 – 2299-12-31); точность по умолчанию совпадает (микросекунды)."
    ),
)


def _rewrite_timestamptz(n: TypeRef, ctx: TranslateContext) -> TypeRef:
    """timestamp with time zone → DateTime64(6) без параметра часового пояса."""
    n.name = "DateTime64"
    n.schema = None
    n.time_zone = None   # пользователь выбрал «пустой параметр»
    if not n.params:
        n.params = [_int_param(6)]
    return n


_RULE_TIMESTAMPTZ = Rule(
    rule_id="pg_ch_type_timestamptz",
    title="timestamp with time zone → DateTime64(6) (тип D)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="TypeRef",
    kind=Kind.D,
    when=lambda n: n.name.upper() == "TIMESTAMP" and bool(n.time_zone),
    rewrite=_rewrite_timestamptz,
    message=(
        "PGSQL хранит значение в UTC, зона отображения — параметр сессии; "
        "CH хранит зону в метаданных столбца, все строки столбца разделяют "
        "единый пояс."
    ),
)

_RULE_DATE = Rule(
    rule_id="pg_ch_type_date",
    title="date → Date (тип D)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="TypeRef",
    kind=Kind.D,
    when=lambda n: n.name.upper() == "DATE",
    rewrite=_rewrite_name("Date"),
    message=(
        "PGSQL date: 4713 до н.э. – 5874897 г.; "
        "CH Date: 1970-01-01 – 2149-06-06, Date32: 1900–2299."
    ),
)

_RULE_BYTEA = Rule(
    rule_id="pg_ch_type_bytea",
    title="bytea → String (тип D)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="TypeRef",
    kind=Kind.D,
    when=lambda n: n.name.upper() == "BYTEA",
    rewrite=_rewrite_name("String"),
    message=(
        "PGSQL: байтовый массив с hex / escape-представлением; "
        "CH: String без разделения на текст и байты, "
        "операции с байтами — через функции unhex / hex."
    ),
)

_RULE_JSONB = Rule(
    rule_id="pg_ch_type_jsonb",
    title="jsonb → JSON (тип D)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="TypeRef",
    kind=Kind.D,
    when=lambda n: n.name.upper() == "JSONB",
    rewrite=_rewrite_name("JSON"),
    message=(
        "jsonb в PGSQL — бинарный формат с индексацией; "
        "CH JSON-тип устроен иначе, без операторов PGSQL ->, ->>, @>."
    ),
)

_RULE_ARRAY = Rule(
    rule_id="pg_ch_type_array",
    title="тип[] / ARRAY → Array(T) (тип D)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="TypeRef",
    kind=Kind.D,
    when=lambda n: n.array_dims > 0,
    rewrite=None,   # array_dims сохраняется; эмиттер рендерит Array(T)
    message=(
        "Семантически близки, но CH поддерживает только одномерные массивы "
        "в качестве столбца; многомерные массивы эмулируются через "
        "Array(Array(T)) с ограничениями на агрегацию и JOIN."
    ),
)


_E_MSG = "нет аналога в ClickHouse"

_RULE_TIMETZ = Rule(
    rule_id="pg_ch_type_timetz",
    title="time with time zone → (тип E: нет аналога в CH)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="TypeRef",
    kind=Kind.E,
    when=lambda n: n.name.upper() == "TIME" and bool(n.time_zone),
    rewrite=None,
    message=_E_MSG,
)

_RULE_INTERVAL = Rule(
    rule_id="pg_ch_type_interval",
    title="interval → (тип E: нет аналога в CH)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="TypeRef",
    kind=Kind.E,
    when=lambda n: n.name.upper() == "INTERVAL",
    rewrite=None,
    message=(
        "В ClickHouse нет типа-интервала на уровне хранения; "
        "интервалы поддерживаются только как выражения."
    ),
)

_RULE_SMALLSERIAL = Rule(
    rule_id="pg_ch_type_smallserial",
    title="smallserial → (тип E: нет аналога в CH)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="TypeRef",
    kind=Kind.E,
    when=lambda n: n.name.upper() == "SMALLSERIAL",
    rewrite=None,
    message=_E_MSG,
)

_RULE_SERIAL = Rule(
    rule_id="pg_ch_type_serial",
    title="serial → (тип E: нет аналога в CH)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="TypeRef",
    kind=Kind.E,
    when=lambda n: n.name.upper() == "SERIAL",
    rewrite=None,
    message=_E_MSG,
)

_RULE_BIGSERIAL = Rule(
    rule_id="pg_ch_type_bigserial",
    title="bigserial → (тип E: нет аналога в CH)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="TypeRef",
    kind=Kind.E,
    when=lambda n: n.name.upper() == "BIGSERIAL",
    rewrite=None,
    message=_E_MSG,
)

_RULE_TSVECTOR = Rule(
    rule_id="pg_ch_type_tsvector",
    title="tsvector → (тип E: нет аналога в CH)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="TypeRef",
    kind=Kind.E,
    when=lambda n: n.name.upper() == "TSVECTOR",
    rewrite=None,
    message=_E_MSG,
)

_RULE_TSQUERY = Rule(
    rule_id="pg_ch_type_tsquery",
    title="tsquery → (тип E: нет аналога в CH)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="TypeRef",
    kind=Kind.E,
    when=lambda n: n.name.upper() == "TSQUERY",
    rewrite=None,
    message=_E_MSG,
)

_RANGE_TYPES = frozenset({
    "INT4RANGE", "INT8RANGE", "NUMRANGE",
    "DATERANGE", "TSRANGE", "TSTZRANGE",
})

_RULE_RANGE = Rule(
    rule_id="pg_ch_type_range",
    title="диапазонные типы (int4range и др.) → (тип E: нет аналога в CH)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="TypeRef",
    kind=Kind.E,
    when=lambda n: n.name.upper() in _RANGE_TYPES,
    rewrite=None,
    message=_E_MSG,
)

_GEO_TYPES = frozenset({
    "POINT", "LINE", "LSEG", "BOX", "PATH", "POLYGON", "CIRCLE",
})

_RULE_GEO = Rule(
    rule_id="pg_ch_type_geo",
    title="геометрические типы (point, line, …) → (тип E: нет аналога в CH)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="TypeRef",
    kind=Kind.E,
    when=lambda n: n.name.upper() in _GEO_TYPES,
    rewrite=None,
    message=_E_MSG,
)

_PSEUDO_TYPES = frozenset({
    "REGCLASS", "REGPROC", "REGTYPE", "REGOPER", "REGPROCEDURE",
    "REGROLE", "REGNAMESPACE", "PG_LSN", "TXID_SNAPSHOT",
})

_RULE_PSEUDO = Rule(
    rule_id="pg_ch_type_pseudo",
    title="псевдо-типы и служебные типы PG → (тип E: нет аналога в CH)",
    source=Dialect.POSTGRES,
    target=Dialect.CLICKHOUSE,
    node_kind="TypeRef",
    kind=Kind.E,
    when=lambda n: n.name.upper() in _PSEUDO_TYPES,
    rewrite=None,
    message=_E_MSG,
)

_ALL_RULES = [
    # A
    _RULE_UUID,
    # B
    _RULE_REAL,
    _RULE_DOUBLE,
    _RULE_TIME,
    # C
    _RULE_SMALLINT,
    _RULE_INTEGER,
    _RULE_BIGINT,
    _RULE_TEXT,
    _RULE_VARCHAR,
    _RULE_BOOLEAN,
    _RULE_JSON,
    # D
    _RULE_NUMERIC,
    _RULE_CHAR,
    _RULE_TIMESTAMP,
    _RULE_TIMESTAMPTZ,
    _RULE_DATE,
    _RULE_BYTEA,
    _RULE_JSONB,
    _RULE_ARRAY,
    # E
    _RULE_TIMETZ,
    _RULE_INTERVAL,
    _RULE_SMALLSERIAL,
    _RULE_SERIAL,
    _RULE_BIGSERIAL,
    _RULE_TSVECTOR,
    _RULE_TSQUERY,
    _RULE_RANGE,
    _RULE_GEO,
    _RULE_PSEUDO,
]

for _rule in _ALL_RULES:
    default_translator.register(_rule)
