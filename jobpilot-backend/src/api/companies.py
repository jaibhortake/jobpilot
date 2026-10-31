from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.common.urls import UnsafeUrl
from src.db.models import CareerSource, Company, Contact
from src.db.session import get_session
from src.directory import service
from src.directory.importer import BadUpload, parse_sheet

router = APIRouter()
SessionDep = Annotated[Session, Depends(get_session)]
MAX_UPLOAD = 5 * 1024 * 1024


class SourceOut(BaseModel):
    id: int
    url: str
    ats_type: str


class ContactOut(BaseModel):
    id: int
    company_id: int
    company: str
    email: str
    name: str | None
    origin: str


class CompanyOut(BaseModel):
    id: int
    name: str
    sources: list[SourceOut]
    contact_count: int


class CompanyIn(BaseModel):
    name: str = Field(min_length=1, max_length=200)


class SourceIn(BaseModel):
    url: str


class ContactIn(BaseModel):
    company_id: int
    email: str = Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
    name: str | None = None


def _company_out(c: Company) -> CompanyOut:
    return CompanyOut(
        id=c.id,
        name=c.name,
        sources=[SourceOut(id=s.id, url=s.url, ats_type=s.ats_type.value) for s in c.sources],
        contact_count=len(c.contacts),
    )


def _contact_out(c: Contact) -> ContactOut:
    return ContactOut(
        id=c.id, company_id=c.company_id, company=c.company.name,
        email=c.email, name=c.name, origin=c.origin,
    )


def _get_company(session: Session, company_id: int) -> Company:
    company = session.get(Company, company_id)
    if not company:
        raise HTTPException(404, "company_not_found")
    return company


@router.get("/companies")
def list_companies(session: SessionDep, q: str = "") -> list[CompanyOut]:
    stmt = select(Company).order_by(Company.name_key)
    if q.strip():
        stmt = stmt.where(Company.name_key.contains(service.name_key(q)))
    return [_company_out(c) for c in session.scalars(stmt)]


@router.post("/companies", status_code=201)
def create_company(body: CompanyIn, session: SessionDep) -> CompanyOut:
    try:
        company = service.create_company(session, body.name)
    except service.Duplicate as exc:
        raise HTTPException(409, exc.code) from exc
    session.commit()
    return _company_out(company)


@router.delete("/companies/{company_id}", status_code=204)
def delete_company(company_id: int, session: SessionDep) -> None:
    session.delete(_get_company(session, company_id))
    session.commit()


@router.post("/companies/{company_id}/sources", status_code=201)
def add_source(company_id: int, body: SourceIn, session: SessionDep) -> SourceOut:
    company = _get_company(session, company_id)
    try:
        source = service.add_source(session, company, body.url)
    except UnsafeUrl as exc:
        raise HTTPException(422, "unsafe_url") from exc
    except service.Duplicate as exc:
        raise HTTPException(409, exc.code) from exc
    session.commit()
    return SourceOut(id=source.id, url=source.url, ats_type=source.ats_type.value)


@router.delete("/sources/{source_id}", status_code=204)
def delete_source(source_id: int, session: SessionDep) -> None:
    source = session.get(CareerSource, source_id)
    if not source:
        raise HTTPException(404, "source_not_found")
    session.delete(source)
    session.commit()


@router.post("/directory/import")
async def import_sheet(
    session: SessionDep, file: Annotated[UploadFile, File()]
) -> dict[str, object]:
    data = await file.read(MAX_UPLOAD + 1)
    if len(data) > MAX_UPLOAD:
        raise HTTPException(400, "bad_upload")
    try:
        parse = parse_sheet(data, file.filename or "")
    except Exception as exc:  # BadUpload, or openpyxl failing on a corrupt file
        if not isinstance(exc, BadUpload):
            exc = BadUpload("unreadable file")
        raise HTTPException(400, "bad_upload") from exc
    r = service.import_directory(session, parse)
    return r.__dict__


@router.get("/contacts")
def list_contacts(session: SessionDep, q: str = "") -> list[ContactOut]:
    stmt = select(Contact).join(Company).order_by(Company.name_key, Contact.email)
    needle = q.strip().lower()
    if needle:
        stmt = stmt.where(Contact.email.contains(needle) | Company.name_key.contains(needle))
    return [_contact_out(c) for c in session.scalars(stmt)]


@router.post("/contacts", status_code=201)
def create_contact(body: ContactIn, session: SessionDep) -> ContactOut:
    company = _get_company(session, body.company_id)
    try:
        contact = service.add_contact(session, company, body.email, body.name)
    except service.Duplicate as exc:
        raise HTTPException(409, exc.code) from exc
    session.commit()
    return _contact_out(contact)


@router.delete("/contacts/{contact_id}", status_code=204)
def delete_contact(contact_id: int, session: SessionDep) -> None:
    contact = session.get(Contact, contact_id)
    if not contact:
        raise HTTPException(404, "contact_not_found")
    session.delete(contact)
    session.commit()


class FindIn(BaseModel):
    company_id: int
    full_name: str | None = None
    domain: str | None = Field(default=None, pattern=r"^[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")


class GuessOut(BaseModel):
    email: str
    pattern: str
    confidence: str
    note: str


class FindOut(BaseModel):
    domain: str | None
    domain_resolves: bool
    guesses: list[GuessOut]


@router.post("/contacts/find")
def find_contact(body: FindIn, session: SessionDep) -> FindOut:
    from src.directory import email_finder

    company = _get_company(session, body.company_id)
    if body.domain:  # the user confirms the domain once; it is then remembered
        company.domain = body.domain.lower()
        session.commit()
    everyone = list(session.scalars(select(Contact)))
    domain, guesses = email_finder.find_emails(company, body.full_name, everyone, body.domain)
    return FindOut(
        domain=domain,
        domain_resolves=bool(domain) and email_finder.domain_resolves(domain or ""),
        guesses=[GuessOut(**g.__dict__) for g in guesses],
    )


class BulkIn(BaseModel):
    text: str
    aliases: dict[str, str] = {}


@router.post("/contacts/bulk")
def bulk_contacts(body: BulkIn, session: SessionDep) -> dict[str, object]:
    from src.directory.email_import import import_pasted

    return import_pasted(session, body.text, body.aliases).__dict__
