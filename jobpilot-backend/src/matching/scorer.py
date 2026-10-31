import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

from src.config.settings import settings
from src.db.models import Job, Profile
from src.discovery.locations import match_location
from src.matching.roles import STOPWORDS, required_years, role_match, tokenize

VOCAB = [
    "python", "java", "c++", "c#", "javascript", "typescript", "react", "node", "sql", "docker",
    "kubernetes", "aws", "azure", "gcp", "google cloud", "git", "linux", "rest", "fastapi",
    "flask", "django", "pytorch", "tensorflow", "scikit-learn", "pandas", "numpy", "spark",
    "langchain", "llm", "rag", "graphrag", "neo4j", "generative ai", "genai", "machine learning",
    "deep learning", "nlp", "computer vision", "data analysis", "data structures", "algorithms",
    "system design", "dbms", "networking", "cybersecurity", "security", "vapt", "embedded",
    "iot", "postgresql", "mongodb", "redis", "kafka", "ci/cd", "devops", "microservices",
]
MAX_ADJ = 0.3


@dataclass
class ScoreResult:
    score: int
    filtered: bool
    reasons: list[str]
    features: list[str] = field(default_factory=list)


@lru_cache(maxsize=1)
def cv_skills() -> frozenset[str]:
    """Skills from the master CV's 'Technical Skills' line plus any vocab term in its text."""
    try:
        text = Path(str(settings.cv.main_tex)).read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return frozenset()
    skills = {s for s in VOCAB if _has(text.lower(), s)}
    m = re.search(r"Technical Skills:\}?\s*(.+?)\\\\", text, re.S)
    if m:
        skills |= {s.strip().lower() for s in m.group(1).split(",") if s.strip()}
    return frozenset(skills)


def _has(text: str, phrase: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(phrase)}(?![a-z0-9])", text) is not None


def job_features(job: Job, skills: list[str]) -> list[str]:
    feats = [f"title:{t}" for t in tokenize(job.title) if t not in STOPWORDS]
    feats.append(f"company:{job.company_id}")
    feats += [f"skill:{s}" for s in skills]
    return feats


def features_for(job: Job) -> list[str]:
    text = f"{job.title} {job.description or ''}".lower()
    mine = cv_skills()
    return job_features(job, [s for s in VOCAB if s in mine and _has(text, s)])


def score_job(job: Job, profile: Profile, weights: dict[str, float]) -> ScoreResult:
    title_toks = set(tokenize(job.title))
    banned = (*profile.exclude_title_words, *profile.hidden_title_words)
    blocked = title_toks & {w.lower() for w in banned}
    if blocked:
        return ScoreResult(0, True, [f"Filtered: title has '{sorted(blocked)[0]}'"])
    synonym = role_match(job.title)
    if not synonym:
        return ScoreResult(0, True, ["Filtered: title doesn't look like one of your roles"])
    loc = match_location(job.location, job.country, profile.locations, profile.include_remote)
    if not loc.ok:
        return ScoreResult(0, True, [f"Filtered: {loc.reason}"])
    years = required_years(job.description)
    if years is not None and years > profile.max_experience_years + 1:
        return ScoreResult(0, True, [f"Filtered: asks for {years}+ years"])

    reasons: list[str] = []
    text = f"{job.title} {job.description or ''}".lower()
    jd_skills = [s for s in VOCAB if _has(text, s)]
    mine = cv_skills()
    matched = [s for s in jd_skills if s in mine]
    if job.description:
        skill = len(matched) / max(4, len(jd_skills))
        base = 0.7 * skill + 0.3
        if matched:
            reasons.append("Matches your skills: " + ", ".join(matched[:5]))
        missing = [s for s in jd_skills if s not in mine][:3]
        if missing:
            reasons.append("Missing: " + ", ".join(missing))
    else:
        base = 0.45
        reasons.append("No description yet — score based on title")
    if job.ai_score is not None:  # Qwen read the job against the CV: weigh it equally
        base = 0.5 * base + 0.5 * job.ai_score / 100
        reasons.insert(0, f"AI: {job.ai_reason}" if job.ai_reason else "AI-assessed")
    reasons.append(f"Title fits '{synonym}'")

    feats = job_features(job, matched)
    adj = max(-MAX_ADJ, min(MAX_ADJ, sum(weights.get(f, 0.0) for f in feats)))
    if abs(adj) > 0.005:
        reasons.append(f"Learned from your feedback ({'+' if adj > 0 else '−'})")
    score = round(100 * max(0.0, min(1.0, base + adj)))
    return ScoreResult(score, False, reasons[:4], feats)
