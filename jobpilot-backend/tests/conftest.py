"""Test bootstrap.

Runs before any ``src`` import: if TEST_DATABASE_URL is set, every test (including
background tasks that build their own session) is pointed at it, and a URL that does
not look like a test database is refused so the dev database can never be truncated.
"""

import os

from src.config.settings import settings  # noqa: E402  (reads .env only; no DB is opened)

_test_url = os.environ.get("TEST_DATABASE_URL") or settings.get("TEST_DATABASE_URL")
if _test_url:
    if not _test_url.rsplit("/", 1)[-1].split("?")[0].endswith("_test"):
        raise RuntimeError("TEST_DATABASE_URL must point at a database whose name ends in _test")
    os.environ["DATABASE_URL"] = _test_url
