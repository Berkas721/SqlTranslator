# Правила преобразования DML PostgreSQL → ClickHouse.
# Импорт подмодулей регистрирует все правила в default_translator.
from . import copy, insert, merge, select  # noqa: F401
