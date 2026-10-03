FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Сначала только зависимости — слой кэшируется, пока не меняется pyproject.toml.
# Сам проект не устанавливается: код запускается из /app.
COPY pyproject.toml ./
RUN mkdir -p app seed && touch app/__init__.py seed/__init__.py \
    && pip install ".[dev]" \
    && pip uninstall -y naryadai-backend \
    && rm -rf app seed build *.egg-info

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
