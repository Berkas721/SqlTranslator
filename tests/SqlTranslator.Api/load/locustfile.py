"""Нагрузочное тестирование эндпоинта ASP.NET-проксирующего сервиса POST /api/translate.


Поведение управляется переменными окружения:
    HOST              базовый URL ASP.NET (например, http://localhost:5295)
    SCENARIO          constant | ramp | spike    (выбор формы нагрузки)
    TARGET_USERS      пиковое число пользователей (по умолчанию 50)
    DURATION_SEC      длительность сценария в секундах (по умолчанию 600 для
                      constant/ramp; для spike сценарий имеет свою длительность)
    WAIT_MIN/WAIT_MAX случайная пауза между запросами одного пользователя, сек
                      (по умолчанию 1..5)
    WARMUP_SEC        длительность плавного выхода на TARGET_USERS, сек
                      (по умолчанию 30). Без него весь пул спавнится мгновенно,
                      и `max response time` ловит cold-start + JIT + создание
                      HTTP-коннектов, что искажает картину.
    SETTLE_SEC        пауза после завершения warmup до сброса статистики, сек
                      (по умолчанию 30). Применяется в scenario=constant: после
                      WARMUP_SEC + SETTLE_SEC накопленные метрики обнуляются и
                      замер идёт уже по установившемуся режиму.
"""
from __future__ import annotations

import os
import random
from pathlib import Path

import gevent
from locust import HttpUser, LoadTestShape, between, events, task

SCRIPTS_DIR = Path(__file__).parent / "postgres_scripts"
SCRIPTS: list[tuple[str, str]] = []  # (имя_файла, sql)


def _load_scripts() -> None:
    if SCRIPTS:
        return
    for path in sorted(SCRIPTS_DIR.glob("*.sql")):
        SCRIPTS.append((path.name, path.read_text(encoding="utf-8")))
    if not SCRIPTS:
        raise RuntimeError(f"Не найдено .sql в {SCRIPTS_DIR}")


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    return int(raw) if raw else default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    return float(raw) if raw else default


TARGET_USERS = _env_int("TARGET_USERS", 50)
DURATION_SEC = _env_int("DURATION_SEC", 600)
WAIT_MIN     = _env_float("WAIT_MIN", 1.0)
WAIT_MAX     = _env_float("WAIT_MAX", 5.0)
WARMUP_SEC   = _env_int("WARMUP_SEC", 30)
SETTLE_SEC   = _env_int("SETTLE_SEC", 30)
SCENARIO     = (os.environ.get("SCENARIO") or "constant").lower()


_env_ref = None
_reset_scheduled = False


@events.init.add_listener
def _on_init(environment, **_kwargs):
    global _env_ref
    _env_ref = environment
    _load_scripts()
    print(f"[locustfile] загружено {len(SCRIPTS)} PostgreSQL-скриптов")


def _reset_stats_now():
    if _env_ref is not None and _env_ref.stats is not None:
        _env_ref.stats.reset_all()
        print(
            f"[locustfile] статистика обнулена через "
            f"WARMUP_SEC({WARMUP_SEC})+SETTLE_SEC({SETTLE_SEC}) — "
            f"замер начался с установившегося режима"
        )


@events.spawning_complete.add_listener
def _on_spawning_complete(user_count, **_kwargs):
    """Срабатывает каждый раз, когда runner достиг очередной цели по числу
    пользователей. В constant нам нужен ровно один сброс — после первого
    выхода на TARGET_USERS."""
    global _reset_scheduled
    if _reset_scheduled or SCENARIO != "constant":
        return
    if user_count >= TARGET_USERS:
        _reset_scheduled = True
        gevent.spawn_later(SETTLE_SEC, _reset_stats_now)


class TranslatorUser(HttpUser):
    """Каждый пользователь отправляет случайный SQL-скрипт на /api/translate
    со случайной паузой между запросами."""

    wait_time = between(WAIT_MIN, WAIT_MAX)

    @task
    def translate(self):
        if not SCRIPTS:
            _load_scripts()
        name, sql = random.choice(SCRIPTS)
        bucket = _size_bucket(name)
        with self.client.post(
            "/api/translate"
            "?source-dialect=postgres&target-dialect=clickhouse",
            data=sql.encode("utf-8"),
            headers={"Content-Type": "text/plain; charset=utf-8"},
            name=f"POST /api/translate [{bucket}]",
            catch_response=True,
        ) as resp:
            if resp.status_code >= 500:
                resp.failure(f"HTTP {resp.status_code}: {resp.text[:200]}")
            elif resp.status_code >= 400:
                # 4xx — это валидный отклик сервиса, не сбой инфраструктуры
                resp.success()


def _size_bucket(filename: str) -> str:
    if filename.startswith("small_"):
        return "small"
    if filename.startswith("medium_"):
        return "medium"
    if filename.startswith("large_"):
        return "large"
    return "other"


class ScenarioShape(LoadTestShape):
    """Диспетчер сценариев нагрузки.

    SCENARIO=constant: ровные TARGET_USERS пользователей в течение DURATION_SEC.
    SCENARIO=ramp:     линейный рост 0 → TARGET_USERS за DURATION_SEC.
    SCENARIO=spike:    baseline → резкий пик → спад → 0. Длительность фиксирована
                       (~10 минут), независимо от DURATION_SEC.
    """

    use_common_options = True

    def tick(self):
        t = self.get_run_time()

        if SCENARIO == "constant":
            total = WARMUP_SEC + DURATION_SEC
            if t >= total:
                return None
            if t < WARMUP_SEC and WARMUP_SEC > 0:
                progress = t / WARMUP_SEC
                users = max(1, int(round(TARGET_USERS * progress)))
                # spawn_rate ≈ TARGET_USERS / WARMUP_SEC, но не меньше 1/c
                spawn_rate = max(1.0, TARGET_USERS / WARMUP_SEC)
                return (users, spawn_rate)
            return (TARGET_USERS, max(1.0, TARGET_USERS / max(1, WARMUP_SEC)))

        if SCENARIO == "ramp":
            if t >= DURATION_SEC:
                return None
            progress = t / DURATION_SEC
            users = max(1, int(round(TARGET_USERS * progress)))
            spawn_rate = max(1.0, TARGET_USERS / DURATION_SEC * 10.0)
            return (users, spawn_rate)

        if SCENARIO == "spike":
            baseline = max(1, TARGET_USERS // 10)
            phase1_end = WARMUP_SEC                    # плавный рост до baseline
            phase2_end = phase1_end + 60               # удержание baseline
            phase3_end = phase2_end + 60               # пик
            phase4_end = phase3_end + 180              # плато на пике
            phase5_end = phase4_end + 60               # спад
            phase6_end = phase5_end + 180              # tail

            if t < phase1_end and WARMUP_SEC > 0:
                progress = t / WARMUP_SEC
                users = max(1, int(round(baseline * progress)))
                spawn_rate = max(1.0, baseline / WARMUP_SEC)
                return (users, spawn_rate)
            if t < phase2_end:
                return (baseline, max(1.0, baseline / max(1, WARMUP_SEC)))
            if t < phase3_end:
                return (TARGET_USERS, float(TARGET_USERS))
            if t < phase4_end:
                return (TARGET_USERS, max(1.0, TARGET_USERS / 10.0))
            if t < phase5_end:
                return (baseline, float(TARGET_USERS))
            if t < phase6_end:
                return (baseline, max(1.0, baseline / 5.0))
            return None

        raise RuntimeError(f"Unknown SCENARIO={SCENARIO!r}")
