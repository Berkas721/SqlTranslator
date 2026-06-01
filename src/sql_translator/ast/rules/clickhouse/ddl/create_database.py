"""Правила преобразования CREATE DATABASE / CREATE USER / GRANT / ALTER ROLE
"""
from __future__ import annotations

from src.ast.metadata import Dialect, Kind
from src.ast.registry import Rule, TranslateContext, default_translator

_E_MSG = "нет аналога в ClickHouse"

_CREATE_DATABASE_RULES: list[Rule] = [
    Rule(
        rule_id="pg_ch_create_db_base",
        title="CreateDatabaseStmt (базовый проход, тип A)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CreateDatabaseStmt",
        kind=Kind.A,
        when=lambda n: True,
        rewrite=None,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_create_db_encoding",
        title="ENCODING / LC_COLLATE / LC_CTYPE / LOCALE (тип C)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CreateDatabaseStmt",
        kind=Kind.C,
        when=lambda n: any([n.encoding, n.lc_collate, n.lc_ctype, n.locale]),
        rewrite=None,
        message=(
            "В CH параметры кодировки и локали управляются на уровне сервера, не базы."
        ),
    ),
    Rule(
        rule_id="pg_ch_create_db_owner",
        title="OWNER [=] role (тип D)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CreateDatabaseStmt",
        kind=Kind.D,
        when=lambda n: n.owner is not None,
        rewrite=None,
        message=(
            "В CH отдельного понятия владельца базы нет; "
            "доступ управляется ролями и привилегиями."
        ),
    ),
    Rule(
        rule_id="pg_ch_create_db_template",
        title="TEMPLATE [=] template (тип D)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CreateDatabaseStmt",
        kind=Kind.D,
        when=lambda n: n.template is not None,
        rewrite=None,
        message=(
            "Концептуально близкий выбор движка базы, но семантика — "
            "тип хранилища, а не инициализационный снимок."
        ),
    ),
]


def _rewrite_user_auth(n, ctx: TranslateContext):
    """Оставить пароль как есть, пометить что нужно указать метод хэширования."""
    if n.auth_method is None:
        n.auth_method = "sha256_password"   # безопасный дефолт для CH
    return n


_CREATE_USER_RULES: list[Rule] = [
    Rule(
        rule_id="pg_ch_create_user_base",
        title="CreateUserStmt (базовый проход, тип A)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CreateUserStmt",
        kind=Kind.A,
        when=lambda n: True,
        rewrite=None,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_create_user_password",
        title="CREATE USER name WITH PASSWORD 'pwd' → IDENTIFIED WITH method BY 'pwd' (тип B)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="CreateUserStmt",
        kind=Kind.B,
        when=lambda n: n.password is not None,
        rewrite=_rewrite_user_auth,
        message=None,
    ),
]


def _rewrite_alter_role_password(n, ctx: TranslateContext):
    """ALTER USER name PASSWORD → ALTER USER name IDENTIFIED WITH method BY 'pwd'."""
    if n.auth_method is None:
        n.auth_method = "sha256_password"
    return n


_ALTER_ROLE_RULES: list[Rule] = [
    Rule(
        rule_id="pg_ch_alter_role_base",
        title="AlterRoleStmt (базовый проход, тип A)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="AlterRoleStmt",
        kind=Kind.A,
        when=lambda n: True,
        rewrite=None,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_alter_role_password",
        title="ALTER USER name PASSWORD 'pwd' → IDENTIFIED WITH method BY 'pwd' (тип B)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="AlterRoleStmt",
        kind=Kind.B,
        when=lambda n: n.password is not None,
        rewrite=_rewrite_alter_role_password,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_alter_role_settings",
        title="ALTER ROLE name SET configuration_parameter → ALTER ROLE name SETTINGS (тип D)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="AlterRoleStmt",
        kind=Kind.D,
        when=lambda n: bool(n.settings),
        rewrite=None,
        message=(
            "Наборы параметров полностью не пересекаются."
        ),
    ),
]


_GRANT_RULES: list[Rule] = [
    Rule(
        rule_id="pg_ch_grant_base",
        title="GrantStmt (базовый проход, тип A)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="GrantStmt",
        kind=Kind.A,
        when=lambda n: True,
        rewrite=None,
        message=None,
    ),
    Rule(
        rule_id="pg_ch_grant_privilege",
        title="GRANT privilege ON object TO grantee (тип C)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="GrantStmt",
        kind=Kind.C,
        when=lambda n: not n.is_role_grant and bool(n.privileges),
        rewrite=None,
        message=(
            "Наборы привилегий полностью не совпадают: в PGSQL есть REFERENCES, "
            "TRIGGER, TEMPORARY, EXECUTE; в CH — KILL QUERY, SYSTEM FLUSH LOGS, "
            "SOURCES, ACCESS MANAGEMENT."
        ),
    ),
    Rule(
        rule_id="pg_ch_grant_role",
        title="GRANT role TO user [WITH ADMIN OPTION] (тип D)",
        source=Dialect.POSTGRES,
        target=Dialect.CLICKHOUSE,
        node_kind="GrantStmt",
        kind=Kind.D,
        when=lambda n: n.is_role_grant,
        rewrite=None,
        message=(
            "В PGSQL роли и пользователи — единое понятие (пользователь — роль с LOGIN); "
            "в CH они разделены."
        ),
    ),
]


for _rule in (
    _CREATE_DATABASE_RULES
    + _CREATE_USER_RULES
    + _ALTER_ROLE_RULES
    + _GRANT_RULES
):
    default_translator.register(_rule)
