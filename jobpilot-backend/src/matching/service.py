import math
from collections import defaultdict

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from src.config.settings import settings
from src.db.models import FeatureWeight, Feedback, Job, JobScore, JobStatus, Profile
from src.matching.scorer import features_for, score_job


def get_profile(session: Session) -> Profile:
    p = session.get(Profile, 1)
    if p is None:
        d = settings.discovery
        p = Profile(
            id=1, role_keywords=list(d.keywords), locations=list(d.locations),
            include_remote=True, max_experience_years=2,
            exclude_title_words=["senior", "sr", "lead", "principal", "staff", "manager",
                                 "director", "head", "architect", "vp"],
            hidden_title_words=[],
        )
        session.add(p)
        session.commit()
    return p


def _weights(session: Session) -> dict[str, float]:
    return {w.feature: w.weight for w in session.scalars(select(FeatureWeight))}


def rebuild_weights(session: Session) -> None:
    """Weights are derived from scratch from all thumbs: 0.06 * sum(value) / sqrt(n), clamp 0.15."""
    sums: dict[str, float] = defaultdict(float)
    counts: dict[str, int] = defaultdict(int)
    for fb in session.scalars(select(Feedback)):
        job = session.get(Job, fb.job_id)
        if not job:
            continue
        for f in set(features_for(job)):
            sums[f] += fb.value
            counts[f] += 1
    session.execute(delete(FeatureWeight))
    for f, total in sums.items():
        w = max(-0.15, min(0.15, 0.06 * total / math.sqrt(counts[f])))
        if abs(w) > 1e-9:
            session.add(FeatureWeight(feature=f, weight=w))
    session.commit()


def rescore_all(session: Session) -> int:
    profile = get_profile(session)
    weights = _weights(session)
    session.execute(delete(JobScore))
    jobs = list(session.scalars(select(Job).where(Job.status != JobStatus.closed)))
    for job in jobs:
        r = score_job(job, profile, weights)
        session.add(JobScore(job_id=job.id, score=r.score, filtered=r.filtered, reasons=r.reasons))
    session.commit()
    return len(jobs)
