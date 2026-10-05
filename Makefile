# Команды для Linux / macOS / CI. На Windows без make — то же самое в tasks.ps1.

COMPOSE ?= docker compose
BACKEND = $(COMPOSE) exec backend
# Одноразовый контейнер бэкенда: тесты и линтер не требуют ничего, кроме Docker
BACKEND_RUN = $(COMPOSE) run --rm --no-deps backend

.PHONY: up down logs ps migrate seed seed-check dataset scene test test-backend test-frontend lint fmt ai-eval e2e

up:  ## Поднять всю систему
	$(COMPOSE) up -d --build

down:
	$(COMPOSE) down

logs:
	$(COMPOSE) logs -f --tail=100

ps:
	$(COMPOSE) ps

migrate:
	$(BACKEND) alembic upgrade head

seed:  ## Наполнить базу тестовыми данными (детерминированно, seed=42)
	$(BACKEND) python -m seed

seed-check:  ## Статистика данных и проверка заложенных закономерностей
	$(BACKEND) python -m seed.check

dataset:  ## Выгрузить тестовый набор данных в data/dataset (CSV)
	cd backend && python -m seed.export

scene:  ## Пересоздать только демо-сцену
	$(BACKEND) python -m seed --scene-only

test: test-backend test-frontend

test-backend:
	$(BACKEND_RUN) pytest

test-frontend:
	cd frontend && npm ci && npm run typecheck

lint:
	$(BACKEND_RUN) sh -c "ruff check . && ruff format --check . && mypy app seed"
	cd frontend && npm run lint

fmt:
	cd backend && ruff check --fix . && ruff format .

ai-eval:  ## Точность ИИ-проверки на размеченном наборе
	$(BACKEND_RUN) python -m tests.ai_eval

e2e:  ## Сквозной демо-сценарий (Playwright)
	cd frontend && npm run e2e
