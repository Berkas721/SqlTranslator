# Правила преобразования PostgreSQL → ClickHouse.
# Импорт подмодулей регистрирует все правила в default_translator.
from . import ddl, dml, expressions, functions, literals, operators, tcl, types  # noqa: F401
