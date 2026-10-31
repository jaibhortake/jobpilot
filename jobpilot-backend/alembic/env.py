from alembic import context
from sqlalchemy import create_engine

from src.config.settings import database_url
from src.db import models  # noqa: F401  (registers tables)
from src.db.base import Base

target_metadata = Base.metadata


def run_migrations_online() -> None:
    engine = create_engine(database_url())
    with engine.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
