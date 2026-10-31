import re
from urllib.parse import urlsplit

from src.db.models import AtsType

_LOCALE = re.compile(r"^[a-z]{2}-[A-Z]{2}$")
_WD_SKIP = {"job", "login", "userHome", "details"}
_ORACLE_SITE = re.compile(r"/hcmUI/CandidateExperience/[^/]+/sites/([^/]+)")


def detect(url: str) -> tuple[AtsType, dict[str, str]]:
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower()
    path = parts.path
    segments = [s for s in path.split("/") if s]

    if host.endswith(".myworkdayjobs.com"):
        labels = host.split(".")
        site = next((s for s in segments if not _LOCALE.match(s) and s not in _WD_SKIP), "")
        return AtsType.workday, {"tenant": labels[0], "wd": labels[1], "site": site}

    m = _ORACLE_SITE.search(path)
    if m and ("oraclecloud.com" in host or "/CandidateExperience/" in path):
        return AtsType.oracle, {"host": host, "site": m.group(1)}

    if host in ("careers.smartrecruiters.com", "jobs.smartrecruiters.com") and segments:
        return AtsType.smartrecruiters, {"company": segments[0]}
    if host == "jobs.ashbyhq.com" and segments:
        return AtsType.ashby, {"org": segments[0]}
    if host in ("boards.greenhouse.io", "job-boards.greenhouse.io") and segments:
        return AtsType.greenhouse, {"board": segments[0]}
    if host == "jobs.lever.co" and segments:
        return AtsType.lever, {"company": segments[0]}
    if host.endswith(".icims.com"):
        return AtsType.icims, {"host": host}
    return AtsType.generic, {}
