"""LLM-шлюз без сети: подменённый клиент, журнал вызовов, повтор, фолбэк на правила."""

from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import anthropic
import pytest
from httpx2 import Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models import LlmCall
from app.services.llm import anonymize, ask_json, gateway
from app.services.llm.schema import strict_schema
from app.services.verification.facts import CheckResult
from app.services.verification.llm_check import WorksMatchOut, works_match
from app.services.verification.photos import PhotoCheck, compare_photos
from tests.factories import jpeg_bytes
from tests.test_verification import _facts


def _message(text: str, stop_reason: str = "end_turn") -> SimpleNamespace:
    return SimpleNamespace(
        stop_reason=stop_reason,
        stop_details=SimpleNamespace(category="cyber") if stop_reason == "refusal" else None,
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(input_tokens=120, output_tokens=40),
    )


class FakeClient:
    """Отвечает заготовками по очереди и запоминает запросы."""

    def __init__(self, *replies: SimpleNamespace | Exception) -> None:
        self.replies = list(replies)
        self.requests: list[dict[str, Any]] = []
        self.messages = SimpleNamespace(create=self._create)
        self.beta = SimpleNamespace(messages=SimpleNamespace(create=self._create))

    async def _create(self, **params: Any) -> SimpleNamespace:
        self.requests.append(params)
        reply = self.replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


@pytest.fixture
def fake_llm(monkeypatch: pytest.MonkeyPatch) -> Callable[..., FakeClient]:
    monkeypatch.setattr(settings, "anthropic_api_key", "test-key")

    def install(*replies: SimpleNamespace | Exception) -> FakeClient:
        client = FakeClient(*replies)
        monkeypatch.setattr(gateway, "_client", lambda: client)
        return client

    return install


GOOD = (
    '{"match": 0.9, "materials_relevant": true, "issues": [], '
    '"reason": "Уплотнение заменено, течь устранена.", "confidence": 0.85}'
)


async def _calls(session: AsyncSession) -> list[LlmCall]:
    return list(await session.scalars(select(LlmCall).order_by(LlmCall.id)))


def test_strict_schema_closes_objects_and_drops_bounds() -> None:
    schema = strict_schema(WorksMatchOut)
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(schema["properties"])
    assert "maximum" not in schema["properties"]["match"]
    assert "title" not in schema


def test_anonymize_hides_names_phones_and_pins() -> None:
    text = (
        "Ахметов Е. заменил подшипник, Ахметову помогал Ковалёв Андрей Петрович. "
        "Звонить +7 701 123-45-67, ПИН 1234."
    )
    result = anonymize(text, ["Ахметов Ерлан Каиртаевич", "Ковалёв Андрей Петрович"])
    assert "Ахметов" not in result and "Ковалёв" not in result
    assert "701" not in result and "1234" not in result
    assert result.startswith("Исполнитель заменил подшипник")


async def test_mock_mode_makes_no_calls(session: AsyncSession) -> None:
    assert settings.llm_mock
    assert await ask_json("works_match", WorksMatchOut, system="s", content=[]) is None
    assert await _calls(session) == []


async def test_valid_answer_is_parsed_and_logged(
    session: AsyncSession, fake_llm: Callable[..., FakeClient]
) -> None:
    client = fake_llm(_message(GOOD))
    out = await ask_json("works_match", WorksMatchOut, system="s", content=[])
    assert out is not None and out.match == 0.9

    request = client.requests[0]
    assert request["model"] == settings.llm_model
    assert request["output_config"]["format"]["type"] == "json_schema"
    assert request["output_config"]["effort"] == settings.llm_effort
    assert request["fallbacks"] == "default"

    (call,) = await _calls(session)
    assert call.ok and call.purpose == "works_match"
    assert (call.input_tokens, call.output_tokens) == (120, 40)


async def test_invalid_json_is_retried_once(
    session: AsyncSession, fake_llm: Callable[..., FakeClient]
) -> None:
    fake_llm(_message('{"match": 7}'), _message(GOOD))
    out = await ask_json("works_match", WorksMatchOut, system="s", content=[])
    assert out is not None
    assert [c.ok for c in await _calls(session)] == [False, True]


async def test_refusal_and_api_errors_fall_back_to_rules(
    session: AsyncSession, fake_llm: Callable[..., FakeClient]
) -> None:
    fake_llm(_message("", stop_reason="refusal"))
    assert await ask_json("works_match", WorksMatchOut, system="s", content=[]) is None

    error = anthropic.APIConnectionError(request=Request("POST", "https://api.anthropic.com"))
    fake_llm(error)
    assert await ask_json("works_match", WorksMatchOut, system="s", content=[]) is None

    status = anthropic.InternalServerError(
        "boom", response=Response(500, request=Request("POST", "https://x")), body=None
    )
    fake_llm(status)
    assert await ask_json("works_match", WorksMatchOut, system="s", content=[]) is None

    calls = await _calls(session)
    assert [c.ok for c in calls] == [False, False, False]
    assert calls[0].error == "refusal: cyber"


async def test_works_match_uses_model_and_sends_no_names(
    fake_llm: Callable[..., FakeClient],
) -> None:
    bad = (
        '{"match": 0.1, "materials_relevant": false, '
        '"issues": ["Работы про пульт, а заявлена течь масла."], '
        '"reason": "Работы не устраняют течь.", "confidence": 0.9}'
    )
    client = fake_llm(_message(bad))
    facts = _facts(works_done="Ахметов протёр пульт управления")
    result = await works_match(facts, ["Ахметов Ерлан Каиртаевич"])

    assert result.source == "llm"
    assert result.check.status == "fail" and result.check.critical
    assert "Работы про пульт, а заявлена течь масла." in result.check.items
    assert "Списанные материалы не соответствуют выполненным работам." in result.check.items
    sent = client.requests[0]["messages"][0]["content"][0]["text"]
    assert "Ахметов" not in sent and "Исполнитель протёр пульт" in sent


async def test_works_match_falls_back_when_model_is_down(
    fake_llm: Callable[..., FakeClient],
) -> None:
    fake_llm(anthropic.APIConnectionError(request=Request("POST", "https://x")))
    result = await works_match(_facts())
    assert result.source == "rules"
    assert result.check.status == "ok"


async def test_photo_comparison_turns_unfixed_problem_into_rework(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_llm: Callable[..., FakeClient]
) -> None:
    monkeypatch.setattr(settings, "media_dir", tmp_path)
    (tmp_path / "b.jpg").write_bytes(jpeg_bytes(mark=0))
    (tmp_path / "a.jpg").write_bytes(jpeg_bytes(mark=3))
    pair: Any = (SimpleNamespace(path="b.jpg"), SimpleNamespace(path="a.jpg"))
    base = PhotoCheck(CheckResult("photos", "Фото до и после", "ok", "ок"), None, 0.9)

    client = fake_llm(
        _message(
            '{"same_equipment": true, "problem_fixed": "no", "tidy": false, '
            '"issues": ["Под насосом по-прежнему масляное пятно."], "score_1_5": 2, '
            '"confidence": 0.8, "summary": "Течь не устранена."}'
        )
    )
    result = await compare_photos(base, pair, "Течь масла", "Заменено уплотнение")

    assert result.source == "llm" and result.score_1_5 == 2
    assert result.check.critical and result.check.status == "fail"
    assert result.check.items[:2] == [
        "По фото «после» неисправность не устранена.",
        "Под насосом по-прежнему масляное пятно.",
    ]
    assert result.check.penalty == 40  # не устранено 30 + неаккуратно 10
    images = [b for b in client.requests[0]["messages"][0]["content"] if b["type"] == "image"]
    assert len(images) == 2 and images[0]["source"]["media_type"] == "image/jpeg"


async def test_unsure_photo_model_adds_no_penalty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fake_llm: Callable[..., FakeClient]
) -> None:
    monkeypatch.setattr(settings, "media_dir", tmp_path)
    (tmp_path / "b.jpg").write_bytes(jpeg_bytes())
    (tmp_path / "a.jpg").write_bytes(jpeg_bytes(mark=2))
    pair: Any = (SimpleNamespace(path="b.jpg"), SimpleNamespace(path="a.jpg"))
    base = PhotoCheck(CheckResult("photos", "Фото до и после", "ok", "ок"), None, 0.9)
    fake_llm(
        _message(
            '{"same_equipment": false, "problem_fixed": "unclear", "tidy": true, '
            '"issues": [], "score_1_5": 3, "confidence": 0.4, "summary": "Темно, не видно."}'
        )
    )
    result = await compare_photos(base, pair, "Течь", "Замена")
    assert not result.check.critical and result.check.penalty == 0
    assert result.confidence == 0.4  # низкая уверенность → решение за мастером
