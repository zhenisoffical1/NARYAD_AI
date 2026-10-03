import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import ws
from app.api import api_router
from app.config import DEV_JWT_SECRET, settings
from app.errors import DomainError
from app.services.notifications.bus import bus

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("naryadai")

FIELD_NAMES = {
    "login": "логин",
    "pin": "ПИН",
    "description": "описание",
    "reason": "причина",
    "equipment_id": "оборудование",
    "assignee_id": "исполнитель",
    "priority": "приоритет",
    "deadline_at": "срок",
}

ERROR_TEXT = {
    "missing": "обязательное поле",
    "string_too_short": "слишком короткое значение",
    "string_too_long": "слишком длинное значение",
    "string_pattern_mismatch": "неверный формат",
    "int_parsing": "нужно целое число",
    "float_parsing": "нужно число",
    "enum": "недопустимое значение",
    "greater_than": "значение слишком маленькое",
    "greater_than_equal": "значение слишком маленькое",
    "less_than_equal": "значение слишком большое",
    "datetime_parsing": "неверная дата или время",
    "json_invalid": "неверный JSON",
}


def _humanize_validation(errors: list[Any]) -> list[dict[str, str]]:
    result = []
    for err in errors:
        loc = [str(p) for p in err.get("loc", ()) if p not in ("body", "query", "path")]
        field = loc[-1] if loc else ""
        name = FIELD_NAMES.get(field, field)
        if field == "pin" and err.get("type") == "string_pattern_mismatch":
            message = "ПИН — ровно 4 цифры"
        else:
            message = f"{name}: {ERROR_TEXT.get(err.get('type', ''), 'неверное значение')}"
        result.append({"field": ".".join(loc), "message": message})
    return result


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    if settings.jwt_secret == DEV_JWT_SECRET and not settings.demo_mode:
        log.warning("JWT_SECRET не задан — используйте случайную строку на сервере")
    await bus.start()
    log.info("НарядAI запущен: ИИ — %s", "mock" if settings.llm_mock else settings.llm_model)
    yield
    await bus.stop()


def create_app() -> FastAPI:
    app = FastAPI(
        title="НарядAI API",
        description="Выдача и контроль нарядов. REST API — точка интеграции с 1С / ERP / ТОиР.",
        version="0.1.0",
        docs_url="/api/docs",
        redoc_url=None,
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.exception_handler(DomainError)
    async def domain_error_handler(_request: Request, exc: DomainError) -> JSONResponse:
        return JSONResponse({"detail": exc.message}, status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        errors = _humanize_validation(list(exc.errors()))
        detail = "Проверьте поля: " + "; ".join(e["message"] for e in errors) + "."
        return JSONResponse({"detail": detail, "errors": errors}, status_code=422)

    app.include_router(api_router)
    app.include_router(ws.router)
    return app


app = create_app()
