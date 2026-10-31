from typing import ClassVar

import httpx

from src.db.models import AtsType, CareerSource
from src.discovery.base import Cancel, FetchResult, JobPostingIn, SearchQuery
from src.discovery.dates import parse_posted
from src.discovery.http import request_with_retry

MAX_PAGES = 5


class SmartRecruitersReader:
    ats_type: ClassVar[AtsType] = AtsType.smartrecruiters

    async def fetch(
        self, source: CareerSource, client: httpx.AsyncClient, query: SearchQuery, cancel: Cancel
    ) -> FetchResult:
        company = source.ats_config["company"]
        url = f"https://api.smartrecruiters.com/v1/companies/{company}/postings"
        seen: dict[str, JobPostingIn] = {}
        raw_n = 0
        complete = True
        for kw in query.keywords:
            for page in range(MAX_PAGES):
                if await cancel():
                    return FetchResult(list(seen.values()), False, raw_n)
                data = (await request_with_retry(
                    client, "GET", url,
                    params={"limit": 100, "offset": page * 100, "q": kw, "country": "in"},
                )).json()
                items = data.get("content", [])
                raw_n += len(items)
                for j in items:
                    loc = j.get("location") or {}
                    place = ", ".join(x for x in (loc.get("city"), loc.get("region")) if x)
                    seen.setdefault(j["id"], JobPostingIn(
                        external_id=j["id"], title=j["name"],
                        url=f"https://jobs.smartrecruiters.com/{company}/{j['id']}",
                        location=place or None, country=loc.get("country"),
                        remote=bool(loc.get("remote")),
                        posted_at=parse_posted(j.get("releasedDate")),
                    ))
                if (page + 1) * 100 >= data.get("totalFound", 0) or not items:
                    break
                if page == MAX_PAGES - 1:
                    complete = False
        return FetchResult(list(seen.values()), complete, raw_n)
