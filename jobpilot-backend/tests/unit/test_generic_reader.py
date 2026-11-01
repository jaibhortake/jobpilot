"""The generic (AI) reader and the Ashby reader, with the browser, model and network faked."""

import json
from typing import Any

import httpx
import pytest

from src.db.models import AtsType, CareerSource
from src.discovery import service
from src.discovery.base import FetchResult, JobPostingIn, SearchQuery
from src.discovery.browser import Link, RenderedPage
from src.discovery.readers import generic
from src.discovery.readers.ashby import AshbyReader
from src.discovery.readers.generic import ExtractedJob, GenericNotice, GenericReader, PageJobs
from src.llm.errors import RateLimited

QUERY = SearchQuery(keywords=["engineer"], locations=["India"])
LANDING = "https://x.com/careers"
RESULTS = "https://x.com/careers/jobs/results"
JOB = "https://x.com/careers/jobs/1"


async def _no_cancel() -> bool:
    return False


def _source(config: dict[str, Any] | None = None) -> CareerSource:
    return CareerSource(ats_type=AtsType.generic, ats_config=config or {}, url=LANDING)


def _pages(monkeypatch: pytest.MonkeyPatch, pages: dict[str, RenderedPage],
           answers: list[PageJobs | Exception]) -> list[str]:
    opened: list[str] = []

    async def render(url: str) -> RenderedPage:
        opened.append(url)
        return pages[url]

    async def complete(*_a: Any, **_k: Any) -> PageJobs:
        answer = answers.pop(0)
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(generic, "render_page", render)
    monkeypatch.setattr(generic.router, "complete", complete)
    monkeypatch.setattr(generic.router, "input_budget", lambda _t: 4000)
    return opened


def _page(url: str, *links: tuple[str, str]) -> RenderedPage:
    return RenderedPage(url, "t", "text", [Link(t, h) for t, h in links])


async def test_listing_page_returns_only_jobs_whose_link_is_on_the_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _pages(
        monkeypatch, {LANDING: _page(LANDING, ("Job 1", JOB))},
        [PageJobs(page_kind="listing", jobs=[
            ExtractedJob(title="Engineer", url=JOB, location="Pune"),
            ExtractedJob(title="Invented", url="https://x.com/made-up"),
        ])],
    )
    async with httpx.AsyncClient() as client:
        res = await GenericReader().fetch(_source(), client, QUERY, _no_cancel)
    assert [p.title for p in res.postings] == ["Engineer"]
    assert res.found_raw == 2 and not res.complete


async def test_landing_page_follows_the_job_search_link_and_remembers_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened = _pages(
        monkeypatch,
        {LANDING: _page(LANDING, ("Search jobs", RESULTS)),
         RESULTS: _page(RESULTS, ("Job 1", JOB))},
        [PageJobs(page_kind="landing", suggested_listing_url=RESULTS),
         PageJobs(page_kind="listing", jobs=[ExtractedJob(title="Engineer", url=JOB)])],
    )
    source = _source()
    async with httpx.AsyncClient() as client:
        res = await GenericReader().fetch(source, client, QUERY, _no_cancel)
    assert opened == [LANDING, RESULTS] and len(res.postings) == 1
    assert source.ats_config["listing_url"] == RESULTS


async def test_next_check_goes_straight_to_the_remembered_page(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    opened = _pages(
        monkeypatch, {RESULTS: _page(RESULTS, ("Job 1", JOB))},
        [PageJobs(page_kind="listing", jobs=[ExtractedJob(title="Engineer", url=JOB)])],
    )
    async with httpx.AsyncClient() as client:
        await GenericReader().fetch(_source({"listing_url": RESULTS}), client, QUERY, _no_cancel)
    assert opened == [RESULTS]


async def test_landing_with_nowhere_to_go_raises_the_paste_a_link_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _pages(monkeypatch, {LANDING: _page(LANDING, ("About", "https://x.com/about"))},
           [PageJobs(page_kind="landing")])
    async with httpx.AsyncClient() as client:
        with pytest.raises(GenericNotice) as err:
            await GenericReader().fetch(_source(), client, QUERY, _no_cancel)
    assert err.value.status == "no_listings"


async def test_login_wall_is_reported_as_blocked(monkeypatch: pytest.MonkeyPatch) -> None:
    _pages(monkeypatch, {LANDING: _page(LANDING)}, [PageJobs(page_kind="blocked")])
    async with httpx.AsyncClient() as client:
        with pytest.raises(GenericNotice) as err:
            await GenericReader().fetch(_source(), client, QUERY, _no_cancel)
    assert err.value.status == "blocked"


async def test_rate_limit_becomes_a_skip_notice(monkeypatch: pytest.MonkeyPatch) -> None:
    _pages(monkeypatch, {LANDING: _page(LANDING)}, [RateLimited()])
    async with httpx.AsyncClient() as client:
        with pytest.raises(GenericNotice) as err:
            await GenericReader().fetch(_source(), client, QUERY, _no_cancel)
    assert err.value.status == "skipped"


async def test_ashby_keeps_only_matching_titles() -> None:
    body = {"jobs": [
        {"id": "1", "title": "Software Engineer", "jobUrl": "https://a/1", "location": "Pune"},
        {"id": "2", "title": "Chef", "jobUrl": "https://a/2", "location": "Pune"},
    ]}
    client = httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _r: httpx.Response(200, text=json.dumps(body)))
    )
    source = CareerSource(ats_type=AtsType.ashby, ats_config={"org": "acme"}, url="https://x")
    async with client:
        res = await AshbyReader().fetch(source, client, QUERY, _no_cancel)
    assert [p.title for p in res.postings] == ["Software Engineer"] and res.found_raw == 2


def test_postings_without_a_location_survive_the_location_filter() -> None:
    postings = [
        JobPostingIn("a", "Engineer", "https://x/a", location=None),
        JobPostingIn("b", "Engineer", "https://x/b", location="Berlin, Germany"),
        JobPostingIn("c", "Engineer", "https://x/c", location="Pune"),
    ]
    q = service.default_query(None)
    kept = [p.external_id for p in postings
            if service.match_location(p.location, p.country, q.locations).ok]
    assert kept == ["a", "c"]
    assert service.dedupe(postings + postings) == postings
    assert isinstance(FetchResult(), FetchResult)
