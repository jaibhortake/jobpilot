from typing import ClassVar

import httpx

from src.db.models import AtsType, CareerSource
from src.discovery.base import Cancel, FetchResult, JobPostingIn, SearchQuery
from src.discovery.dates import parse_posted
from src.discovery.http import request_with_retry
from src.discovery.readers.greenhouse import title_matches


class LeverReader:
    ats_type: ClassVar[AtsType] = AtsType.lever

    async def fetch(
        self, source: CareerSource, client: httpx.AsyncClient, query: SearchQuery, cancel: Cancel
    ) -> FetchResult:
        url = f"https://api.lever.co/v0/postings/{source.ats_config['company']}"
        raw = (await request_with_retry(client, "GET", url, params={"mode": "json"})).json()
        out = [
            JobPostingIn(
                external_id=j["id"], title=j["text"], url=j.get("hostedUrl"),
                location=(j.get("categories") or {}).get("location"),
                country=j.get("country"),
                remote=j.get("workplaceType") == "remote",
                posted_at=parse_posted(j.get("createdAt")),
                description=j.get("descriptionPlain"),
            )
            for j in raw if title_matches(j["text"], query.keywords)
        ]
        return FetchResult(out, True, len(raw))
