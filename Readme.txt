Запуск:
1) из корня проекта с активированным venv: .venv\Scripts\uvicorn sql_translator.api.app:app --host 0.0.0.0 --port 8000
2) SqlTranslator.Api: dotnet run

тестирование:
1) SonarQube: docker run --rm -it -v "D:\VyzWork\ВКР\SqlTranslator\src\sql_translator:/usr/src" -w /usr/src sonarsource/sonar-scanner-cli sonar-scanner -Dsonar.projectKey=sql_translator -Dsonar.sources=. -Dsonar.host.url=http://host.docker.internal:9000 -Dsonar.login=<YOUR_SONAR_TOKEN> -Dsonar.language=python
2) покрытие: pytest --cov=sql_translator --cov-report=xml:coverage.xml