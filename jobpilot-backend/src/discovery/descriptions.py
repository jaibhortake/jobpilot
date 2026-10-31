import html
import re
from urllib.parse import urlsplit

import httpx
from sqlalchemy import select

from src.db.models import AtsType, CareerSource, Job
from src.db.session import SessionLocal
from src.discovery.http import SourceFetchError, request_with_retry

CAP = 40


def _text(markup: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", html.unescape(markup))).strip()


async def fetch_workday(client: httpx.AsyncClient, cfg: dict[str, str], url: str) -> str | None:
    host = f"{cfg['tenant']}.{cfg['wd']}.myworkdayjobs.com"
    path = urlsplit(url).path
    marker = f"/{cfg['site']}"
    ext = path.split(marker, 1)[1] if marker in path else None
    if not ext:
        return None
    api = f"https://{host}/wday/cxs/{cfg['tenant']}/{cfg['site']}{ext}"
    data = (await request_with_retry(client, "GET", api)).json()
    raw = (data.get("jobPostingInfo") or {}).get("jobDescription")
    return _text(raw)[:12000] if raw else None


async def describe_missing(client: httpx.AsyncClient, source_id: int) -> int:
    """Fetch descriptions for this source's jobs lacking one (newest first). Returns the count."""
    with SessionLocal() as s:
        src = s.get(CareerSource, source_id)
        if not src or src.ats_type != AtsType.workday:
            return 0
        cfg = {k: str(v) for k, v in src.ats_config.items() if isinstance(v, str)}
        jobs = [(j.id, j.url) for j in s.scalars(
            select(Job).where(Job.source_id == source_id, Job.description.is_(None))
            .order_by(Job.first_seen_at.desc(), Job.id.desc()).limit(CAP)
        ) if j.url]
    done = 0
    for job_id, url in jobs:
        try:
            text = await fetch_workday(client, cfg, url)
        except SourceFetchError:
            continue
        if text:
            with SessionLocal() as s:
                job = s.get(Job, job_id)
                if job and not job.description:
                    job.description, job.description_source = text, "ats"
                    s.commit()
                    done += 1
    return done
