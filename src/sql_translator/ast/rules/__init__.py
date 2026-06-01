# Пакет правил преобразования диалектов AST.
#
# Для активации правил нужен явный импорт диалектного подпакета:
#
#     import src.ast.rules.clickhouse
#
# После этого все правила регистрируются в default_translator и применяются
# при вызове translate_to(Dialect.CLICKHOUSE).
