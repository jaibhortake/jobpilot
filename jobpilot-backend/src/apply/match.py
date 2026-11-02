"""Match application-form fields to the applicant's details and saved answers.

Order: applicant details by label synonyms (high), answer bank exact (high), answer bank by
token overlap (medium), else unknown (low). Free-text drafting is done by the caller.
"""

import re

from pydantic import BaseModel

# detail key -> label phrases (token sequences) that identify it
SYNONYMS: dict[str, list[str]] = {
    "first_name": ["first name", "given name", "firstname"],
    "last_name": ["last name", "surname", "family name", "lastname"],
    "full_name": ["full name", "name", "your name", "legal name"],
    "email": ["email", "email address", "e mail"],
    "phone": ["phone", "mobile", "mobile number", "phone number", "contact number"],
    "city": ["city", "current city", "current location", "location"],
    "country": ["country"],
    "linkedin": ["linkedin", "linkedin profile", "linkedin url"],
    "github": ["github", "github url"],
    "portfolio": ["website", "portfolio", "personal website"],
    "college": ["college", "university", "school", "institution"],
    "degree": ["degree", "qualification"],
    "graduation_year": ["graduation year", "year of graduation", "passing year"],
    "cgpa": ["cgpa", "gpa", "percentage"],
    "experience_years": ["years of experience", "total experience", "experience years"],
    "current_ctc": ["current ctc", "current salary", "current compensation"],
    "expected_ctc": ["expected ctc", "expected salary", "salary expectation"],
    "notice_period": ["notice period"],
    "work_authorization": ["authorized to work", "work authorization"],
    "gender": ["gender"],
}
DETAIL_KEYS = list(SYNONYMS)
_NOISE = re.compile(r"[^a-z0-9 ]+")
STOP = {"the", "a", "an", "you", "your", "are", "do", "to", "of", "in", "for", "is", "please",
        "what", "how", "and", "or", "if", "any", "this", "with", "on"}


class FieldIn(BaseModel):
    id: str
    label: str
    kind: str = "text"  # text, textarea, select, radio, checkbox, file
    options: list[str] = []


class FieldOut(BaseModel):
    id: str
    value: str | None
    confidence: str  # high / medium / low
    source: str  # profile / answer / llm / none


def norm_question(text: str) -> str:
    return " ".join(_NOISE.sub(" ", text.lower()).split())


def is_detail_question(text: str) -> bool:
    """True for labels that are just a personal detail ("Email", "Phone number")."""
    label = norm_question(text)
    return any(label == p for phrases in SYNONYMS.values() for p in phrases)


def _tokens(text: str) -> set[str]:
    return {t for t in norm_question(text).split() if t not in STOP}


def _has_phrase(label: str, phrase: str) -> bool:
    return f" {phrase} " in f" {label} "


def _detail_for(label: str, details: dict[str, str]) -> str | None:
    best: tuple[int, str] | None = None
    for key, phrases in SYNONYMS.items():
        for p in phrases:
            if _has_phrase(label, p) and details.get(key) and (best is None or len(p) > best[0]):
                best = (len(p), key)
    if best is None:
        return None
    # a bare "name" label must not win when the label is about something else (company name)
    if best[1] == "full_name" and len(label.split()) > 3:
        return None
    return details[best[1]]


def _pick_option(value: str, options: list[str]) -> str | None:
    if not options:
        return value
    v = norm_question(value)
    for o in options:
        if norm_question(o) == v:
            return o
    for o in options:
        if v and (v in norm_question(o) or norm_question(o) in v):
            return o
    return None


def match_field(field: FieldIn, details: dict[str, str], bank: dict[str, str]) -> FieldOut:
    label = norm_question(field.label)

    def out(value: str | None, conf: str, src: str) -> FieldOut:
        if value is not None and field.kind in ("select", "radio"):
            value = _pick_option(value, field.options)
            if value is None:
                return FieldOut(id=field.id, value=None, confidence="low", source="none")
        return FieldOut(id=field.id, value=value, confidence=conf, source=src)

    if field.kind != "textarea" and (v := _detail_for(label, details)) is not None:
        return out(v, "high", "profile")
    if label in bank:
        return out(bank[label], "high", "answer")
    want = _tokens(label)
    best, best_score = None, 0.0
    for q, a in bank.items():
        have = _tokens(q)
        if not want or not have:
            continue
        score = len(want & have) / len(want | have)
        if score > best_score:
            best, best_score = a, score
    if best is not None and best_score >= 0.5:
        return out(best, "medium", "answer")
    return FieldOut(id=field.id, value=None, confidence="low", source="none")
