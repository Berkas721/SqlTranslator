using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.DependencyInjection;

namespace SqlTranslator.Api.IntegrationTests;

/// <summary>
/// WebApplicationFactory, поднимающий реальное ASP.NET-приложение в памяти
/// и подменяющий именованный HttpClient «PythonTranslator» так, чтобы он
/// отправлял запросы не на настоящий Python-сервис, а в
/// <see cref="PythonServiceMockHandler"/>.
///
/// Дополнительно сокращает таймаут до 1 секунды — чтобы сценарий «долгая
/// обработка» завершался быстро.
/// </summary>
public sealed class TranslationApiFactory : WebApplicationFactory<Program>
{
    public PythonServiceMockHandler Mock { get; } = new();

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.UseEnvironment("Testing");

        builder.ConfigureAppConfiguration((_, cfg) =>
        {
            cfg.AddInMemoryCollection(new Dictionary<string, string?>
            {
                ["TranslatorService:BaseUrl"]             = "http://python-mock",
                ["TranslatorService:HttpTimeoutSeconds"]  = "1",
            });
        });

        builder.ConfigureServices(services =>
        {
            services
                .AddHttpClient("PythonTranslator")
                .ConfigureHttpClient(c => c.Timeout = TimeSpan.FromSeconds(1))
                .ConfigurePrimaryHttpMessageHandler(() => Mock);
        });
    }
}
