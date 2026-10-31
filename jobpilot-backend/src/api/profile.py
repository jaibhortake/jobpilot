from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.db.session import get_session
from src.matching import service

router = APIRouter()
SessionDep = Annotated[Session, Depends(get_session)]


class ProfileModel(BaseModel):
    role_keywords: list[str]
    locations: list[str]
    include_remote: bool
    max_experience_years: int
    exclude_title_words: list[str]
    hidden_title_words: list[str]


@router.get("/profile")
def get_profile(session: SessionDep) -> ProfileModel:
    p = service.get_profile(session)
    return ProfileModel(
        role_keywords=list(p.role_keywords), locations=list(p.locations),
        include_remote=p.include_remote, max_experience_years=p.max_experience_years,
        exclude_title_words=list(p.exclude_title_words),
        hidden_title_words=list(p.hidden_title_words),
    )


@router.put("/profile")
def put_profile(body: ProfileModel, session: SessionDep) -> ProfileModel:
    p = service.get_profile(session)
    for k, v in body.model_dump().items():
        setattr(p, k, [x.strip() for x in v if x.strip()] if isinstance(v, list) else v)
    session.commit()
    service.rescore_all(session)
    return get_profile(session)
