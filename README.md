# НарядAI

**Наряд выдан — ИИ на контроле.** Система выдачи и контроля нарядов для АО «Костанайские Минералы» (Qostanai AI Industry Hackathon 2026, кейс 1).

Мастер выдаёт наряд с телефона за ≤6 нажатий, исполнитель ведёт его по статусам в PWA и Telegram, ИИ следит за сроками, проверяет закрытый наряд, считает рейтинг и находит закономерности в истории.

> README дополняется по ходу работы: скриншоты, схема архитектуры, описание ИИ-модулей и результаты `ai-eval` появятся к сдаче.

## Запуск

С Docker (рекомендуется):

```bash
cp .env.example .env
docker compose up -d --build
make seed
```

Откройте http://localhost. API и документация — http://localhost/api/docs.

Без Docker на Windows (SQLite):

```powershell
.\tasks.ps1 setup
.\tasks.ps1 dev      # бэкенд :8000 + фронтенд :5173
.\tasks.ps1 seed
```

Ключ `ANTHROPIC_API_KEY` не обязателен: без него ИИ работает в mock-режиме на правилах.

## Тестовые учётные записи

| Роль | Логин | ПИН |
|---|---|---|
| Администратор | admin | 0000 |
| Руководитель | boss | 1111 |
| Мастер смены | master1 | 2222 |
| Исполнитель | worker1 | 3333 |

## Разработка

```bash
make test    # pytest + проверка типов фронтенда
make lint    # ruff, mypy, eslint
```

Структура и правила — в [CLAUDE.md](CLAUDE.md), решения — в [docs/DECISIONS.md](docs/DECISIONS.md), ход работ — в [docs/PROGRESS.md](docs/PROGRESS.md).
