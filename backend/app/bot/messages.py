"""Что и с какими кнопками отправить в Telegram — без зависимости от aiogram (тестируется)."""

from dataclasses import dataclass
from html import escape

from app.config import settings
from app.models import Employee, Notification
from app.models.enums import Role
from app.services.state_machine import ACTION_LABELS, Action

# Наряд пришёл исполнителю — отвечает прямо из сообщения
WORKER_ACTION_KINDS = frozenset({"order_new", "order_alarm"})


@dataclass(frozen=True, slots=True)
class Button:
    text: str
    callback: str | None = None
    url: str | None = None


@dataclass(frozen=True, slots=True)
class OutMessage:
    text: str
    rows: list[list[Button]]


def callback_action(order_id: int, action: Action) -> str:
    return f"o:{order_id}:{action.value}"


def callback_reassign(order_id: int, employee_id: int) -> str:
    return f"r:{order_id}:{employee_id}"


def order_url(order_id: int, role: Role) -> str | None:
    """Ссылка «Открыть наряд». Telegram не принимает адреса localhost — тогда без кнопки."""
    base = settings.public_url.rstrip("/")
    if not base.startswith("https://"):
        return None
    prefix = "/w/orders" if role == Role.WORKER else "/m/orders"
    return f"{base}{prefix}/{order_id}"


def render(note: Notification, employee: Employee) -> OutMessage:
    text = f"<b>{escape(note.title)}</b>\n{escape(note.body)}"
    rows: list[list[Button]] = []
    if note.order_id is not None:
        if note.kind in WORKER_ACTION_KINDS and employee.role == Role.WORKER:
            rows.append(
                [
                    Button(ACTION_LABELS[a], callback_action(note.order_id, a))
                    for a in (Action.ACCEPT, Action.QUEUE)
                ]
            )
        data = note.data or {}
        if note.kind == "order_escalation" and "reassign_to" in data:
            rows.append(
                [
                    Button(
                        f"Переназначить: {data['reassign_name']}",
                        callback_reassign(note.order_id, int(data["reassign_to"])),
                    )
                ]
            )
        if url := order_url(note.order_id, employee.role):
            rows.append([Button("Открыть наряд", url=url)])
    return OutMessage(text=text, rows=rows)
