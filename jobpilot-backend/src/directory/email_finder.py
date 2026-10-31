"""Guess a person's work email from the company's email domain and known address patterns.

No mail is sent and no server is probed: results are guesses ranked by how well each pattern
fits the addresses already stored for that company.
"""

import re
import socket
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass

from src.db.models import Company

FREE_MAIL = {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "proton.me", "icloud.com"}
GENERIC_LOCALS = ["careers", "jobs", "hr", "recruitment", "talent", "hiring"]

# pattern name -> builder(first, last)
PATTERNS: dict[str, Callable[[str, str], str]] = {
    "first.last": lambda first, last: f"{first}.{last}",
    "firstlast": lambda first, last: f"{first}{last}",
    "flast": lambda first, last: f"{first[0]}{last}",
    "first": lambda first, last: first,
    "first_last": lambda first, last: f"{first}_{last}",
    "f.last": lambda first, last: f"{first[0]}.{last}",
    "last.first": lambda first, last: f"{last}.{first}",
    "firstl": lambda first, last: f"{first}{last[0]}",
}


@dataclass
class Guess:
    email: str
    pattern: str
    confidence: str  # inferred (matches this company's known addresses) / common / generic
    note: str = ""


def _clean(s: str) -> str:
    return re.sub(r"[^a-z]", "", s.lower())


def split_name(full_name: str) -> tuple[str, str] | None:
    parts = [_clean(p) for p in full_name.split() if _clean(p)]
    if len(parts) < 2:
        return None
    return parts[0], parts[-1]


def company_domain(company: Company) -> str | None:
    """Explicit domain first, else the most common non-free-mail domain among its contacts."""
    if company.domain:
        return company.domain.lower()
    counts = Counter(
        c.email.rsplit("@", 1)[1] for c in company.contacts
        if "@" in c.email and c.email.rsplit("@", 1)[1] not in FREE_MAIL
    )
    return counts.most_common(1)[0][0] if counts else None


def infer_patterns(company: Company, domain: str) -> Counter[str]:
    """Which patterns fit the company's named contacts at this domain."""
    hits: Counter[str] = Counter()
    for c in company.contacts:
        if not c.name or not c.email.endswith("@" + domain):
            continue
        names = split_name(c.name)
        if not names:
            continue
        local = c.email.split("@", 1)[0].lower()
        for pname, build in PATTERNS.items():
            if build(*names) == local:
                hits[pname] += 1
    return hits


def domain_resolves(domain: str) -> bool:
    try:
        socket.getaddrinfo(domain, None)
        return True
    except OSError:
        return False


def find_emails(company: Company, full_name: str | None) -> tuple[str | None, list[Guess]]:
    domain = company_domain(company)
    if not domain:
        return None, []
    guesses: list[Guess] = []
    names = split_name(full_name) if full_name else None
    if names:
        inferred = infer_patterns(company, domain)
        order = [p for p, _ in inferred.most_common()] + [p for p in PATTERNS if p not in inferred]
        for pname in order:
            local = PATTERNS[pname](*names)
            guesses.append(Guess(
                f"{local}@{domain}", pname,
                "inferred" if pname in inferred else "common",
                f"matches {inferred[pname]} known address(es)" if pname in inferred else "",
            ))
    guesses += [Guess(f"{g}@{domain}", g, "generic", "role address") for g in GENERIC_LOCALS]
    return domain, guesses
