from httpx import AsyncClient


async def test_health_reports_db_and_mock_llm(client: AsyncClient) -> None:
    resp = await client.get("/api/health")
    assert resp.status_code == 200
    assert resp.json() == {
        "status": "ok",
        "db": "ok",
        "llm": "mock",
        "telegram": "off",
        "demo_mode": False,
    }


async def test_openapi_available(client: AsyncClient) -> None:
    resp = await client.get("/api/openapi.json")
    assert resp.status_code == 200
    assert resp.json()["info"]["title"] == "НарядAI API"
