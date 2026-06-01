# Правила преобразования DDL PostgreSQL → ClickHouse.
# Импорт подмодулей регистрирует все правила в default_translator.
from . import create_database, create_function, create_index, create_table, create_view  # noqa: F401
