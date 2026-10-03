# Ход работ

## Этап 1. Каркас — готово (3 октября)

Сделано:
- бэкенд: FastAPI, настройки через `.env`, async SQLAlchemy, все сущности раздела 5 и миграция `0001`, `/api/health`, OpenAPI на `/api/docs`;
- `services/state_machine.py`: полная таблица переходов, ошибки 409/403/422 на русском, журнал `order_events`, живые события; тесты на все разрешённые и ключевые запрещённые переходы;
- вход логин + ПИН, JWT, `require_role`, блокировка после 5 неверных попыток;
- WebSocket `/ws`: подписка по роли из токена, адресные события исполнителю, LISTEN/NOTIFY между процессами;
- фронтенд: Vite + React + TS strict + Tailwind 4 + PWA, маршруты `/w /m /panel /boss /admin /dev/ui /demo` с защитой по ролям, вход, `useLiveEvents`, i18n ru/kk;
- инфраструктура: `docker-compose.yml` (db, backend, scheduler, bot, frontend на Caddy), `infra/Caddyfile` с автоматическим HTTPS, `Makefile`, `tasks.ps1` для Windows, GitHub Actions (ruff, mypy, pytest на PostgreSQL, eslint, tsc, сборка);
- базовые учётные записи (`python -m seed`): admin/0000, boss/1111, master1/2222, worker1/3333.

Проверено: 95 тестов бэкенда, ruff, mypy, eslint, tsc, сборка; миграция вверх и вниз; локальный запуск на SQLite — вход мастера, переход в панель, WebSocket «На связи», закрытый чужой раздел.

Не проверено: `docker compose up` — на машине разработки пока нет Docker.

Дальше: API нарядов (2a), дизайн-система (2b), генератор данных (2c).
