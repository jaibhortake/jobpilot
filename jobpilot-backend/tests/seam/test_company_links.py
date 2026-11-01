from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy import text

from src.api.app import create_app
from src.db.session import get_engine

pytestmark = pytest.mark.seam
H = {"X-JobPilot": "1"}


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    with get_engine().begin() as conn:
        conn.execute(text("TRUNCATE companies RESTART IDENTITY CASCADE"))
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as c:
        yield c


async def test_new_company_with_careers_link(client: httpx.AsyncClient) -> None:
    url = "https://acme.wd1.myworkdayjobs.com/en-US/Ext"
    r = await client.post("/api/companies", json={"name": "Acme", "url": url}, headers=H)
    assert r.status_code == 201
    assert r.json()["sources"][0]["url"] == url
    assert r.json()["sources"][0]["ats_type"] == "workday"


async def test_bad_link_does_not_leave_a_company_behind(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/companies", json={"name": "Acme", "url": "ftp://x"}, headers=H)
    assert r.status_code == 422
    assert (await client.get("/api/companies")).json() == []


async def test_check_by_partial_name_without_link_reports_no_sources(
    client: httpx.AsyncClient,
) -> None:
    await client.post("/api/companies", json={"name": "Rockwell Automation"}, headers=H)
    r = await client.post("/api/checks/by-input", json={"company_name": "rockwell"}, headers=H)
    assert r.status_code == 422 and r.json()["detail"] == "no_sources"
    await client.post("/api/companies", json={"name": "Rockwell Tools"}, headers=H)
    r = await client.post("/api/checks/by-input", json={"company_name": "rockwell"}, headers=H)
    assert r.status_code == 404  # ambiguous: don't guess


async def test_move_domain_out_of_other(client: httpx.AsyncClient) -> None:
    await client.post(
        "/api/contacts/bulk", json={"text": "a@wipro.com, b@wipro.com, c@other.org"}, headers=H
    )
    r = await client.post(
        "/api/contacts/move-domain", json={"domain": "wipro.com", "company_name": "Wipro"},
        headers=H,
    )
    assert r.json() == {"moved": 2}
    by_email = {c["email"]: c["company"] for c in (await client.get("/api/contacts")).json()}
    assert by_email == {"a@wipro.com": "Wipro", "b@wipro.com": "Wipro", "c@other.org": "Other"}
    # later pastes from that domain now land under the company
    await client.post("/api/contacts/bulk", json={"text": "d@wipro.com"}, headers=H)
    by_email = {c["email"]: c["company"] for c in (await client.get("/api/contacts")).json()}
    assert by_email["d@wipro.com"] == "Wipro"
