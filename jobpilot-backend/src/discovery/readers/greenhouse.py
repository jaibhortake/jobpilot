import html
import re
from typing import ClassVar

import httpx

from src.db.models import AtsType, CareerSource
from src.discovery.base import Cancel, FetchResult, JobPostingIn, SearchQuery
from src.discovery.dates import parse_posted
from src.discovery.http import request_with_retry


def strip_html(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(s))).strip()


def title_matches(title: str, keywords: list[str]) -> bool:
    toks = set(re.findall(r"[a-z0-9+#.]+", title.lower()))
    return any(set(k.lower().split()) <= toks for k in keywords)


class GreenhouseReader:
    ats_type: ClassVar[AtsType] = AtsType.greenhouse

    async def fetch(
        self, source: CareerSource, client: httpx.AsyncClient, query: SearchQuery, cancel: Cancel
    ) -> FetchResult:
        url = f"https://boards-api.greenhouse.io/v1/boards/{source.ats_config['board']}/jobs"
        jobs = (await request_with_retry(client, "GET", url, params={"content": "true"})).json()
        raw = jobs.get("jobs", [])
        out = [
            JobPostingIn(
                external_id=str(j["id"]), title=j["title"], url=j.get("absolute_url"),
                location=(j.get("location") or {}).get("name"),
                posted_at=parse_posted(j.get("updated_at")),
                description=strip_html(j["content"]) if j.get("content") else None,
            )
            for j in raw if title_matches(j["title"], query.keywords)
        ]
        return FetchResult(out, True, len(raw))
