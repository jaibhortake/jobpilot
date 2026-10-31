from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from src.config.settings import database_url


@lru_cache(maxsize=1)
def get_engine() -> Engine:
    """Built lazily so tests can set DATABASE_URL before the first use."""
    return create_engine(database_url(), pool_pre_ping=True)


def SessionLocal() -> Session:  # noqa: N802  (name kept for parity with the plan)
    return sessionmaker(bind=get_engine(), expire_on_commit=False)()


def get_session() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
