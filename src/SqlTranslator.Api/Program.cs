var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllers();
builder.Services.AddHttpClient("PythonTranslator", client =>
{
    // Таймаут запроса к Python-сервису. Конфигурируется через
    // TranslatorService:HttpTimeoutSeconds; по умолчанию 30 c.
    var timeoutSec = builder.Configuration.GetValue<int?>(
        "TranslatorService:HttpTimeoutSeconds") ?? 30;
    client.Timeout = TimeSpan.FromSeconds(timeoutSec);
});

var app = builder.Build();

app.UseDefaultFiles();   // "/" → wwwroot/index.html
app.UseStaticFiles();    // serve wwwroot/ files

app.MapControllers();

app.Run();

// Чтобы WebApplicationFactory<Program> из интеграционных тестов
// смог сослаться на этот тип.
public partial class Program { }
