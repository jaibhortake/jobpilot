"""Import a pasted email list (as copied from a mail client) into the contacts table."""

import re
import unicodedata
from dataclasses import dataclass, field

import tldextract
from sqlalchemy import select
from sqlalchemy.orm import Session

from src.db.models import Company, Contact
from src.directory import service

OTHER = service.OTHER
FREE_MAIL = {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com"}
_EMAIL = r"[\w.+\-]+@[\w\-]+(?:\.[\w\-]+)+"
_ANGLE = re.compile(rf'(?:"([^"]*)"|([^,<>"]*?))\s*<\s*({_EMAIL})\s*>')
_extract = tldextract.TLDExtract(suffix_list_urls=())  # bundled suffix list, no network


@dataclass
class ParsedEmail:
    email: str
    name: str | None


@dataclass
class BulkResult:
    added: int = 0
    duplicates: int = 0
    companies_created: int = 0
    by_company: dict[str, int] = field(default_factory=dict)
    other_domains: list[str] = field(default_factory=list)


def _clean_name(raw: str | None, email: str) -> str | None:
    if not raw:
        return None
    name = re.sub(r"\(.*?\)", "", raw).strip(" \"'")
    if not name or "@" in name:
        return None
    if "," in name:  # "Last, First"
        last, _, first = name.partition(",")
        name = f"{first.strip()} {last.strip()}"
    if name.isupper():
        name = name.title()
    return re.sub(r"\s+", " ", name) or None


def parse_pasted(text: str) -> list[ParsedEmail]:
    text = unicodedata.normalize("NFKC", text)  # folds styled letters (𝐧𝐞𝐡𝐚 -> neha)
    out: dict[str, ParsedEmail] = {}
    for m in _ANGLE.finditer(text):
        email = m.group(3).lower()
        name = _clean_name(m.group(1) or m.group(2), email)
        out.setdefault(email, ParsedEmail(email, name))
    rest = _ANGLE.sub(" ", text)
    for e in re.findall(_EMAIL, rest):
        out.setdefault(e.lower(), ParsedEmail(e.lower(), None))
    return list(out.values())


def registrable_label(domain: str) -> str:
    """qti.qualcomm.com -> qualcomm, sisc.in.sony.com.sg -> sony."""
    return (_extract(domain).domain or domain.split(".")[0]).lower()


def _norm(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", s.lower())


def match_company(label: str, companies: list[Company]) -> Company | None:
    """Unique company whose name equals / starts with / is started by the domain label."""
    lab = _norm(label)
    if not lab:
        return None
    for test in (
        lambda n: n == lab,  # exact, any length (hp, bp)
        lambda n: len(n) >= 3 and len(lab) >= 3 and lab.startswith(n),
        lambda n: len(lab) >= 3 and n.startswith(lab),
    ):
        hits = [c for c in companies if test(_norm(c.name))]
        if len(hits) == 1:
            return hits[0]
        if hits:  # ambiguous at this level: don't guess
            return None
    return None


def import_pasted(
    session: Session, text: str, aliases: dict[str, str] | None = None
) -> BulkResult:
    result = BulkResult()
    companies = list(session.scalars(select(Company)))
    alias = {d.lower(): n for d, n in (aliases or {}).items()}
    # domains already seen on stored contacts keep their company (learned, not hardcoded)
    known = {
        c.email.rsplit("@", 1)[1]: c.company for c in session.scalars(select(Contact))
        if c.company.name != OTHER and c.email.rsplit("@", 1)[1] not in FREE_MAIL
    }
    other: Company | None = next((c for c in companies if c.name == OTHER), None)
    for p in parse_pasted(text):
        domain = p.email.rsplit("@", 1)[1]
        company: Company | None = None
        if domain in alias:
            company = next((c for c in companies if _norm(c.name) == _norm(alias[domain])), None)
        company = company or known.get(domain)
        if company is None and domain not in FREE_MAIL:
            company = match_company(registrable_label(domain), companies)
        if company is None:
            if other is None:
                other = service.create_company(session, OTHER)
                companies.append(other)
                result.companies_created += 1
            company = other
            if domain not in result.other_domains:
                result.other_domains.append(domain)
        try:
            service.add_contact(session, company, p.email, p.name, origin="verified")
        except service.Duplicate:
            result.duplicates += 1
            continue
        if company.name != OTHER and domain not in FREE_MAIL:
            known.setdefault(domain, company)
        result.added += 1
        result.by_company[company.name] = result.by_company.get(company.name, 0) + 1
    session.commit()
    return result
