import pytest

from src.db.models import Job, Profile
from src.matching.roles import required_years, role_match
from src.matching.scorer import score_job


@pytest.mark.parametrize(
    ("title", "ok"),
    [
        ("GenAI Engineer", True),
        ("Software Engineer II", True),
        ("Mechanical Engineer", False),
        ("Security Officer", False),
        ("Data Entry Operator", False),
        ("Maintenance Chain", False),
    ],
)
def test_role_match(title: str, ok: bool) -> None:
    assert bool(role_match(title)) is ok


@pytest.mark.parametrize(
    ("text", "years"),
    [
        ("1-3 years of experience", 1),
        ("5+ years of relevant experience", 5),
        ("Experience: 4-6 yrs", 4),
        ("5+ years overall including 2 years of Python experience", 5),
        ("founded 50 years ago", None),
    ],
)
def test_required_years(text: str, years: int | None) -> None:
    assert required_years(text) == years


def _profile() -> Profile:
    return Profile(
        id=1, role_keywords=[], locations=["India"], include_remote=True,
        max_experience_years=2, exclude_title_words=["senior", "sr"], hidden_title_words=[],
    )


def _job(title: str, desc: str | None = None, loc: str = "Pune, India") -> Job:
    return Job(id=1, company_id=1, external_id="x", title=title, location=loc, description=desc)


def test_senior_filtered() -> None:
    assert score_job(_job("Senior Software Engineer"), _profile(), {}).filtered


def test_experience_filtered_and_kept() -> None:
    senior = _job("Software Engineer", "5+ years of experience")
    junior = _job("Software Engineer", "0-2 years of experience")
    assert score_job(senior, _profile(), {}).filtered
    assert not score_job(junior, _profile(), {}).filtered


def test_feedback_adjustment_is_clamped() -> None:
    base = score_job(_job("Software Engineer"), _profile(), {})
    boosted = score_job(_job("Software Engineer"), _profile(), {"company:1": 5.0})
    assert boosted.score - base.score <= 30
