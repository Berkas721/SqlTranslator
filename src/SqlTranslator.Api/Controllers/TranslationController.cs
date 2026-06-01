using Microsoft.AspNetCore.Mvc;
using System.Text;

namespace SqlTranslator.Api.Controllers;

[ApiController]
[Route("api")]
public class TranslationController : ControllerBase
{
    private readonly IHttpClientFactory _httpClientFactory;
    private readonly string _pythonBaseUrl;

    public TranslationController(IHttpClientFactory httpClientFactory, IConfiguration configuration)
    {
        _httpClientFactory = httpClientFactory;
        _pythonBaseUrl = configuration["TranslatorService:BaseUrl"] ?? "http://localhost:8000";
    }

    [HttpPost("translate")]
    public async Task<IActionResult> Translate(
        [FromQuery(Name = "source-dialect")] string sourceDialect = "postgres",
        [FromQuery(Name = "target-dialect")] string targetDialect = "clickhouse")
    {
        using var reader = new StreamReader(Request.Body, Encoding.UTF8);
        var sql = await reader.ReadToEndAsync();

        var client = _httpClientFactory.CreateClient("PythonTranslator");
        var content = new StringContent(sql, Encoding.UTF8, "text/plain");

        var url = $"{_pythonBaseUrl}/translate"
                + $"?source_dialect={Uri.EscapeDataString(sourceDialect)}"
                + $"&target_dialect={Uri.EscapeDataString(targetDialect)}";

        HttpResponseMessage response;
        try
        {
            response = await client.PostAsync(url, content);
        }
        catch (TaskCanceledException ex) when (ex.InnerException is TimeoutException)
        {
            return StatusCode(504, new { detail = $"Translator service timeout: {ex.Message}" });
        }
        catch (HttpRequestException ex)
        {
            return StatusCode(502, new { detail = $"Translator service unavailable: {ex.Message}" });
        }

        var body = await response.Content.ReadAsStringAsync();

        return response.IsSuccessStatusCode
            ? Content(body, "application/json")
            : StatusCode((int)response.StatusCode, body);
    }
}
