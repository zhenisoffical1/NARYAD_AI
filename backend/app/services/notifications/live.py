"""Живые события для WebSocket.

Изменения складываются в «исходящие» сессии БД и рассылаются только после успешного
commit — клиент никогда не увидит событие об изменении, которое откатилось.
"""

import json
from dataclasses import dataclass, field
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.enums import Role

STAFF_ROLES = frozenset({Role.MASTER, Role.BOSS, Role.ADMIN})

_OUTBOX_KEY = "live_events_outbox"


@dataclass(frozen=True, slots=True)
class LiveEvent:
    """Событие {type, payload}. Получатели — роли целиком и/или конкретные сотрудники."""

    type: str
    payload: dict[str, Any]
    roles: frozenset[Role] = field(default_factory=frozenset)
    user_ids: frozenset[int] = field(default_factory=frozenset)

    def is_for(self, user_id: int, role: Role) -> bool:
        return role in self.roles or user_id in self.user_ids

    def wire(self) -> dict[str, Any]:
        return {"type": self.type, "payload": self.payload}

    def to_json(self) -> str:
        return json.dumps(
            {
                "type": self.type,
                "payload": self.payload,
                "roles": sorted(self.roles),
                "user_ids": sorted(self.user_ids),
            },
            ensure_ascii=False,
            default=str,
        )

    @classmethod
    def from_json(cls, raw: str) -> "LiveEvent":
        data = json.loads(raw)
        return cls(
            type=data["type"],
            payload=data["payload"],
            roles=frozenset(Role(r) for r in data.get("roles", [])),
            user_ids=frozenset(data.get("user_ids", [])),
        )


def queue_event(session: AsyncSession, event: LiveEvent) -> None:
    session.info.setdefault(_OUTBOX_KEY, []).append(event)


def pending_events(session: AsyncSession) -> list[LiveEvent]:
    return list(session.info.get(_OUTBOX_KEY, []))


async def commit_and_publish(session: AsyncSession) -> None:
    from app.services.notifications.bus import bus

    events: list[LiveEvent] = session.info.pop(_OUTBOX_KEY, [])
    try:
        await session.commit()
    except Exception:
        session.info.pop(_OUTBOX_KEY, None)
        raise
    for event in events:
        await bus.publish(event)
