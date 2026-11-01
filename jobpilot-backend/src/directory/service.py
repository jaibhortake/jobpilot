from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.common.urls import UnsafeUrl, safe_http_url
from src.db.models import CareerSource, Company, Contact
from src.directory.ats_detect import detect
from src.directory.importer import SheetParse

OTHER = "Other"


class Duplicate(Exception):
    def __init__(self, code: str) -> None:
        super().__init__(code)
        self.code = code


def name_key(name: str) -> str:
    return " ".join(name.split()).lower()


@dataclass
class ImportResult:
    companies_created: int = 0
    companies_existing: int = 0
    sources_created: int = 0
    contacts_created: int = 0
    unsafe_urls: list[str] = field(default_factory=list)


def find_company(session: Session, name: str) -> Company | None:
    """Exact name, else the only company whose name contains it ("rockwell" matches one)."""
    key = name_key(name)
    exact = session.scalar(select(Company).where(Company.name_key == key))
    if exact or len(key) < 3:
        return exact
    hits = list(
        session.scalars(select(Company).where(Company.name_key.contains(key, autoescape=True)))
    )
    return hits[0] if len(hits) == 1 else None


def move_domain(session: Session, domain: str, target_name: str) -> int:
    """Move every "Other" contact on this email domain to a company, creating it if needed."""
    target = session.scalar(select(Company).where(Company.name_key == name_key(target_name)))
    target = target or create_company(session, target_name)
    if target.name == OTHER:
        return 0
    rows = session.scalars(
        select(Contact).join(Company).where(
            Company.name == OTHER, Contact.email.endswith(f"@{domain.lower()}", autoescape=True)
        )
    )
    moved = 0
    for contact in rows:
        if session.scalar(
            select(Contact).where(Contact.company_id == target.id, Contact.email == contact.email)
        ):
            session.delete(contact)  # already listed under the company
        else:
            contact.company_id = target.id
        moved += 1
    session.flush()
    return moved


def rename_company(session: Session, company: Company, name: str) -> Company:
    key = name_key(name)
    clash = session.scalar(select(Company).where(Company.name_key == key, Company.id != company.id))
    if clash:
        raise Duplicate("duplicate_company")
    company.name, company.name_key = " ".join(name.split()), key
    session.flush()
    return company


def create_company(session: Session, name: str) -> Company:
    key = name_key(name)
    if session.scalar(select(Company).where(Company.name_key == key)):
        raise Duplicate("duplicate_company")
    company = Company(name=" ".join(name.split()), name_key=key)
    session.add(company)
    session.flush()
    return company


def add_source(session: Session, company: Company, url: str) -> CareerSource:
    url = safe_http_url(url)
    if session.scalar(select(CareerSource).where(CareerSource.url == url)):
        raise Duplicate("duplicate_url")
    ats, config = detect(url)
    source = CareerSource(company_id=company.id, url=url, ats_type=ats, ats_config=dict(config))
    session.add(source)
    session.flush()
    return source


def update_source(session: Session, source: CareerSource, url: str) -> CareerSource:
    """Point a source at a new link: re-detect its platform and forget the old check result."""
    url = safe_http_url(url)
    if url == source.url:
        return source
    clash = session.scalar(
        select(CareerSource).where(CareerSource.url == url, CareerSource.id != source.id)
    )
    if clash:
        raise Duplicate("duplicate_url")
    ats, config = detect(url)
    source.url, source.ats_type, source.ats_config = url, ats, dict(config)
    source.last_check_at = source.last_success_at = None
    source.last_status, source.last_error = "never", None
    source.last_found = source.last_kept = None
    session.flush()
    return source


def add_contact(
    session: Session, company: Company, email: str, name: str | None, origin: str = "manual"
) -> Contact:
    email = email.strip().lower()
    if session.scalar(
        select(Contact).where(Contact.company_id == company.id, Contact.email == email)
    ):
        raise Duplicate("duplicate_contact")
    contact = Contact(company_id=company.id, email=email, name=name or None, origin=origin)
    session.add(contact)
    session.flush()
    return contact


def import_directory(session: Session, parse: SheetParse) -> ImportResult:
    result = ImportResult()
    for row in parse.rows:
        company = session.scalar(select(Company).where(Company.name_key == name_key(row.company)))
        if company:
            result.companies_existing += 1
        else:
            company = create_company(session, row.company)
            result.companies_created += 1
        for url in row.urls:
            try:
                add_source(session, company, url)
                result.sources_created += 1
            except UnsafeUrl:
                result.unsafe_urls.append(url)
            except Duplicate:
                pass
        for email in row.emails:
            try:
                add_contact(session, company, email, None, origin="sheet")
                result.contacts_created += 1
            except Duplicate:
                pass
    session.commit()
    return result
