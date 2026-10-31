import os
from pathlib import Path

from dynaconf import Dynaconf

_BACKEND_DIR = Path(__file__).resolve().parents[2]

settings = Dynaconf(
    settings_files=[str(_BACKEND_DIR / "settings.toml")],
    load_dotenv=True,
    dotenv_path=str(_BACKEND_DIR / ".env"),
    environments=False,
    envvar_prefix=False,
)


def database_url() -> str:
    url = os.environ.get("DATABASE_URL") or settings.get("DATABASE_URL")
    if not url:
        raise RuntimeError("DATABASE_URL not set")
    return url
