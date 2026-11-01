from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy import text

from src.api.app import create_app
from src.db.session import get_engine
from src.directory import careers_finder
from src.discovery import service
from src.search.provider import SearchHit

pytestmark = pytest.mark.seam
H = {"X-JobPilot": "1"}
WD = "https://acme.wd1.myworkdayjobs.com/en-US/Ext"


@pytest.fixture
async def client(monkeypatch: pytest.MonkeyPatch) -> AsyncIterator[httpx.AsyncClient]:
    ran: list[int] = []

    async def fake_run(run_id: int) -> None:  # the real run needs a browser, a model, the net
        ran.append(run_id)

    monkeypatch.setattr(service, "run_check", fake_run)
    with get_engine().begin() as conn:
        conn.execute(text("TRUNCATE companies RESTART IDENTITY CASCADE"))
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as c:
        yield c


async def test_unknown_company_is_404(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/checks/by-input", json={"company_name": "Nope"}, headers=H)
    assert r.status_code == 404 and r.json()["detail"] == "company_not_found"


async def test_company_without_link_is_422(client: httpx.AsyncClient) -> None:
    await client.post("/api/companies", json={"name": "Acme"}, headers=H)
    r = await client.post("/api/checks/by-input", json={"company_name": "Acme"}, headers=H)
    assert r.status_code == 422 and r.json()["detail"] == "no_sources"


async def test_link_needs_a_company_name_then_creates_it(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/checks/by-input", json={"url": WD}, headers=H)
    assert r.status_code == 422 and r.json()["detail"] == "company_name_required"
    r = await client.post("/api/checks/by-input", json={"url": WD, "company_name": "Acme"},
                          headers=H)
    assert r.status_code == 202 and r.json()["runs"][0]["company"] == "Acme"
    assert (await client.get("/api/companies")).json()[0]["sources"][0]["ats_type"] == "workday"


async def test_second_check_while_running_is_409(client: httpx.AsyncClient) -> None:
    body = {"url": WD, "company_name": "Acme"}
    assert (await client.post("/api/checks/by-input", json=body, headers=H)).status_code == 202
    r = await client.post("/api/checks/by-input", json=body, headers=H)
    assert r.status_code == 409 and r.json()["detail"]["code"] == "check_running"


async def test_unsafe_link_is_rejected(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/checks/by-input",
                          json={"url": "javascript:alert(1)", "company_name": "X"}, headers=H)
    assert r.status_code == 422 and r.json()["detail"] == "unsafe_url"


async def test_cancel_marks_a_running_check(client: httpx.AsyncClient) -> None:
    run = (await client.post("/api/checks/by-input", json={"url": WD, "company_name": "Acme"},
                             headers=H)).json()["runs"][0]
    got = (await client.post(f"/api/checks/{run['id']}/cancel", headers=H)).json()
    assert got["id"] == run["id"]
    assert (await client.get("/api/checks/active")).json()["runs"][0]["id"] == run["id"]
    assert (await client.get("/api/checks/9999")).status_code == 404


async def test_find_careers_reports_a_failed_search(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Broken:
        async def search(self, q: str, n: int) -> list[SearchHit]:
            raise RuntimeError("down")

    monkeypatch.setattr("src.search.provider.get_search_provider", lambda: Broken())
    r = await client.get("/api/companies/find-careers", params={"name": "Acme"})
    assert r.status_code == 502 and r.json()["detail"] == "search_failed"


async def test_find_careers_ranks_candidates_and_skips_job_boards(
    client: httpx.AsyncClient, monkeypatch: pytest.MonkeyPatch
) -> None:
    class Fake:
        async def search(self, q: str, n: int) -> list[SearchHit]:
            return [
                SearchHit("Acme on LinkedIn", "https://www.linkedin.com/company/acme/jobs", ""),
                SearchHit("Acme jobs", WD, ""),
                SearchHit("Acme", "https://acme.example/careers", ""),
            ]

    monkeypatch.setattr("src.search.provider.get_search_provider", lambda: Fake())
    r = await client.get("/api/companies/find-careers", params={"name": "Acme"})
    urls = [c["url"] for c in r.json()]
    assert urls[0] == WD and "linkedin" not in " ".join(urls)
    assert careers_finder.AGGREGATORS


async def test_companies_report_last_check_result_and_can_be_renamed(
    client: httpx.AsyncClient,
) -> None:
    co = (await client.post("/api/companies", json={"name": "baker huges", "url": WD},
                            headers=H)).json()
    assert co["sources"][0]["last_status"] == "never" and co["sources"][0]["last_check_at"] is None
    r = await client.patch(f"/api/companies/{co['id']}", json={"name": "Baker Hughes"}, headers=H)
    assert r.json()["name"] == "Baker Hughes"
    await client.post("/api/companies", json={"name": "Other Co"}, headers=H)
    clash = await client.patch(f"/api/companies/{co['id']}", json={"name": "other co"}, headers=H)
    assert clash.status_code == 409
