import io
from collections.abc import AsyncIterator

import httpx
import pytest
from openpyxl import Workbook
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


async def test_contacts_add_list_delete(client: httpx.AsyncClient) -> None:
    co = (await client.post("/api/companies", json={"name": "Acme"}, headers=H)).json()
    r = await client.post(
        "/api/contacts", json={"company_id": co["id"], "email": "HR@Acme.com"}, headers=H
    )
    assert r.status_code == 201 and r.json()["email"] == "hr@acme.com"
    dup = await client.post(
        "/api/contacts", json={"company_id": co["id"], "email": "hr@acme.com"}, headers=H
    )
    assert dup.status_code == 409
    assert len((await client.get("/api/contacts")).json()) == 1
    assert (await client.delete(f"/api/contacts/{r.json()['id']}", headers=H)).status_code == 204
    assert (await client.get("/api/contacts")).json() == []


async def test_import_sheet_creates_companies_sources_contacts(client: httpx.AsyncClient) -> None:
    wb = Workbook()
    ws = wb.active
    assert ws is not None
    ws.append(["Company", "Website", "Hr contacts"])
    ws.append(["Acme", "https://jobs.ashbyhq.com/acme", "hr@acme.com, jobs@acme.com"])
    ws.append(["Blank", None, None])
    buf = io.BytesIO()
    wb.save(buf)
    files = {"file": ("s.xlsx", buf.getvalue())}
    r = await client.post("/api/directory/import", files=files, headers=H)
    assert r.json()["companies_created"] == 2
    assert r.json()["contacts_created"] == 2
    again = await client.post("/api/directory/import", files=files, headers=H)
    assert again.json()["companies_created"] == 0
    assert again.json()["contacts_created"] == 0
