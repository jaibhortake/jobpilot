import re
from dataclasses import dataclass
from urllib.parse import urlsplit

from src.common.urls import UnsafeUrl, safe_http_url
from src.db.models import AtsType
from src.directory.ats_detect import detect
from src.search.provider import SearchProvider

AGGREGATORS = (
    "linkedin.com", "indeed.com", "naukri.com", "glassdoor.com", "foundit.in", "monster.com",
    "instahyre.com", "wellfound.com",
)


class SearchFailed(Exception):
    pass


@dataclass
class Candidate:
    url: str
    title: str
    ats_type: str
    score: int


def _tokens(name: str) -> list[str]:
    return [t for t in re.findall(r"[a-z0-9]+", name.lower()) if len(t) > 2]


async def find_careers_pages(name: str, provider: SearchProvider) -> list[Candidate]:
    hits = []
    failure: Exception | None = None
    for q in (f"{name} careers jobs", f"{name} careers India"):
        try:
            hits += await provider.search(q, 8)
        except Exception as exc:  # one query failing is fine; both failing is reported
            failure = exc
    if failure and not hits:
        raise SearchFailed(str(failure)) from failure
    toks = _tokens(name)
    best: dict[str, Candidate] = {}
    for h in hits:
        try:
            url = safe_http_url(h.url)
        except UnsafeUrl:
            continue
        parts = urlsplit(url)
        host = (parts.hostname or "").lower()
        if any(host.endswith(a) for a in AGGREGATORS):
            continue
        ats, _ = detect(url)
        score = 0
        if ats != AtsType.generic:
            score += 3
        if any(t in host or t in parts.path.lower() for t in toks):
            score += 2
        if re.search(r"career|jobs", parts.path.lower()):
            score += 1
        key = host + parts.path.rstrip("/")
        if key not in best or best[key].score < score:
            best[key] = Candidate(url, h.title, ats.value, score)
    return sorted(best.values(), key=lambda c: -c.score)[:5]
