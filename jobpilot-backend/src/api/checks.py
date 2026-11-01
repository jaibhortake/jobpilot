from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.common.urls import UnsafeUrl, safe_http_url
from src.db.models import CareerSource, CheckRun, Company
from src.db.session import get_session
from src.directory import service as directory
from src.discovery import service

router = APIRouter()
SessionDep = Annotated[Session, Depends(get_session)]


class RunOut(BaseModel):
    id: int
    source_id: int
    company: str
    status: str
    phase: str
    stats: dict[str, object]
    error: str | None
    started_at: datetime
    finished_at: datetime | None


class RunsOut(BaseModel):
    runs: list[RunOut]


class ByInput(BaseModel):
    company_name: str | None = None
    url: str | None = None


def _out(session: Session, run: CheckRun) -> RunOut:
    src = session.get(CareerSource, run.source_id)
    name = src.company.name if src else ""
    return RunOut(
        id=run.id, source_id=run.source_id, company=name, status=run.status, phase=run.phase,
        stats=run.stats or {}, error=run.error, started_at=run.started_at,
        finished_at=run.finished_at,
    )


def _start(session: Session, bg: BackgroundTasks, company: Company) -> RunsOut:
    if not any(s.enabled for s in company.sources):
        raise HTTPException(422, "no_sources")
    try:
        runs = service.check_company(session, company)
    except service.CheckRunning as exc:
        raise HTTPException(409, {"code": "check_running", "run_id": exc.run_id}) from exc
    for r in runs:
        bg.add_task(service.run_check, r.id)
    return RunsOut(runs=[_out(session, r) for r in runs])


@router.post("/companies/{company_id}/check", status_code=202)
def check_known(company_id: int, session: SessionDep, bg: BackgroundTasks) -> RunsOut:
    company = session.get(Company, company_id)
    if not company:
        raise HTTPException(404, "company_not_found")
    return _start(session, bg, company)


@router.post("/checks/by-input", status_code=202)
def check_by_input(body: ByInput, session: SessionDep, bg: BackgroundTasks) -> RunsOut:
    name = (body.company_name or "").strip()
    if body.url:
        try:
            url = safe_http_url(body.url)
        except UnsafeUrl as exc:
            raise HTTPException(422, "unsafe_url") from exc
        src = session.scalar(select(CareerSource).where(CareerSource.url == url))
        if src:
            return _start(session, bg, src.company)
        if not name:
            raise HTTPException(422, "company_name_required")
        owner = directory.find_company(session, name) or directory.create_company(session, name)
        directory.add_source(session, owner, url)
        session.commit()
        return _start(session, bg, owner)
    if not name:
        raise HTTPException(422, "company_name_required")
    company = directory.find_company(session, name)
    if not company:
        raise HTTPException(404, "company_not_found")
    return _start(session, bg, company)


class CandidateOut(BaseModel):
    url: str
    title: str
    ats_type: str


@router.get("/companies/find-careers")
async def find_careers(name: str) -> list[CandidateOut]:
    from src.directory.careers_finder import SearchFailed, find_careers_pages
    from src.search.provider import get_search_provider

    try:
        found = await find_careers_pages(name, get_search_provider())
    except SearchFailed as exc:
        raise HTTPException(502, "search_failed") from exc
    return [CandidateOut(url=c.url, title=c.title, ats_type=c.ats_type) for c in found]


@router.get("/checks/active")
def active(session: SessionDep) -> RunsOut:
    runs = session.scalars(select(CheckRun).where(CheckRun.status == "running"))
    return RunsOut(runs=[_out(session, r) for r in runs])


@router.get("/checks/{run_id}")
def get_run(run_id: int, session: SessionDep) -> RunOut:
    run = session.get(CheckRun, run_id)
    if not run:
        raise HTTPException(404, "run_not_found")
    return _out(session, run)


@router.post("/checks/{run_id}/cancel")
def cancel(run_id: int, session: SessionDep) -> RunOut:
    service.cancel_check(session, run_id)
    return get_run(run_id, session)
