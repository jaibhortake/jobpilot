from datetime import UTC, datetime, timedelta
from typing import Any, ClassVar

import httpx

from src.db.models import AtsType, CareerSource
from src.discovery.base import Cancel, FetchResult, JobPostingIn, SearchQuery
from src.discovery.dates import parse_posted
from src.discovery.http import request_with_retry

PAGE = 20
MAX_PAGES = 10


class WorkdayReader:
    ats_type: ClassVar[AtsType] = AtsType.workday

    async def fetch(
        self, source: CareerSource, client: httpx.AsyncClient, query: SearchQuery, cancel: Cancel
    ) -> FetchResult:
        cfg = source.ats_config
        host = f"{cfg['tenant']}.{cfg['wd']}.myworkdayjobs.com"
        api = f"https://{host}/wday/cxs/{cfg['tenant']}/{cfg['site']}/jobs"
        now = datetime.now(UTC)
        floor = now - timedelta(days=query.max_age_days)
        if query.since and query.since > floor:
            floor = query.since

        ids = cfg.get("country_ids")
        if ids is None:
            r = await request_with_retry(
                client, "POST", api,
                json={"appliedFacets": {}, "limit": 1, "offset": 0, "searchText": ""},
            )
            ids = _country_ids(r.json(), query.locations)
            cfg["country_ids"] = ids

        seen: dict[str, JobPostingIn] = {}
        found_raw = 0
        complete = True
        for kw in query.keywords:
            for page in range(MAX_PAGES):
                if await cancel():
                    return FetchResult(list(seen.values()), False, found_raw)
                body: dict[str, Any] = {
                    "limit": PAGE, "offset": page * PAGE, "searchText": kw,
                    "appliedFacets": {"locationCountry": ids} if ids else {},
                }
                data = (await request_with_retry(client, "POST", api, json=body)).json()
                items = data.get("jobPostings", [])
                found_raw += len(items)
                dates = []
                for it in items:
                    ext = it.get("externalPath", "")
                    posted = parse_posted(it.get("postedOn"), now)
                    dates.append(posted)
                    loc = it.get("locationsText")
                    bullets = it.get("bulletFields") or []
                    seen.setdefault(ext, JobPostingIn(
                        external_id=bullets[0] if bullets else ext.rsplit("/", 1)[-1],
                        title=it.get("title", ""),
                        url=f"https://{host}/en-US/{cfg['site']}{ext}",
                        location=loc,
                        remote=bool(loc and "remote" in loc.lower()),
                        posted_at=posted,
                        posted_text=it.get("postedOn"),
                    ))
                known = [d for d in dates if d]
                if (page + 1) * PAGE >= data.get("total", 0) or not items:
                    break
                if known and min(known) < floor:
                    # stopped at the age cutoff, so older jobs went unseen: not a full crawl
                    complete = False
                    break
                if page == MAX_PAGES - 1:
                    complete = False
        return FetchResult(list(seen.values()), complete, found_raw)


def _country_ids(facets: dict[str, Any], locations: list[str]) -> list[str]:
    wanted = {w.lower() for w in locations}
    out: list[str] = []

    def walk(nodes: list[dict[str, Any]]) -> None:
        for n in nodes:
            if "values" in n:
                walk(n["values"])
            elif str(n.get("descriptor", "")).lower() in wanted and "id" in n:
                out.append(str(n["id"]))

    for f in facets.get("facets", []):
        if f.get("facetParameter") == "locationCountry":
            walk(f.get("values", []))
    return out
