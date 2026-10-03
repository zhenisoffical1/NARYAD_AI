import pytest
from starlette.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

from app.main import app
from app.models.enums import Role
from app.security import create_access_token
from app.services.notifications.live import STAFF_ROLES, LiveEvent
from app.ws import manager


def _connect(client: TestClient, user_id: int, role: Role):  # type: ignore[no-untyped-def]
    return client.websocket_connect(f"/ws?token={create_access_token(user_id, role)}")


def test_ws_rejects_without_valid_token() -> None:
    with TestClient(app) as client, pytest.raises(WebSocketDisconnect):  # noqa: SIM117
        with client.websocket_connect("/ws?token=bad") as ws:
            ws.receive_json()


def test_ws_hello_and_ping() -> None:
    with TestClient(app) as client, _connect(client, 1, Role.MASTER) as ws:
        assert ws.receive_json() == {"type": "hello", "payload": {"role": "master"}}
        ws.send_text("ping")
        assert ws.receive_text() == "pong"


def test_ws_routes_events_by_role_and_user() -> None:
    staff_event = LiveEvent("order.created", {"order_id": 1}, roles=STAFF_ROLES)
    personal_event = LiveEvent("order.status_changed", {"order_id": 2}, user_ids=frozenset({7}))

    with (
        TestClient(app) as client,
        _connect(client, 1, Role.MASTER) as master_ws,
        _connect(client, 7, Role.WORKER) as worker_ws,
    ):
        master_ws.receive_json()
        worker_ws.receive_json()

        client.portal.call(manager.deliver, staff_event)  # type: ignore[union-attr]
        client.portal.call(manager.deliver, personal_event)  # type: ignore[union-attr]

        # Мастер видит общее событие; адресное событие исполнителю ему не приходит,
        # поэтому следующим он получит ответ на ping, а не чужое событие.
        assert master_ws.receive_json()["type"] == "order.created"
        master_ws.send_text("ping")
        assert master_ws.receive_text() == "pong"

        # Исполнитель не получает событие для мастеров — первым приходит его личное
        assert worker_ws.receive_json() == {
            "type": "order.status_changed",
            "payload": {"order_id": 2},
        }


def test_live_event_json_roundtrip() -> None:
    event = LiveEvent("x", {"a": "б"}, roles=frozenset({Role.BOSS}), user_ids=frozenset({3}))
    assert LiveEvent.from_json(event.to_json()) == event
