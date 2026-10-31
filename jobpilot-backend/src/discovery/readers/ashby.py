from typing import ClassVar

import httpx

from src.db.models import AtsType, CareerSource
from src.discovery.base import Cancel, FetchResult, JobPostingIn, SearchQuery
from src.discovery.dates import parse_posted
from src.discovery.http import request_with_retry
from src.discovery.readers.greenhouse import title_matches


class AshbyReader:
    ats_type: ClassVar[AtsType] = AtsType.ashby

    async def fetch(
        self, source: CareerSource, client: httpx.AsyncClient, query: SearchQuery, cancel: Cancel
    ) -> FetchResult:
        url = f"https://api.ashbyhq.com/posting-api/job-board/{source.ats_config['org']}"
        raw = (await request_with_retry(client, "GET", url)).json().get("jobs", [])
        out = [
            JobPostingIn(
                external_id=j["id"], title=j["title"], url=j.get("jobUrl"),
                location=j.get("location"),
                country=((j.get("address") or {}).get("postalAddress") or {}).get("addressCountry"),
                remote=bool(j.get("isRemote")),
                posted_at=parse_posted(j.get("publishedAt")),
                description=j.get("descriptionPlain"),
            )
            for j in raw if title_matches(j["title"], query.keywords)
        ]
        return FetchResult(out, True, len(raw))
