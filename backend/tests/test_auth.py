from fastapi import APIRouter, Depends
from httpx import AsyncClient

from app.deps import require_role
from app.main import app
from app.models import Employee
from app.models.enums import Role
from tests.conftest import auth_header

# Тестовый маршрут, закрытый ролью мастера — проверяем require_role изолированно
_probe = APIRouter()


@_probe.get("/api/_test/master-only")
async def master_only(user: Employee = Depends(require_role(Role.MASTER))) -> dict[str, int]:
    return {"id": user.id}


app.include_router(_probe)


async def test_login_success_returns_token_and_user(client: AsyncClient, make_employee) -> None:
    await make_employee(
        Role.WORKER, pin="4821", login="akhmetov", full_name="Ахметов Ерлан Каиртаевич"
    )

    resp = await client.post("/api/auth/login", json={"login": "Akhmetov ", "pin": "4821"})

    assert resp.status_code == 200
    body = resp.json()
    assert body["user"]["role"] == "worker"
    assert body["user"]["short_name"] == "Ахметов Е."
    me = await client.get(
        "/api/auth/me", headers={"Authorization": f"Bearer {body['access_token']}"}
    )
    assert me.status_code == 200
    assert me.json()["login"] == "akhmetov"


async def test_login_wrong_pin(client: AsyncClient, make_employee) -> None:
    await make_employee(Role.WORKER, pin="4821", login="akhmetov")
    resp = await client.post("/api/auth/login", json={"login": "akhmetov", "pin": "0000"})
    assert resp.status_code == 401
    assert "Неверный логин или ПИН" in resp.json()["detail"]


async def test_login_pin_format_message_in_russian(client: AsyncClient) -> None:
    resp = await client.post("/api/auth/login", json={"login": "x", "pin": "12a"})
    assert resp.status_code == 422
    assert "ПИН — ровно 4 цифры" in resp.json()["detail"]


async def test_login_locked_after_too_many_attempts(client: AsyncClient, make_employee) -> None:
    await make_employee(Role.WORKER, pin="4821", login="akhmetov")
    for _ in range(5):
        await client.post("/api/auth/login", json={"login": "akhmetov", "pin": "0000"})

    resp = await client.post("/api/auth/login", json={"login": "akhmetov", "pin": "4821"})
    assert resp.status_code == 429
    assert "Слишком много" in resp.json()["detail"]


async def test_me_requires_token(client: AsyncClient) -> None:
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401


async def test_me_rejects_garbage_token(client: AsyncClient) -> None:
    resp = await client.get("/api/auth/me", headers={"Authorization": "Bearer nope"})
    assert resp.status_code == 401
    assert "Войдите заново" in resp.json()["detail"]


async def test_require_role_allows_master(client: AsyncClient, make_employee) -> None:
    master = await make_employee(Role.MASTER)
    resp = await client.get("/api/_test/master-only", headers=auth_header(master))
    assert resp.status_code == 200


async def test_require_role_blocks_worker(client: AsyncClient, make_employee) -> None:
    worker = await make_employee(Role.WORKER)
    resp = await client.get("/api/_test/master-only", headers=auth_header(worker))
    assert resp.status_code == 403
    assert resp.json()["detail"] == "Этот раздел недоступен для вашей роли."


async def test_inactive_user_rejected(client: AsyncClient, make_employee) -> None:
    master = await make_employee(Role.MASTER, is_active=False)
    resp = await client.get("/api/auth/me", headers=auth_header(master))
    assert resp.status_code == 401
