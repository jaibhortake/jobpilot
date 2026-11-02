from collections.abc import AsyncIterator

import httpx
import pytest
from sqlalchemy import text

from src.api.app import create_app
from src.db.session import get_engine

pytestmark = pytest.mark.seam
H = {"X-JobPilot": "1"}
POSTING = "https://boards.greenhouse.io/acme/jobs/4455667"


@pytest.fixture
async def client() -> AsyncIterator[httpx.AsyncClient]:
    with get_engine().begin() as conn:
        conn.execute(text("TRUNCATE companies, answers, applicant RESTART IDENTITY CASCADE"))
    transport = httpx.ASGITransport(app=create_app())
    async with httpx.AsyncClient(transport=transport, base_url="http://localhost") as c:
        yield c


async def test_applicant_defaults_and_unknown_keys_dropped(client: httpx.AsyncClient) -> None:
    first = (await client.get("/api/applicant")).json()
    assert first["disabled_sites"] == ["linkedin.com", "naukri.com"]
    body = {"details": {"email": " jai@x.com ", "shoe_size": "9"}, "disabled_sites": []}
    saved = (await client.put("/api/applicant", json=body, headers=H)).json()
    assert saved["details"] == {"email": "jai@x.com"}


async def test_fill_learn_and_mark_applied(client: httpx.AsyncClient) -> None:
    await client.put("/api/applicant", headers=H,
                     json={"details": {"email": "jai@x.com"}, "disabled_sites": []})
    await client.post("/api/answers", headers=H,
                      json=[{"question": "Willing to relocate?", "answer": "Yes"}])
    job = (await client.post("/api/jobs/manual", headers=H, json={
        "company_name": "Acme", "title": "ML Engineer", "url": POSTING})).json()
    fields = [
        {"id": "a", "label": "Email *"},
        {"id": "b", "label": "Willing to relocate?"},
        {"id": "c", "label": "Favourite colour"},
    ]
    r = (await client.post("/api/apply/fill", headers=H, json={
        "url": POSTING + "#app", "fields": fields, "draft": False})).json()
    assert r["job_id"] == job["id"]
    assert [(f["value"], f["confidence"]) for f in r["fields"]] == [
        ("jai@x.com", "high"), ("Yes", "high"), (None, "low")]

    await client.post("/api/answers", headers=H,
                      json=[{"question": "Favourite colour", "answer": "Blue"}])
    again = (await client.post("/api/apply/fill", headers=H, json={
        "url": POSTING, "fields": fields[2:], "draft": False})).json()
    assert again["fields"][0]["value"] == "Blue"

    marked = await client.post("/api/apply/mark-applied", headers=H, json={"url": POSTING})
    assert marked.status_code == 200 and marked.json()["status"] == "applied"
    unknown = await client.post("/api/apply/mark-applied", headers=H,
                                json={"url": "https://example.com/x"})
    assert unknown.status_code == 404


async def test_extension_origin_allowed_other_origins_not(client: httpx.AsyncClient) -> None:
    ext = "chrome-extension://" + "a" * 32
    ok = await client.get("/api/applicant", headers={"Origin": ext})
    bad = await client.get("/api/applicant", headers={"Origin": "https://evil.com"})
    assert ok.headers.get("access-control-allow-origin") == ext
    assert "access-control-allow-origin" not in bad.headers
