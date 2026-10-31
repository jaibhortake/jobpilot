import re
from typing import ClassVar

import httpx

from src.db.models import AtsType, CareerSource
from src.discovery.base import Cancel, FetchResult, JobPostingIn, SearchQuery
from src.discovery.http import request_with_retry

LINK = re.compile(r'href="([^"]*/jobs/(\d+)/[^"/]+/job[^"]*)"[^>]*>(.*?)</a>', re.S)


class IcimsReader:
    ats_type: ClassVar[AtsType] = AtsType.icims

    async def fetch(
        self, source: CareerSource, client: httpx.AsyncClient, query: SearchQuery, cancel: Cancel
    ) -> FetchResult:
        host = source.ats_config["host"]
        seen: dict[str, JobPostingIn] = {}
        for kw in query.keywords[:4]:
            for page in range(3):
                if await cancel():
                    return FetchResult(list(seen.values()), False, len(seen))
                r = await request_with_retry(
                    client, "GET", f"https://{host}/jobs/search",
                    params={"ss": 1, "searchKeyword": kw, "in_iframe": 1, "pr": page},
                )
                hits = LINK.findall(r.text)
                for href, jid, inner in hits:
                    title = re.sub(r"<[^>]+>|\s+", " ", inner).strip()
                    if title:
                        url = href if href.startswith("http") else f"https://{host}{href}"
                        seen.setdefault(jid, JobPostingIn(jid, title, url))
                if not hits:
                    break
        return FetchResult(list(seen.values()), False, len(seen))
