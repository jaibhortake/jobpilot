import asyncio
import hashlib
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.db.models import CareerSource, CheckRun, Company, Job, JobStatus, JobStatusEvent
from src.db.session import SessionLocal
from src.discovery.base import FetchResult, JobPostingIn, SearchQuery
from src.discovery.descriptions import describe_missing
from src.discovery.http import SourceFetchError, get_client
from src.discovery.locations import match_location
from src.discovery.readers.generic import GenericNotice
from src.discovery.registry import get_reader

CLOSEABLE = (JobStatus.new, JobStatus.shortlisted, JobStatus.dismissed)
GENERIC_MISSES = 2


class CheckRunning(Exception):
    def __init__(self, run_id: int) -> None:
        super().__init__(f"check {run_id} already running")
        self.run_id = run_id


def default_query(since: datetime | None) -> SearchQuery:
    d = settings.discovery
    return SearchQuery(
        keywords=list(d.keywords), locations=list(d.locations),
        max_age_days=int(d.max_age_days), since=since,
    )


def query_hash(q: SearchQuery) -> str:
    raw = "|".join(sorted(q.keywords)) + "#" + "|".join(sorted(q.locations))
    return hashlib.sha1(raw.encode()).hexdigest()[:12]


def dedupe(postings: list[JobPostingIn]) -> list[JobPostingIn]:
    seen: dict[str, JobPostingIn] = {}
    for p in postings:
        seen.setdefault(p.external_id, p)
    return list(seen.values())


def start_check(session: Session, source_id: int) -> CheckRun:
    run = CheckRun(source_id=source_id, status="running", phase="crawling", stats={})
    session.add(run)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        active = session.scalar(
            select(CheckRun).where(CheckRun.source_id == source_id, CheckRun.status == "running")
        )
        raise CheckRunning(active.id if active else 0) from exc
    return run


def recover_runs() -> None:
    """Single-process app: any run still marked running at startup was interrupted."""
    with SessionLocal() as s:
        for run in s.scalars(select(CheckRun).where(CheckRun.status == "running")):
            run.status = "failed"
            run.error = "interrupted (app restarted)"
            run.finished_at = datetime.now(UTC)
        s.commit()


def cancel_check(session: Session, run_id: int) -> None:
    run = session.get(CheckRun, run_id)
    if run and run.status == "running":
        run.cancel_requested = True
        session.commit()


def _cancel_requested(run_id: int) -> bool:
    with SessionLocal() as s:
        run = s.get(CheckRun, run_id)
        return bool(run and run.cancel_requested)


def _set_phase(run_id: int, phase: str) -> None:
    with SessionLocal() as s:
        run = s.get(CheckRun, run_id)
        if run:
            run.phase = phase
            s.commit()


def _load(run_id: int) -> tuple[int, datetime | None, str, dict[str, Any], str]:
    with SessionLocal() as s:
        run = s.get(CheckRun, run_id)
        assert run
        src = s.get(CareerSource, run.source_id)
        assert src
        return src.id, src.last_success_at, src.ats_type.value, dict(src.ats_config), src.url


def _event(session: Session, job: Job, old: JobStatus | None, new: JobStatus, note: str) -> None:
    session.add(JobStatusEvent(
        job_id=job.id, from_status=old.value if old else None, to_status=new.value,
        note=note, actor="system",
    ))


def persist(
    run_id: int, source_id: int, postings: list[JobPostingIn], result: FetchResult,
    q: SearchQuery, config: dict[str, Any],
) -> dict[str, int]:
    now = datetime.now(UTC)
    stats = {"found_raw": result.found_raw, "kept": 0, "new": 0, "updated": 0,
             "closed": 0, "restored": 0, "dropped_location": 0}
    with SessionLocal() as s:
        src = s.get(CareerSource, source_id)
        assert src
        first_crawl = src.last_success_at is None
        qh = query_hash(q)
        complete = result.complete and config.get("last_query_hash") == qh
        generic = src.ats_type.value == "generic"

        kept: list[JobPostingIn] = []
        for p in postings:
            if match_location(p.location, p.country, q.locations).ok:
                kept.append(p)
            else:
                stats["dropped_location"] += 1
        kept = dedupe(kept)
        stats["kept"] = len(kept)

        existing = {
            j.external_id: j
            for j in s.scalars(select(Job).where(
                Job.company_id == src.company_id,
                Job.external_id.in_([p.external_id for p in kept]),
            ))
        }
        seen_ids: set[int] = set()
        for p in kept:
            job = existing.get(p.external_id)
            if job is None:
                undated = p.posted_at is None
                job = Job(
                    source_id=src.id, company_id=src.company_id, external_id=p.external_id,
                    title=p.title, location=p.location, remote=p.remote, country=p.country,
                    url=p.url, description=p.description,
                    description_source="ats" if p.description else None,
                    posted_at=p.posted_at if not undated else (None if first_crawl else now),
                    posted_text=p.posted_text, date_known=not (undated and first_crawl),
                    first_seen_at=now, last_seen_at=now, missed_checks=0,
                    status=JobStatus.new, origin="check",
                )
                s.add(job)
                s.flush()
                stats["new"] += 1
            else:
                job.title, job.location, job.url = p.title, p.location, p.url
                job.last_seen_at, job.missed_checks = now, 0
                if p.posted_at:
                    old = job.posted_at
                    job.posted_at = min(old, p.posted_at) if old else p.posted_at
                    job.date_known = True
                if p.description and not job.description:
                    job.description, job.description_source = p.description, "ats"
                if job.status == JobStatus.closed and job.status_before_close:
                    restored = job.status_before_close
                    _event(s, job, JobStatus.closed, restored, "seen again")
                    job.status, job.status_before_close = restored, None
                    stats["restored"] += 1
                stats["updated"] += 1
            seen_ids.add(job.id)

        if complete:
            stale = s.scalars(select(Job).where(
                Job.source_id == src.id, Job.status.in_(CLOSEABLE),
                Job.id.not_in(seen_ids) if seen_ids else Job.id.is_not(None),
            ))
            for job in stale:
                job.missed_checks += 1
                if generic and job.missed_checks < GENERIC_MISSES:
                    continue
                _event(s, job, job.status, JobStatus.closed, "no longer listed")
                job.status_before_close, job.status = job.status, JobStatus.closed
                stats["closed"] += 1

        src.ats_config = {
            **config, "last_query_hash": qh,
            "prev_check_at": src.last_success_at.isoformat() if src.last_success_at else None,
        }
        src.last_check_at = src.last_success_at = now
        src.last_status = "ok" if kept else "no_listings"
        src.last_error = None
        src.last_found, src.last_kept = result.found_raw, len(kept)
        run = s.get(CheckRun, run_id)
        assert run
        run.stats = stats
        s.commit()
    return stats


def _fail(
    run_id: int, source_id: int, status: str, message: str, run_status: str = "failed"
) -> None:
    with SessionLocal() as s:
        run, src = s.get(CheckRun, run_id), s.get(CareerSource, source_id)
        if run:
            run.status, run.error, run.finished_at = run_status, message, datetime.now(UTC)
        if src:
            src.last_check_at, src.last_status, src.last_error = datetime.now(UTC), status, message
        s.commit()


def _rescore() -> None:
    from src.matching.service import rescore_all

    with SessionLocal() as s:
        rescore_all(s)


def _finish(run_id: int, status: str) -> None:
    with SessionLocal() as s:
        run = s.get(CheckRun, run_id)
        if run:
            run.status, run.phase, run.finished_at = status, "done", datetime.now(UTC)
            s.commit()


async def run_check(run_id: int) -> None:
    source_id, last_success, ats_value, config, url = await asyncio.to_thread(_load, run_id)
    from src.db.models import AtsType

    reader = get_reader(AtsType(ats_value))
    if reader is None:
        await asyncio.to_thread(
            _fail, run_id, source_id, "skipped", "reader arrives in a later phase", "done"
        )
        return

    q = default_query(last_success)

    async def cancel() -> bool:
        return await asyncio.to_thread(_cancel_requested, run_id)

    # the reader mutates ats_config (cached facet ids); give it a throwaway source object
    probe = CareerSource(ats_type=AtsType(ats_value), ats_config=config, url=url)
    try:
        async with get_client() as client:
            result = await reader.fetch(probe, client, q, cancel)
    except GenericNotice as notice:
        await asyncio.to_thread(_fail, run_id, source_id, notice.status, str(notice), "done")
        return
    except SourceFetchError as exc:
        await asyncio.to_thread(_fail, run_id, source_id, "error", str(exc))
        return
    except Exception as exc:  # reader bug or unexpected payload shape
        await asyncio.to_thread(_fail, run_id, source_id, "error", f"{type(exc).__name__}: {exc}")
        return

    if await cancel():
        # keep what was saved before; nothing is closed on cancel
        result.complete = False
    await asyncio.to_thread(
        persist, run_id, source_id, result.postings, result, q, probe.ats_config
    )
    await asyncio.to_thread(_set_phase, run_id, "describing")
    try:
        async with get_client() as client:
            await describe_missing(client, source_id)
    except Exception:  # descriptions are best-effort; the crawl already succeeded
        pass
    await asyncio.to_thread(_set_phase, run_id, "scoring")
    await asyncio.to_thread(_rescore)
    await asyncio.to_thread(_finish, run_id, "cancelled" if await cancel() else "done")


def check_company(session: Session, company: Company) -> list[CheckRun]:
    runs = []
    for src in company.sources:
        if src.enabled:
            runs.append(start_check(session, src.id))
    return runs
