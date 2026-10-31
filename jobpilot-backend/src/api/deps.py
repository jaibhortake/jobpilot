from sqlalchemy import text

from src.db.session import get_engine


async def db_ok() -> bool:
    """True when the database answers SELECT 1; never raises (health must always respond)."""
    try:
        with get_engine().connect() as conn:
            conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False
