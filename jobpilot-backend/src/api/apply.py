"""Apply Assist: applicant details, answer bank, form filling and mark-applied for the
Chrome extension. The extension fills forms; it never submits them."""

from pathlib import Path
from typing import Annotated
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.api.jobs import JobOut, StatusIn, set_status
from src.apply.match import (
    DETAIL_KEYS,
    FieldIn,
    FieldOut,
    is_detail_question,
    match_field,
    norm_question,
)
from src.common.urls import UnsafeUrl, canonical_url
from src.config.settings import settings
from src.db.models import Answer, Applicant, Job
from src.db.session import get_session

router = APIRouter()
SessionDep = Annotated[Session, Depends(get_session)]
DRAFT_MIN_CHARS = 25  # labels shorter than this are not real questions worth an LLM draft


def _applicant(session: Session) -> Applicant:
    a = session.get(Applicant, 1)
    if a is None:
        a = Applicant(id=1, details={}, disabled_sites=["linkedin.com", "naukri.com"])
        session.add(a)
        session.commit()
    return a


class ApplicantModel(BaseModel):
    details: dict[str, str]
    disabled_sites: list[str]


@router.get("/applicant")
def get_applicant(session: SessionDep) -> ApplicantModel:
    a = _applicant(session)
    return ApplicantModel(details=dict(a.details), disabled_sites=list(a.disabled_sites))


@router.put("/applicant")
def put_applicant(body: ApplicantModel, session: SessionDep) -> ApplicantModel:
    a = _applicant(session)
    a.details = {k: v.strip() for k, v in body.details.items() if k in DETAIL_KEYS and v.strip()}
    a.disabled_sites = sorted({s.strip().lower() for s in body.disabled_sites if s.strip()})
    session.commit()
    return get_applicant(session)


@router.get("/applicant/keys")
def detail_keys() -> list[str]:
    return DETAIL_KEYS


class AnswerModel(BaseModel):
    id: int | None = None
    question: str
    answer: str


@router.get("/answers")
def list_answers(session: SessionDep) -> list[AnswerModel]:
    rows = session.scalars(select(Answer).order_by(Answer.question)).all()
    return [AnswerModel(id=r.id, question=r.question, answer=r.answer) for r in rows]


def _upsert(session: Session, question: str, answer: str) -> None:
    key = norm_question(question)
    if not key or not answer.strip() or is_detail_question(question):
        return
    row = session.scalar(select(Answer).where(Answer.key == key))
    if row is None:
        session.add(Answer(question=question.strip(), key=key, answer=answer.strip()))
    else:
        row.answer = answer.strip()


@router.post("/answers")
def save_answers(body: list[AnswerModel], session: SessionDep) -> dict[str, int]:
    for a in body:
        _upsert(session, a.question, a.answer)
    session.commit()
    return {"saved": len(body)}


@router.delete("/answers/{answer_id}", status_code=204)
def delete_answer(answer_id: int, session: SessionDep) -> None:
    row = session.get(Answer, answer_id)
    if row is None:
        raise HTTPException(404, "answer_not_found")
    session.delete(row)
    session.commit()


def _strip_apply(path: str) -> str:
    path = path.rstrip("/")
    for tail in ("/apply", "/application", "/applynow", "/apply/applymanually"):
        if path.lower().endswith(tail):
            return path[: -len(tail)]
    return path


def find_job(session: Session, page_url: str) -> Job | None:
    """The job whose posting URL matches the application page, or None when unsure."""
    try:
        page = urlsplit(canonical_url(page_url))
    except UnsafeUrl:
        return None
    jobs = session.scalars(select(Job).where(Job.url.ilike(f"%{page.netloc}%"))).all()
    want = _strip_apply(page.path)
    exact = [j for j in jobs if j.url and _strip_apply(urlsplit(canonical_url(j.url)).path) == want]
    if len(exact) == 1:
        return exact[0]
    by_id = [j for j in jobs if len(j.external_id) >= 4 and j.external_id in page_url]
    return by_id[0] if len(by_id) == 1 else None


class FillIn(BaseModel):
    url: str
    fields: list[FieldIn]
    draft: bool = True


class FillOut(BaseModel):
    job_id: int | None
    job_title: str | None
    fields: list[FieldOut]


async def _draft(question: str, job: Job | None) -> str | None:
    from src.llm import router as llm
    from src.llm.errors import LlmError
    from src.matching.scorer import cv_skills

    skills = ", ".join(sorted(cv_skills())[:25])
    about = f"'{job.title}' at {job.company.name}" if job else "this role"
    jd = (job.description or "")[:3000] if job else ""
    prompt = (
        f"Answer this job application question for Jai Bhortake applying to {about} in 2-4 "
        f"honest first-person sentences. Use ONLY these facts: B.Tech in Electronics and "
        f"Telecommunication (VJTI, 2026); GenAI Engineer at Accionlabs (GraphRAG, Neo4j, "
        f"LangChain); Security Researcher (CVE recreation, VAPT, IoT); skills: {skills}. "
        f"Do not invent employers, numbers or degrees. Reply with the answer only.\n"
        f"Question: {question}\nJob description: {jd or 'not provided'}"
    )
    try:
        text = await llm.complete("extract", [{"role": "user", "content": prompt}], max_tokens=400)
    except LlmError:
        return None
    return text.strip() or None


@router.post("/apply/fill")
async def fill(body: FillIn, session: SessionDep) -> FillOut:
    details = dict(_applicant(session).details)
    bank = {r.key: r.answer for r in session.scalars(select(Answer))}
    job = find_job(session, body.url)
    out = []
    for f in body.fields[:200]:
        r = match_field(f, details, bank)
        if (r.value is None and body.draft and f.kind == "textarea"
                and len(f.label) >= DRAFT_MIN_CHARS):
            text = await _draft(f.label, job)
            if text:
                r = FieldOut(id=f.id, value=text, confidence="medium", source="llm")
        out.append(r)
    return FillOut(job_id=job.id if job else None, job_title=job.title if job else None, fields=out)


class MarkIn(BaseModel):
    url: str


@router.post("/apply/mark-applied")
def mark_applied(body: MarkIn, session: SessionDep) -> JobOut:
    job = find_job(session, body.url)
    if job is None:
        raise HTTPException(404, "job_not_in_jobpilot")
    return set_status(job.id, StatusIn(status="applied", note="via Apply Assist"), session)


@router.get("/apply/cv")
def cv_file() -> FileResponse:
    path = Path(str(settings.get("apply.cv_path", "")))
    if not path.is_file() or path.suffix.lower() != ".pdf":
        raise HTTPException(404, "cv_not_found")
    return FileResponse(path, media_type="application/pdf", filename=path.name)
