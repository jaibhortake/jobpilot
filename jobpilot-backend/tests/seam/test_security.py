import httpx
import pytest

from src.api.app import create_app

pytestmark = pytest.mark.seam


def _client(host: str = "127.0.0.1") -> httpx.AsyncClient:
    app = create_app(testing=True)
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url=f"http://{host}")


async def test_mutation_without_header_403() -> None:
    async with _client() as client:
        denied = await client.post("/api/health-echo", json={"x": 1})
        allowed = await client.post(
            "/api/health-echo", json={"x": 1}, headers={"X-JobPilot": "1"}
        )
    assert denied.status_code == 403
    assert denied.json() == {"detail": "missing_client_header"}
    assert allowed.status_code == 200
    assert allowed.json() == {"x": 1}


async def test_untrusted_host_400() -> None:
    async with _client("evil.com") as client:
        res = await client.get("/api/health")
    assert res.status_code == 400


async def test_testing_router_absent_by_default() -> None:
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        res = await client.post("/api/health-echo", json={}, headers={"X-JobPilot": "1"})
    assert res.status_code == 404
