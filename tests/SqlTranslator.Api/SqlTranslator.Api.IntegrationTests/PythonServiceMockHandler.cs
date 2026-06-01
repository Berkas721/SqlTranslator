using System.Net;
using System.Text;

namespace SqlTranslator.Api.IntegrationTests;

/// <summary>
/// Mock-обработчик HTTP-сообщений, играющий роль Python-сервиса для интеграционных
/// тестов ASP.NET-эндпоинта <c>POST /api/translate</c>.
/// </summary>
public sealed class PythonServiceMockHandler : HttpMessageHandler
{
    public Func<HttpRequestMessage, CancellationToken, Task<HttpResponseMessage>> Respond { get; set; }
        = (_, _) => Task.FromResult(Ok("""{"sql":"","annotations":[]}"""));

    public HttpRequestMessage? LastRequest { get; private set; }
    public string? LastRequestBody { get; private set; }
    public int CallCount { get; private set; }

    protected override async Task<HttpResponseMessage> SendAsync(
        HttpRequestMessage request, CancellationToken cancellationToken)
    {
        LastRequest = request;
        LastRequestBody = request.Content is null
            ? null
            : await request.Content.ReadAsStringAsync(cancellationToken);
        CallCount++;
        return await Respond(request, cancellationToken);
    }

    public static HttpResponseMessage Ok(string jsonBody) =>
        new(HttpStatusCode.OK)
        {
            Content = new StringContent(jsonBody, Encoding.UTF8, "application/json"),
        };

    public static HttpResponseMessage Status(HttpStatusCode code, string body) =>
        new(code)
        {
            Content = new StringContent(body, Encoding.UTF8, "application/json"),
        };
}
