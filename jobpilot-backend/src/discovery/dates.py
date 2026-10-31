import re
from datetime import UTC, datetime, timedelta


def parse_posted(text: str | int | float | None, now: datetime | None = None) -> datetime | None:
    now = now or datetime.now(UTC)
    if text is None or text == "":
        return None
    if isinstance(text, int | float):
        return datetime.fromtimestamp(text / 1000 if text > 1e11 else text, UTC)
    s = str(text).strip().lower()
    if "today" in s:
        return now
    if "yesterday" in s:
        return now - timedelta(days=1)
    m = re.search(r"(\d+)\+?\s*days?\s*ago", s)
    if m:
        return now - timedelta(days=int(m.group(1)))
    try:
        dt = datetime.fromisoformat(str(text).strip().replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
