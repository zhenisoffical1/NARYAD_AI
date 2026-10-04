"""LLM-шлюз: единственное место, откуда система обращается к модели.

- Ответ строго по JSON-схеме (structured outputs) и проверяется Pydantic; один повтор,
  если ответ не прошёл проверку.
- Каждый вызов пишется в `llm_calls`: назначение, модель, время, токены, успех, хэш промпта.
- Без ANTHROPIC_API_KEY, при отказе модели или сбое API возвращается None — вызывающий код
  переходит на правила. Проверка наряда не зависит от доступности внешнего сервиса.
"""

import hashlib
import json
import logging
import time
from functools import cache
from pathlib import Path
from typing import Any

import anthropic
from pydantic import BaseModel, ValidationError

from app.config import settings
from app.db import SessionLocal
from app.models import LlmCall
from app.services.llm.schema import strict_schema

log = logging.getLogger(__name__)

PROMPTS_DIR = Path(__file__).parent / "prompts"
ATTEMPTS = 2  # первый ответ + один повтор при невалидном JSON

# Модели, на которых доступен server-side fallback вида "default" (Claude API)
_FALLBACK_MODELS = ("claude-sonnet-5-5", "claude-opus-5", "claude-fable-5")


@cache
def prompt(name: str) -> str:
    """Системный промпт из файла `prompts/<name>.md` — промпты живут отдельно от кода."""
    return (PROMPTS_DIR / f"{name}.md").read_text(encoding="utf-8").strip()


@cache
def _client() -> anthropic.AsyncAnthropic:
    return anthropic.AsyncAnthropic(
        api_key=settings.anthropic_api_key,
        timeout=settings.llm_timeout_seconds,
        max_retries=1,
    )


def _prompt_hash(system: str, content: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256(system.encode())
    for block in content:
        if block["type"] == "text":
            digest.update(block["text"].encode())
        else:  # картинка: хэшируем данные, а не кладём их в журнал
            digest.update(block["source"]["data"][:4096].encode())
    return digest.hexdigest()


async def _log_call(
    purpose: str,
    model: str,
    started: float,
    prompt_hash: str,
    *,
    ok: bool,
    usage: Any = None,
    error: str | None = None,
) -> None:
    try:
        async with SessionLocal() as session:
            session.add(
                LlmCall(
                    purpose=purpose,
                    model=model,
                    latency_ms=int((time.monotonic() - started) * 1000),
                    input_tokens=getattr(usage, "input_tokens", None),
                    output_tokens=getattr(usage, "output_tokens", None),
                    ok=ok,
                    error=error[:500] if error else None,
                    prompt_hash=prompt_hash,
                )
            )
            await session.commit()
    except Exception:  # журнал не должен ронять проверку
        log.exception("Не удалось записать llm_calls")


def _request(model: str, system: str, content: list[dict[str, Any]], schema: dict[str, Any],
             max_tokens: int) -> dict[str, Any]:  # fmt: skip
    output_config: dict[str, Any] = {"format": {"type": "json_schema", "schema": schema}}
    if "haiku" not in model:  # effort на Haiku 4.5 не поддерживается
        output_config["effort"] = settings.llm_effort
    params: dict[str, Any] = {
        "model": model,
        "max_tokens": max_tokens,
        "system": system,
        "messages": [{"role": "user", "content": content}],
        "output_config": output_config,
    }
    if settings.llm_server_fallback and model.startswith(_FALLBACK_MODELS):
        params["betas"] = ["server-side-fallback-2026-07-01"]
        params["fallbacks"] = "default"
    return params


async def ask_json[T: BaseModel](
    purpose: str,
    output: type[T],
    *,
    system: str,
    content: list[dict[str, Any]],
    fast: bool = False,
    max_tokens: int = 4000,
) -> T | None:
    """Ответ модели как экземпляр `output` или None (mock-режим, отказ, сбой, невалидный JSON)."""
    if settings.llm_mock:
        return None
    model = settings.llm_fast_model if fast else settings.llm_model
    params = _request(model, system, content, strict_schema(output), max_tokens)
    p_hash = _prompt_hash(system, content)
    client = _client()

    for attempt in range(1, ATTEMPTS + 1):
        started = time.monotonic()
        try:
            if "betas" in params:
                response: Any = await client.beta.messages.create(**params)
            else:
                response = await client.messages.create(**params)
        except anthropic.APIStatusError as exc:
            await _log_call(purpose, model, started, p_hash, ok=False,
                            error=f"{exc.status_code}: {exc.message}")  # fmt: skip
            log.warning("LLM %s: ошибка API %s", purpose, exc.status_code)
            return None
        except anthropic.APIError as exc:  # таймаут, сеть
            await _log_call(purpose, model, started, p_hash, ok=False, error=repr(exc))
            log.warning("LLM %s: нет ответа (%s)", purpose, type(exc).__name__)
            return None

        if response.stop_reason == "refusal":
            category = getattr(response.stop_details, "category", None)
            await _log_call(purpose, model, started, p_hash, ok=False,
                            usage=response.usage, error=f"refusal: {category}")  # fmt: skip
            return None

        text = next((b.text for b in response.content if b.type == "text"), "")
        try:
            result = output.model_validate_json(text)
        except ValidationError as exc:
            await _log_call(purpose, model, started, p_hash, ok=False, usage=response.usage,
                            error=f"попытка {attempt}: {exc.errors()[:3]}")  # fmt: skip
            continue
        await _log_call(purpose, model, started, p_hash, ok=True, usage=response.usage)
        return result
    return None


def text_block(text: str) -> dict[str, Any]:
    return {"type": "text", "text": text}


def image_block(jpeg_base64: str) -> dict[str, Any]:
    return {
        "type": "image",
        "source": {"type": "base64", "media_type": "image/jpeg", "data": jpeg_base64},
    }


def facts_json(data: Any) -> str:
    """Факты для промпта — JSON с кириллицей как есть (меньше токенов, читаемо в журнале)."""
    return json.dumps(data, ensure_ascii=False, indent=1, default=str)
