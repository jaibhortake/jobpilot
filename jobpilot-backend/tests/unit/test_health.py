import httpx

from src.api.app import create_app
from src.api.deps import db_ok


def _client(app_db_ok: bool) -> httpx.AsyncClient:
    app = create_app()

    async def _override() -> bool:
        return app_db_ok

    app.dependency_overrides[db_ok] = _override
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1")


async def test_health_ok() -> None:
    async with _client(True) as client:
        res = await client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "db": True}


async def test_health_db_down() -> None:
    async with _client(False) as client:
        res = await client.get("/api/health")
    assert res.status_code == 200
    assert res.json() == {"status": "ok", "db": False}
