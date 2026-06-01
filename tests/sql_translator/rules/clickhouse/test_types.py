"""Правила pg→ch для TypeRef.

Источник правил: ``src/sql_translator/ast/rules/clickhouse/types.py``.
"""
from __future__ import annotations

import pytest

from sql_translator.ast.metadata import Kind
from sql_translator.ast.nodes import Literal, TypeRef


def _type(make, name, **kwargs):
    return make(TypeRef, name=name, **kwargs)


def _int_param(make, value=10):
    return make(Literal, value=value, literal_kind="int", raw=str(value))


class TestUUID:
    def test_uuid_unchanged(self, make, apply):
        n = _type(make, "UUID")
        r = apply(n)
        assert r.name == "UUID"

    def test_uuid_no_annotation(self, make, apply, rule_ids):
        n = _type(make, "UUID")
        r = apply(n)
        # Kind.A без message.
        assert "pg_ch_type_uuid" not in rule_ids(r)

    @pytest.mark.parametrize("name", ["uuid", "Uuid"])
    def test_uuid_case_insensitive(self, make, apply, name):
        n = _type(make, name)
        r = apply(n)
        # Правило срабатывает на upper(name), но rewrite=None — имя не меняется.
        assert r.name == name


class TestRealDouble:
    def test_real_to_Float32(self, make, apply):
        n = _type(make, "REAL", schema="pg_catalog")
        r = apply(n)
        assert r.name == "Float32"
        assert r.schema is None

    def test_double_to_Float64(self, make, apply):
        n = _type(make, "DOUBLE PRECISION")
        r = apply(n)
        assert r.name == "Float64"

    def test_real_no_annotation(self, make, apply, rule_ids):
        n = _type(make, "REAL")
        r = apply(n)
        assert "pg_ch_type_real" not in rule_ids(r)


class TestTimeWithoutZone:
    def test_time_no_tz_renamed_to_Time(self, make, apply):
        n = _type(make, "TIME", time_zone=None)
        r = apply(n)
        assert r.name == "Time"

    def test_time_with_tz_not_renamed(self, make, apply):
        n = _type(make, "TIME", time_zone="WITH TIME ZONE")
        r = apply(n)
        # Правило B не сработало — другое (E) обработает.
        assert r.name == "TIME"


class TestIntegerFamily:
    @pytest.mark.parametrize("name,new_name,rule_id", [
        ("SMALLINT", "Int16", "pg_ch_type_smallint"),
        ("INTEGER",  "Int32", "pg_ch_type_integer"),
        ("BIGINT",   "Int64", "pg_ch_type_bigint"),
    ])
    def test_int_family_renamed_and_kindC(
        self, make, apply, rule_ids, kinds, name, new_name, rule_id
    ):
        n = _type(make, name)
        r = apply(n)
        assert r.name == new_name
        assert rule_id in rule_ids(r)
        assert Kind.C in kinds(r)

    def test_integer_message_mentions_wraparound(self, make, apply):
        n = _type(make, "INTEGER")
        r = apply(n)
        ann = next(a for a in r.annotations if a.rule_id == "pg_ch_type_integer")
        msg = (ann.message or "").lower()
        assert "wraparound" in msg or "smallint" in msg


class TestText:
    def test_text_to_String_kindC(self, make, apply, rule_ids, kinds):
        n = _type(make, "TEXT")
        r = apply(n)
        assert r.name == "String"
        assert "pg_ch_type_text" in rule_ids(r)
        assert Kind.C in kinds(r)


class TestVarchar:
    def test_varchar_to_String_drops_params(self, make, apply):
        n = _type(make, "VARCHAR", params=[_int_param(make, 255)])
        r = apply(n)
        assert r.name == "String"
        assert r.params == []

    def test_varchar_kindC(self, make, apply, rule_ids, kinds):
        n = _type(make, "VARCHAR", params=[_int_param(make, 255)])
        r = apply(n)
        assert "pg_ch_type_varchar" in rule_ids(r)
        assert Kind.C in kinds(r)


class TestBoolean:
    def test_boolean_to_Bool_kindC(self, make, apply, rule_ids, kinds):
        n = _type(make, "BOOLEAN")
        r = apply(n)
        assert r.name == "Bool"
        assert "pg_ch_type_boolean" in rule_ids(r)
        assert Kind.C in kinds(r)


class TestJson:
    def test_json_to_String_kindC(self, make, apply, rule_ids, kinds):
        n = _type(make, "JSON")
        r = apply(n)
        assert r.name == "String"
        assert "pg_ch_type_json" in rule_ids(r)
        assert Kind.C in kinds(r)


class TestNumeric:
    def test_numeric_with_params_to_Decimal(self, make, apply):
        n = _type(make, "NUMERIC", params=[_int_param(make, 10), _int_param(make, 2)])
        r = apply(n)
        assert r.name == "Decimal"
        # Параметры сохранены.
        assert len(r.params) == 2

    def test_numeric_without_params_to_Decimal256(self, make, apply):
        n = _type(make, "NUMERIC")
        r = apply(n)
        assert r.name == "Decimal256"

    def test_numeric_kindD(self, make, apply, rule_ids, kinds):
        n = _type(make, "NUMERIC")
        r = apply(n)
        assert "pg_ch_type_numeric" in rule_ids(r)
        assert Kind.D in kinds(r)


class TestChar:
    def test_char_to_FixedString_keeps_params(self, make, apply):
        n = _type(make, "CHAR", params=[_int_param(make, 8)])
        r = apply(n)
        assert r.name == "FixedString"
        assert len(r.params) == 1

    def test_char_kindD(self, make, apply, rule_ids, kinds):
        n = _type(make, "CHAR", params=[_int_param(make, 8)])
        r = apply(n)
        assert "pg_ch_type_char" in rule_ids(r)
        assert Kind.D in kinds(r)


class TestTimestamp:
    def test_timestamp_no_tz_to_DateTime64(self, make, apply):
        n = _type(make, "TIMESTAMP", time_zone=None)
        r = apply(n)
        assert r.name == "DateTime64"
        # Параметр точности — 6 по умолчанию.
        assert len(r.params) == 1
        assert r.params[0].value == 6
        assert r.time_zone is None

    def test_timestamp_keeps_user_params(self, make, apply):
        n = _type(make, "TIMESTAMP",
                  time_zone=None,
                  params=[_int_param(make, 3)])
        r = apply(n)
        assert r.params[0].value == 3

    def test_timestamp_kindD(self, make, apply, rule_ids, kinds):
        n = _type(make, "TIMESTAMP", time_zone=None)
        r = apply(n)
        assert "pg_ch_type_timestamp" in rule_ids(r)
        assert Kind.D in kinds(r)


class TestTimestampTz:
    def test_timestamptz_to_DateTime64_drops_tz(self, make, apply):
        n = _type(make, "TIMESTAMP", time_zone="WITH TIME ZONE")
        r = apply(n)
        assert r.name == "DateTime64"
        assert r.time_zone is None
        assert r.params[0].value == 6

    def test_timestamptz_kindD(self, make, apply, rule_ids, kinds):
        n = _type(make, "TIMESTAMP", time_zone="WITH TIME ZONE")
        r = apply(n)
        assert "pg_ch_type_timestamptz" in rule_ids(r)
        assert Kind.D in kinds(r)

    def test_timestamptz_does_not_trigger_timestamp_rule(
        self, make, apply, rule_ids
    ):
        n = _type(make, "TIMESTAMP", time_zone="WITH TIME ZONE")
        r = apply(n)
        assert "pg_ch_type_timestamp" not in rule_ids(r)


class TestDate:
    def test_date_renamed_kindD(self, make, apply, rule_ids, kinds):
        n = _type(make, "DATE")
        r = apply(n)
        assert r.name == "Date"
        assert "pg_ch_type_date" in rule_ids(r)
        assert Kind.D in kinds(r)


class TestBytea:
    def test_bytea_to_String_kindD(self, make, apply, rule_ids, kinds):
        n = _type(make, "BYTEA")
        r = apply(n)
        assert r.name == "String"
        assert "pg_ch_type_bytea" in rule_ids(r)
        assert Kind.D in kinds(r)


class TestJsonb:
    def test_jsonb_to_JSON_kindD(self, make, apply, rule_ids, kinds):
        n = _type(make, "JSONB")
        r = apply(n)
        assert r.name == "JSON"
        assert "pg_ch_type_jsonb" in rule_ids(r)
        assert Kind.D in kinds(r)


class TestArrayDims:
    def test_array_dims_triggers_kindD(self, make, apply, rule_ids, kinds):
        n = _type(make, "INTEGER", array_dims=1)
        r = apply(n)
        assert "pg_ch_type_array" in rule_ids(r)
        assert Kind.D in kinds(r)

    def test_array_combined_with_base_type_rule(
        self, make, apply, rule_ids
    ):
        # INTEGER[] — сработают и INTEGER → Int32 (C), и array (D).
        n = _type(make, "INTEGER", array_dims=1)
        r = apply(n)
        ids = rule_ids(r)
        assert "pg_ch_type_integer" in ids
        assert "pg_ch_type_array" in ids
        assert r.name == "Int32"
        assert r.array_dims == 1

    def test_no_array_no_rule(self, make, apply, rule_ids):
        n = _type(make, "INTEGER", array_dims=0)
        r = apply(n)
        assert "pg_ch_type_array" not in rule_ids(r)


# Тип E — TIMETZ / INTERVAL / SERIAL-семейство / TSVECTOR / TSQUERY /
#         RANGE / GEO / PSEUDO

class TestTimeTz:
    def test_time_with_tz_triggers_kindE(
        self, make, apply, rule_ids, kinds
    ):
        n = _type(make, "TIME", time_zone="WITH TIME ZONE")
        r = apply(n)
        assert "pg_ch_type_timetz" in rule_ids(r)
        assert Kind.E in kinds(r)

    def test_time_without_tz_no_E(self, make, apply, rule_ids):
        n = _type(make, "TIME", time_zone=None)
        r = apply(n)
        assert "pg_ch_type_timetz" not in rule_ids(r)


class TestInterval:
    def test_interval_triggers_kindE(self, make, apply, rule_ids, kinds):
        n = _type(make, "INTERVAL")
        r = apply(n)
        assert "pg_ch_type_interval" in rule_ids(r)
        assert Kind.E in kinds(r)


class TestSerialFamily:
    @pytest.mark.parametrize("name,rule_id", [
        ("SMALLSERIAL", "pg_ch_type_smallserial"),
        ("SERIAL",      "pg_ch_type_serial"),
        ("BIGSERIAL",   "pg_ch_type_bigserial"),
    ])
    def test_serial_triggers_kindE(
        self, make, apply, rule_ids, kinds, name, rule_id
    ):
        n = _type(make, name)
        r = apply(n)
        assert rule_id in rule_ids(r)
        assert Kind.E in kinds(r)


class TestTsvectorTsquery:
    @pytest.mark.parametrize("name,rule_id", [
        ("TSVECTOR", "pg_ch_type_tsvector"),
        ("TSQUERY",  "pg_ch_type_tsquery"),
    ])
    def test_tsvector_tsquery_kindE(
        self, make, apply, rule_ids, kinds, name, rule_id
    ):
        n = _type(make, name)
        r = apply(n)
        assert rule_id in rule_ids(r)
        assert Kind.E in kinds(r)


class TestRangeTypes:
    @pytest.mark.parametrize("name", [
        "INT4RANGE", "INT8RANGE", "NUMRANGE",
        "DATERANGE", "TSRANGE", "TSTZRANGE",
    ])
    def test_range_triggers_kindE(
        self, make, apply, rule_ids, kinds, name
    ):
        n = _type(make, name)
        r = apply(n)
        assert "pg_ch_type_range" in rule_ids(r)
        assert Kind.E in kinds(r)

    def test_non_range_no_rule(self, make, apply, rule_ids):
        n = _type(make, "INTEGER")
        r = apply(n)
        assert "pg_ch_type_range" not in rule_ids(r)


class TestGeoTypes:
    @pytest.mark.parametrize("name", [
        "POINT", "LINE", "LSEG", "BOX", "PATH", "POLYGON", "CIRCLE",
    ])
    def test_geo_triggers_kindE(
        self, make, apply, rule_ids, kinds, name
    ):
        n = _type(make, name)
        r = apply(n)
        assert "pg_ch_type_geo" in rule_ids(r)
        assert Kind.E in kinds(r)


class TestPseudoTypes:
    @pytest.mark.parametrize("name", [
        "REGCLASS", "REGPROC", "REGTYPE", "REGOPER", "REGPROCEDURE",
        "REGROLE", "REGNAMESPACE", "PG_LSN", "TXID_SNAPSHOT",
    ])
    def test_pseudo_triggers_kindE(
        self, make, apply, rule_ids, kinds, name
    ):
        n = _type(make, name)
        r = apply(n)
        assert "pg_ch_type_pseudo" in rule_ids(r)
        assert Kind.E in kinds(r)


class TestTypesFallback:
    def test_unknown_type_gets_fallback(self, make, apply, rule_ids):
        n = _type(make, "SOME_RANDOM_TYPE")
        r = apply(n)
        assert "pg_ch.fallback" in rule_ids(r)

    def test_uuid_blocks_fallback(self, make, apply, rule_ids):
        n = _type(make, "UUID")
        r = apply(n)
        assert "pg_ch.fallback" not in rule_ids(r)
