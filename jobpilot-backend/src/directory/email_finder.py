"""Guess a person's work email, learning how each domain forms addresses from stored emails.

Nothing here encodes "company X uses pattern Y". The only fixed part is the vocabulary of ways a
name can be composed (first.last, flast, ...). Which of those a domain uses, what counts as a
role mailbox, and the global fallback order are all computed from the contacts you have stored,
so every address you add changes the next guess. No mail is sent and no server is probed.
"""

import re
import socket
from collections import Counter, defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass

from src.db.models import Company, Contact

FREE_MAIL = {"gmail.com", "yahoo.com", "outlook.com", "hotmail.com", "proton.me", "icloud.com"}

# How a name can be composed into a local part. A vocabulary, not a per-company rule.
BUILDERS: dict[str, Callable[[str, str], str]] = {
    "first.last": lambda first, last: f"{first}.{last}",
    "first_last": lambda first, last: f"{first}_{last}",
    "first-last": lambda first, last: f"{first}-{last}",
    "firstlast": lambda first, last: f"{first}{last}",
    "flast": lambda first, last: f"{first[0]}{last}",
    "f.last": lambda first, last: f"{first[0]}.{last}",
    "first": lambda first, last: first,
    "firstl": lambda first, last: f"{first}{last[0]}",
    "last.first": lambda first, last: f"{last}.{first}",
}
_SEP_SHAPE = {".": "first.last", "_": "first_last", "-": "first-last"}


@dataclass
class Guess:
    email: str
    pattern: str
    confidence: str  # learned / common / role
    note: str = ""


def _clean(s: str) -> str:
    return re.sub(r"[^a-z]", "", s.lower())


def split_name(full_name: str) -> tuple[str, str] | None:
    parts = [_clean(p) for p in full_name.split() if _clean(p)]
    return (parts[0], parts[-1]) if len(parts) >= 2 else None


def _tokens(local: str) -> list[str]:
    return [t for t in re.split(r"[._\-]+", re.sub(r"\d+", "", local.lower())) if t]


def _split(email: str) -> tuple[str, str]:
    local, _, domain = email.lower().partition("@")
    return local, domain


@dataclass
class Corpus:
    """Everything learned from the stored contacts."""

    by_domain: dict[str, list[tuple[str, str | None]]]  # domain -> [(local, name)]
    role_tokens: set[str]
    role_domains: dict[str, int]
    first_len: float
    last_len: float

    @classmethod
    def build(cls, contacts: Iterable[Contact]) -> "Corpus":
        by_domain: dict[str, list[tuple[str, str | None]]] = defaultdict(list)
        for c in contacts:
            local, domain = _split(c.email)
            if domain and domain not in FREE_MAIL:
                by_domain[domain].append((local, c.name))
        # a role mailbox is a whole local part reused by several different domains
        # (careers@, hr@, recruitment@ ...); real people don't share locals across companies
        doms_per_local: dict[str, set[str]] = defaultdict(set)
        for dom, items in by_domain.items():
            for local, _ in items:
                doms_per_local[local].add(dom)
        role_tokens = {lo for lo, ds in doms_per_local.items() if len(ds) >= 2}
        # typical token lengths of separated "first<sep>last" addresses, to size compact ones
        firsts, lasts = [], []
        for items in by_domain.values():
            for local, _ in items:
                toks = _tokens(local)
                if len(toks) == 2 and local not in role_tokens and len(toks[0]) > 1:
                    firsts.append(len(toks[0]))
                    lasts.append(len(toks[1]))
        return cls(
            dict(by_domain), role_tokens, {lo: len(ds) for lo, ds in doms_per_local.items()},
            sum(firsts) / len(firsts) if firsts else 5.0,
            sum(lasts) / len(lasts) if lasts else 6.0,
        )

    def is_role(self, local: str) -> bool:
        return local in self.role_tokens

    def _compact_shape(self, locals_: list[str]) -> str:
        """Pick flast / firstlast / first for a domain whose addresses have no separator,
        by which expected length is closest to what the domain actually shows."""
        mean = sum(len(_clean(x)) for x in locals_) / len(locals_)
        expected = {
            "flast": 1 + self.last_len,
            "firstlast": self.first_len + self.last_len,
            "first": self.first_len,
        }
        return min(expected, key=lambda k: abs(expected[k] - mean))

    def domain_shapes(self, domain: str) -> Counter[str]:
        items = [(lo, nm) for lo, nm in self.by_domain.get(domain, []) if not self.is_role(lo)]
        shapes: Counter[str] = Counter()
        compact: list[str] = []
        for local, name in items:
            names = split_name(name) if name else None
            exact = [p for p, b in BUILDERS.items() if names and b(*names) == local]
            if exact:  # a known name pins the shape exactly
                shapes[exact[0]] += 1
                continue
            toks = _tokens(local)
            sep = next((ch for ch in "._-" if ch in local), None)
            if len(toks) == 2 and sep:
                shapes["f.last" if sep == "." and len(toks[0]) == 1 else _SEP_SHAPE[sep]] += 1
            elif len(toks) == 1:
                compact.append(local)
        if compact:
            shapes[self._compact_shape(compact)] += len(compact)
        return shapes

    def global_shapes(self) -> Counter[str]:
        total: Counter[str] = Counter()
        for d in self.by_domain:
            total.update(self.domain_shapes(d))
        return total

    def role_locals(self, domain: str) -> list[str]:
        return [lo for lo, _ in self.by_domain.get(domain, []) if self.is_role(lo)]

    def global_roles(self) -> list[str]:
        """Role locals ranked by how many different domains use them."""
        return sorted(self.role_tokens, key=lambda lo: -self.role_domains[lo])


def domain_resolves(domain: str) -> bool:
    try:
        socket.getaddrinfo(domain, None)
        return True
    except OSError:
        return False


def company_domain(company: Company) -> str | None:
    if company.domain:
        return company.domain.lower()
    counts = Counter(
        _split(c.email)[1] for c in company.contacts if _split(c.email)[1] not in FREE_MAIL
    )
    return counts.most_common(1)[0][0] if counts else None


def find_emails(
    company: Company, full_name: str | None, all_contacts: Iterable[Contact],
    domain: str | None = None,
) -> tuple[str | None, list[Guess]]:
    domain = (domain or company_domain(company) or "").lower() or None
    if not domain:
        return None, []
    corpus = Corpus.build(all_contacts)
    guesses: list[Guess] = []
    seen: set[str] = set()

    def add(local: str, pattern: str, confidence: str, note: str = "") -> None:
        email = f"{local}@{domain}"
        if local and email not in seen:
            seen.add(email)
            guesses.append(Guess(email, pattern, confidence, note))

    names = split_name(full_name) if full_name else None
    if names:
        learned = corpus.domain_shapes(domain)
        fallback = corpus.global_shapes()
        for shape, n in learned.most_common():
            note = f"{n} address(es) at {domain} look like this"
            add(BUILDERS[shape](*names), shape, "learned", note)
        for shape, _n in fallback.most_common():
            add(BUILDERS[shape](*names), shape, "common", "common across your list")
        for shape in BUILDERS:  # anything never seen in your data goes last
            add(BUILDERS[shape](*names), shape, "common", "not seen in your list")
    for lo in corpus.role_locals(domain):
        add(lo, "role", "learned", "stored role address")
    for lo in corpus.global_roles():
        add(lo, "role", "role", "role address used by other companies in your list")
    return domain, guesses
