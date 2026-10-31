from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from src.common.urls import UnsafeUrl, safe_http_url
from src.db.models import CareerSource, Feedback, Job, JobScore, JobStatus, JobStatusEvent
from src.db.session import get_session
from src.matching import service as matching

router = APIRouter()
SessionDep = Annotated[Session, Depends(get_session)]


class JobOut(BaseModel):
    id: int
    company_id: int
    company: str
    title: str
    location: str | None
    remote: bool
    url: str | None
    posted_at: datetime | None
    date_known: bool
    first_seen_at: datetime
    status: str
    is_new: bool
    description: str | None = None
    score: int | None = None
    filtered: bool = False
    reasons: list[str] = []
    feedback: int | None = None


class JobsOut(BaseModel):
    items: list[JobOut]
    total: int


class EventOut(BaseModel):
    from_status: str | None
    to_status: str
    at: datetime
    note: str | None
    actor: str


class JobDetail(JobOut):
    events: list[EventOut]


def _is_new(job: Job, source: CareerSource | None) -> bool:
    if job.status != JobStatus.new:
        return False
    prev = source.ats_config.get("prev_check_at") if source else None
    return prev is None or job.first_seen_at >= datetime.fromisoformat(prev)


def _out(job: Job, source: CareerSource | None, with_desc: bool = False) -> JobOut:
    return JobOut(
        id=job.id, company_id=job.company_id, company=job.company.name, title=job.title,
        location=job.location, remote=job.remote, url=job.url, posted_at=job.posted_at,
        date_known=job.date_known, first_seen_at=job.first_seen_at, status=job.status.value,
        is_new=_is_new(job, source), description=job.description if with_desc else None,
    )


@router.get("/jobs")
def list_jobs(
    session: SessionDep, company_id: int | None = None, q: str = "",
    posted_within_days: int | None = None, include_dismissed: bool = False,
    include_closed: bool = False, limit: int = 50, offset: int = 0,
    min_score: int = 0, include_filtered: bool = False, sort: str = "date", statuses: str = "",
) -> JobsOut:
    stmt = select(Job).outerjoin(JobScore, JobScore.job_id == Job.id)
    wanted = [JobStatus(s) for s in statuses.split(",") if s in JobStatus.__members__]
    if wanted:  # tracker view: explicit statuses, no score/dismiss/close hiding
        stmt = stmt.where(Job.status.in_(wanted))
        include_filtered = include_dismissed = include_closed = True
    if not include_filtered:
        stmt = stmt.where(JobScore.filtered.is_not(True))
    if min_score:
        stmt = stmt.where(func.coalesce(JobScore.score, 0) >= min_score)
    if company_id:
        stmt = stmt.where(Job.company_id == company_id)
    if q.strip():
        stmt = stmt.where(Job.title.ilike(f"%{q.strip()}%"))
    hidden = [JobStatus.dismissed] if not include_dismissed else []
    if not include_closed:
        hidden.append(JobStatus.closed)
    if hidden:
        stmt = stmt.where(Job.status.not_in(hidden))
    if posted_within_days:
        stmt = stmt.where(
            func.coalesce(Job.posted_at, Job.first_seen_at)
            >= func.now() - func.make_interval(0, 0, 0, posted_within_days)
        )
    total = session.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    by_date = (
        Job.date_known.desc(), func.coalesce(Job.posted_at, Job.first_seen_at).desc(), Job.id.desc()
    )
    order = (func.coalesce(JobScore.score, 0).desc(), *by_date) if sort == "score" else by_date
    stmt = stmt.order_by(*order).limit(min(limit, 200)).offset(offset)
    jobs = list(session.scalars(stmt))
    items = [_with_score(session, _out(j, session.get(CareerSource, j.source_id)
                                       if j.source_id else None)) for j in jobs]
    return JobsOut(items=items, total=total)


def _with_score(session: Session, out: JobOut) -> JobOut:
    sc = session.get(JobScore, out.id)
    fb = session.get(Feedback, out.id)
    if sc:
        out.score, out.filtered, out.reasons = sc.score, sc.filtered, list(sc.reasons)
    out.feedback = fb.value if fb else None
    return out


class FeedbackIn(BaseModel):
    value: int | None


@router.post("/jobs/{job_id}/feedback")
def set_feedback(job_id: int, body: FeedbackIn, session: SessionDep) -> JobOut:
    job = _get(session, job_id)
    existing = session.get(Feedback, job_id)
    if existing:
        session.delete(existing)
        session.flush()
    if body.value in (1, -1):
        session.add(Feedback(job_id=job_id, value=body.value))
    session.commit()
    matching.rebuild_weights(session)
    matching.rescore_all(session)
    return _with_score(session, _out(job, None))


class HideIn(BaseModel):
    words: list[str]


@router.post("/jobs/{job_id}/hide-similar")
def hide_similar(job_id: int, body: HideIn, session: SessionDep) -> JobOut:
    job = _get(session, job_id)
    profile = matching.get_profile(session)
    profile.hidden_title_words = sorted({*profile.hidden_title_words,
                                         *(w.lower() for w in body.words if w.strip())})
    session.commit()
    matching.rescore_all(session)
    return _with_score(session, _out(job, None))


@router.post("/jobs/rescore")
def rescore(session: SessionDep) -> dict[str, int]:
    return {"rescored": matching.rescore_all(session)}


def _get(session: Session, job_id: int) -> Job:
    job = session.get(Job, job_id)
    if not job:
        raise HTTPException(404, "job_not_found")
    return job


@router.get("/jobs/{job_id}")
def get_job(job_id: int, session: SessionDep) -> JobDetail:
    job = _get(session, job_id)
    src = session.get(CareerSource, job.source_id) if job.source_id else None
    events = session.scalars(
        select(JobStatusEvent).where(JobStatusEvent.job_id == job.id).order_by(JobStatusEvent.id)
    )
    base = _with_score(session, _out(job, src, with_desc=True))
    return JobDetail(**base.model_dump(), events=[
        EventOut(from_status=e.from_status, to_status=e.to_status, at=e.at, note=e.note,
                 actor=e.actor)
        for e in events
    ])


def _transition(session: Session, job: Job, frm: JobStatus, to: JobStatus) -> None:
    if job.status != frm:
        raise HTTPException(409, "invalid_transition")
    job.status = to
    session.add(JobStatusEvent(
        job_id=job.id, from_status=frm.value, to_status=to.value, actor="user"
    ))
    session.commit()


@router.post("/jobs/{job_id}/dismiss")
def dismiss(job_id: int, session: SessionDep) -> JobOut:
    job = _get(session, job_id)
    _transition(session, job, JobStatus.new, JobStatus.dismissed)
    return _out(job, None)


@router.post("/jobs/{job_id}/undismiss")
def undismiss(job_id: int, session: SessionDep) -> JobOut:
    job = _get(session, job_id)
    _transition(session, job, JobStatus.dismissed, JobStatus.new)
    return _out(job, None)


TRACKED = {
    JobStatus.new, JobStatus.shortlisted, JobStatus.applied, JobStatus.interview,
    JobStatus.offer, JobStatus.rejected, JobStatus.dismissed,
}


class StatusIn(BaseModel):
    status: str
    note: str | None = None


@router.post("/jobs/{job_id}/status")
def set_status(job_id: int, body: StatusIn, session: SessionDep) -> JobOut:
    job = _get(session, job_id)
    if body.status not in JobStatus.__members__ or JobStatus(body.status) not in TRACKED:
        raise HTTPException(422, "invalid_status")
    new = JobStatus(body.status)
    if job.status != new:
        session.add(JobStatusEvent(
            job_id=job.id, from_status=job.status.value, to_status=new.value,
            note=body.note, actor="user",
        ))
        job.status, job.status_before_close = new, None
        session.commit()
    return _with_score(session, _out(job, None))


@router.post("/jobs/{job_id}/cover-letter")
async def cover_letter(job_id: int, session: SessionDep) -> dict[str, str]:
    from src.llm import router as llm
    from src.llm.errors import LlmError
    from src.matching.scorer import cv_skills

    job = _get(session, job_id)
    skills = ", ".join(sorted(cv_skills())[:25])
    prompt = (
        f"Write a concise, honest cover letter (under 220 words) for Jai Bhortake applying to "
        f"'{job.title}' at {job.company.name}. Use ONLY these facts: B.Tech in Electronics and "
        f"Telecommunication (VJTI, 2026); GenAI Engineer at Accionlabs (GraphRAG, Neo4j, "
        f"LangChain); Security Researcher (CVE recreation, VAPT, IoT); skills: {skills}. "
        f"Do not invent employers, numbers or degrees. Job description:\n"
        f"{(job.description or 'not provided')[:4000]}"
    )
    try:
        text = await llm.complete("extract", [{"role": "user", "content": prompt}], max_tokens=700)
    except LlmError as exc:
        raise HTTPException(503, f"llm_unavailable: {exc}") from exc
    return {"text": text}


class AiMatch(BaseModel):
    score: int
    reason: str


@router.post("/jobs/{job_id}/ai-match")
async def ai_match(job_id: int, session: SessionDep) -> JobOut:
    """Ask Qwen how well this job fits the CV; the result is blended into the score."""
    from src.llm import router as llm
    from src.llm.errors import LlmError
    from src.matching.scorer import cv_skills

    job = _get(session, job_id)
    prompt = (
        "Rate how well this job fits the candidate, 0-100, and give one short reason "
        "(max 20 words). Candidate: new graduate (B.Tech Electronics & Telecom, 2026), GenAI "
        f"engineer, security research; skills: {', '.join(sorted(cv_skills())[:30])}. "
        f"Job: {job.title} at {job.company.name}. "
        f"Description: {(job.description or 'not provided')[:3000]}"
    )
    try:
        res = await llm.complete(
            "classify", [{"role": "user", "content": prompt}], schema=AiMatch, max_tokens=300
        )
    except LlmError as exc:
        raise HTTPException(503, f"llm_unavailable: {exc}") from exc
    job.ai_score, job.ai_reason = max(0, min(100, res.score)), res.reason[:200]
    session.commit()
    matching.rescore_all(session)
    return _with_score(session, _out(job, None))


class ManualJob(BaseModel):
    company_name: str
    title: str
    url: str | None = None
    location: str | None = None
    description: str | None = None


@router.post("/jobs/manual", status_code=201)
def add_manual(body: ManualJob, session: SessionDep) -> JobOut:
    import hashlib
    import uuid

    from src.common.urls import canonical_url
    from src.db.models import Company
    from src.directory import service as directory

    url = None
    if body.url:
        try:
            url = safe_http_url(body.url)
        except UnsafeUrl as exc:
            raise HTTPException(422, "unsafe_url") from exc
    company = session.scalar(
        select(Company).where(Company.name_key == directory.name_key(body.company_name))
    ) or directory.create_company(session, body.company_name)
    ext = (
        hashlib.sha1(canonical_url(url).encode()).hexdigest()[:16] if url
        else f"manual-{uuid.uuid4().hex}"
    )
    dup = session.scalar(
        select(Job).where(Job.company_id == company.id, Job.external_id == ext)
    )
    if dup:
        raise HTTPException(409, {"code": "duplicate_job", "existing_id": dup.id})
    job = Job(
        company_id=company.id, external_id=ext, title=body.title, url=url,
        location=body.location, description=body.description or None,
        description_source="pasted" if body.description else None,
        origin="url" if url else "manual", status=JobStatus.new, date_known=True,
        posted_at=None,
    )
    session.add(job)
    session.commit()
    return _out(job, None)


class DescriptionIn(BaseModel):
    text: str


@router.put("/jobs/{job_id}/description")
def set_description(job_id: int, body: DescriptionIn, session: SessionDep) -> JobOut:
    job = _get(session, job_id)
    job.description, job.description_source = body.text, "pasted"
    session.commit()
    matching.rescore_all(session)
    return _with_score(session, _out(job, None, with_desc=True))
