# syntax=docker/dockerfile:1.7
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Pango — для PDF-отчётов (WeasyPrint), Roboto — шрифт отчётов, как в интерфейсе
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libharfbuzz-subset0 fonts-roboto fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

# Сначала только зависимости — слой кэшируется, пока не меняется pyproject.toml.
# Кэш pip переживает пересборки: повторная сборка не скачивает пакеты заново.
# Сам проект не устанавливается: код запускается из /app.
COPY pyproject.toml ./
RUN --mount=type=cache,target=/root/.cache/pip \
    mkdir -p app seed && touch app/__init__.py seed/__init__.py \
    && pip install ".[dev]" \
    && pip uninstall -y naryadai-backend \
    && rm -rf app seed build *.egg-info

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
