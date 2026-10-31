import re

_TOKEN = re.compile(r"c\+\+|c#|\.net|[a-z0-9]+")

STOPWORDS = {
    "engineer", "software", "developer", "i", "ii", "iii", "intern", "india", "remote", "the",
    "and", "of", "for", "with", "jr", "junior", "associate", "graduate", "trainee", "new",
}

_DOMAINS = {
    "software", "ml", "ai", "data", "backend", "frontend", "full", "stack", "platform", "security",
    "cloud", "devops", "genai", "llm", "research", "application", "python", "java", "sde", "swe",
}
_SINGLE = {"developer", "sde", "swe", "ml", "ai", "genai", "llm", "nlp", "programmer"}
_PHRASES = [
    "data scientist", "data analyst", "data engineer", "machine learning", "computer vision",
    "security analyst", "security engineer", "research scientist", "applied scientist",
    "software engineer", "software developer",
]


def tokenize(s: str) -> list[str]:
    return _TOKEN.findall(s.lower())


def role_match(title: str) -> str | None:
    """Return the matching role synonym, or None. A bare 'Engineer' does not match."""
    low = " ".join(tokenize(title))
    for p in _PHRASES:
        if p in low:
            return p
    toks = set(tokenize(title))
    hit = toks & _SINGLE
    if hit:
        return sorted(hit)[0]
    if "engineer" in toks and toks & _DOMAINS:
        return "engineer " + sorted(toks & _DOMAINS)[0]
    return None


_EXP_A = re.compile(
    r"(\d+)\s*\+?\s*(?:[-–]|to)?\s*(\d+)?\s*(?:years?|yrs?)\s+(?:of\s+)?(?:\w+\s+){0,3}?experience",
    re.I,
)
_EXP_B = re.compile(
    r"experience\s*[:\-]?\s*(\d+)\s*\+?\s*(?:[-–]|to)?\s*(\d+)?\s*(?:years?|yrs?)", re.I
)


_EXP_C = re.compile(r"(\d+)\s*\+\s*(?:years?|yrs?)", re.I)


def required_years(description: str | None) -> int | None:
    """Lower bound of the first stated experience requirement."""
    if not description:
        return None
    found = (p.search(description) for p in (_EXP_A, _EXP_B, _EXP_C))
    hits = [m for m in found if m]
    if not hits:
        return None
    return int(min(hits, key=lambda m: m.start()).group(1))
