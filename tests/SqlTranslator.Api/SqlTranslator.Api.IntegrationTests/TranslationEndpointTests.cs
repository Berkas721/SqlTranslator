using System.Net;
using System.Net.Http.Headers;
using System.Text;
using FluentAssertions;
using Xunit;

namespace SqlTranslator.Api.IntegrationTests;

/// <summary>
/// Интеграционные тесты ASP.NET-эндпоинта POST /api/translate.
/// </summary>
public sealed class TranslationEndpointTests : IClassFixture<TranslationApiFactory>
{
    private readonly TranslationApiFactory _factory;
    private readonly HttpClient _client;

    public TranslationEndpointTests(TranslationApiFactory factory)
    {
        _factory = factory;
        _client = factory.CreateClient();
    }

    private static StringContent SqlBody(string sql) =>
        new(sql, Encoding.UTF8, "text/plain");

    private const string TranslateUrl =
        "/api/translate?source-dialect=postgres&target-dialect=clickhouse";

    // Python-сервис недоступен

    [Fact]
    public async Task When_python_service_unreachable_returns_502()
    {
        _factory.Mock.Respond = (_, _) =>
            throw new HttpRequestException("connect ECONNREFUSED");

        var resp = await _client.PostAsync(TranslateUrl, SqlBody("SELECT 1"));

        resp.StatusCode.Should().Be(HttpStatusCode.BadGateway);
        var body = await resp.Content.ReadAsStringAsync();
        body.Should().Contain("Translator service unavailable");
        body.Should().Contain("ECONNREFUSED");
    }

    // Python-сервис очень долго отвечает

    [Fact]
    public async Task When_python_service_is_too_slow_returns_504()
    {
        _factory.Mock.Respond = async (_, ct) =>
        {
            await Task.Delay(TimeSpan.FromSeconds(5), ct);
            return PythonServiceMockHandler.Ok("""{"sql":"","annotations":[]}""");
        };

        var resp = await _client.PostAsync(TranslateUrl, SqlBody("SELECT 1"));

        resp.StatusCode.Should().Be(HttpStatusCode.GatewayTimeout);
        var body = await resp.Content.ReadAsStringAsync();
        body.Should().Contain("Translator service timeout");
    }

    // Python-сервис вернул 500

    [Fact]
    public async Task When_python_service_returns_500_status_is_proxied()
    {
        _factory.Mock.Respond = (_, _) => Task.FromResult(
            PythonServiceMockHandler.Status(
                HttpStatusCode.InternalServerError,
                """{"detail":"oops"}"""));

        var resp = await _client.PostAsync(TranslateUrl, SqlBody("SELECT 1"));

        resp.StatusCode.Should().Be(HttpStatusCode.InternalServerError);
        var body = await resp.Content.ReadAsStringAsync();
        body.Should().Contain("oops");
    }

    // Python-сервис вернул некорректный (не-JSON) результат

    [Fact]
    public async Task When_python_service_returns_garbage_body_it_is_passed_through()
    {
        const string garbage = "<<< not a json >>>";
        _factory.Mock.Respond = (_, _) =>
        {
            var msg = new HttpResponseMessage(HttpStatusCode.OK)
            {
                Content = new StringContent(garbage, Encoding.UTF8, "text/plain"),
            };
            return Task.FromResult(msg);
        };

        var resp = await _client.PostAsync(TranslateUrl, SqlBody("SELECT 1"));
        resp.StatusCode.Should().Be(HttpStatusCode.OK);
        resp.Content.Headers.ContentType?.MediaType.Should().Be("application/json");
        var body = await resp.Content.ReadAsStringAsync();
        body.Should().Be(garbage);
    }

    // 5) Невалидный SQL (Python вернул 400) 

    [Fact]
    public async Task When_python_service_returns_400_for_invalid_sql_status_is_proxied()
    {
        _factory.Mock.Respond = (_, _) => Task.FromResult(
            PythonServiceMockHandler.Status(
                HttpStatusCode.BadRequest,
                """{"detail":"Parse error: syntax error at or near \"SELEKT\""}"""));

        var resp = await _client.PostAsync(TranslateUrl, SqlBody("SELEKT 1"));

        resp.StatusCode.Should().Be(HttpStatusCode.BadRequest);
        var body = await resp.Content.ReadAsStringAsync();
        body.Should().Contain("Parse error");
        body.Should().Contain("SELEKT");
    }

    // Валидный SQL: успешный ответ от Python

    [Fact]
    public async Task When_python_service_returns_200_response_is_proxied_as_json()
    {
        const string payload = """
            {"sql":"SELECT 1","annotations":[{"kind":"A","comment":"identity"}]}
            """;
        _factory.Mock.Respond = (_, _) =>
            Task.FromResult(PythonServiceMockHandler.Ok(payload));

        var resp = await _client.PostAsync(TranslateUrl, SqlBody("SELECT 1"));

        resp.StatusCode.Should().Be(HttpStatusCode.OK);
        resp.Content.Headers.ContentType?.MediaType.Should().Be("application/json");
        var body = await resp.Content.ReadAsStringAsync();
        body.Should().Contain("\"sql\":\"SELECT 1\"");
        body.Should().Contain("\"annotations\"");
    }

    // Сквозная проверка проксирования: ASP.NET не ломает контракт

    [Fact]
    public async Task Proxies_query_string_and_body_to_python_service()
    {
        _factory.Mock.Respond = (_, _) =>
            Task.FromResult(PythonServiceMockHandler.Ok("""{"sql":"","annotations":[]}"""));

        const string sql = "SELECT 1, 2, 3 FROM t";
        await _client.PostAsync(
            "/api/translate?source-dialect=postgres&target-dialect=clickhouse",
            SqlBody(sql));

        _factory.Mock.LastRequest.Should().NotBeNull();
        _factory.Mock.LastRequest!.Method.Should().Be(HttpMethod.Post);
        _factory.Mock.LastRequest.RequestUri!.PathAndQuery
            .Should().Be("/translate?source_dialect=postgres&target_dialect=clickhouse");
        _factory.Mock.LastRequestBody.Should().Be(sql);
    }
}
