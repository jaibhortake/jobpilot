from typing import Any, ClassVar

import httpx

from src.db.models import AtsType, CareerSource
from src.discovery.base import Cancel, FetchResult, JobPostingIn, SearchQuery
from src.discovery.dates import parse_posted
from src.discovery.http import SourceFetchError, request_with_retry

PAGE = 25
MAX_PAGES = 8


class OracleReader:
    ats_type: ClassVar[AtsType] = AtsType.oracle

    async def _site_number(self, source: CareerSource, client: httpx.AsyncClient) -> str:
        cfg = source.ats_config
        if cfg.get("site_number"):
            return str(cfg["site_number"])
        site = cfg["site"]
        if site.startswith("CX_"):
            return str(site)
        base = f"https://{cfg['host']}/hcmRestApi/resources/latest/recruitingCESites"
        try:
            r = await request_with_retry(
                client, "GET", base, params={"onlyData": "true", "q": f"SiteURLName={site}"}
            )
            items = r.json().get("items", [])
            number = items[0]["SiteNumber"] if items else site
        except (SourceFetchError, KeyError):
            number = site
        cfg["site_number"] = number
        return str(number)

    async def fetch(
        self, source: CareerSource, client: httpx.AsyncClient, query: SearchQuery, cancel: Cancel
    ) -> FetchResult:
        cfg = source.ats_config
        host, site = cfg["host"], cfg["site"]
        number = await self._site_number(source, client)
        api = f"https://{host}/hcmRestApi/resources/latest/recruitingCEJobRequisitions"
        seen: dict[str, JobPostingIn] = {}
        raw_n = 0
        complete = True
        for kw in query.keywords:
            for page in range(MAX_PAGES):
                if await cancel():
                    return FetchResult(list(seen.values()), False, raw_n)
                finder = (
                    f"findReqs;siteNumber={number},facetsList=NONE,limit={PAGE},"
                    f"offset={page * PAGE},keyword={kw},sortBy=POSTING_DATES_DESC"
                )
                data: dict[str, Any] = (await request_with_retry(
                    client, "GET", api, params={"onlyData": "true", "finder": finder}
                )).json()
                head = (data.get("items") or [{}])[0]
                reqs = head.get("requisitionList", [])
                raw_n += len(reqs)
                for j in reqs:
                    seen.setdefault(str(j["Id"]), JobPostingIn(
                        external_id=str(j["Id"]), title=j["Title"],
                        url=f"https://{host}/hcmUI/CandidateExperience/en/sites/{site}/job/{j['Id']}",
                        location=j.get("PrimaryLocation"), country=j.get("PrimaryLocationCountry"),
                        posted_at=parse_posted(j.get("PostedDate")),
                    ))
                if (page + 1) * PAGE >= head.get("TotalJobsCount", 0) or not reqs:
                    break
                if page == MAX_PAGES - 1:
                    complete = False
        return FetchResult(list(seen.values()), complete, raw_n)
