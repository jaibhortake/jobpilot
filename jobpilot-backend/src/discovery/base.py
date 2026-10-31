from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from datetime import datetime
from typing import ClassVar, Protocol

import httpx

from src.db.models import AtsType, CareerSource


@dataclass
class JobPostingIn:
    external_id: str
    title: str
    url: str | None
    location: str | None = None
    country: str | None = None
    remote: bool = False
    posted_at: datetime | None = None
    posted_text: str | None = None
    description: str | None = None


@dataclass
class SearchQuery:
    keywords: list[str]
    locations: list[str]
    max_age_days: int = 30
    since: datetime | None = None  # last successful check of this source


@dataclass
class FetchResult:
    postings: list[JobPostingIn] = field(default_factory=list)
    complete: bool = True
    found_raw: int = 0
    page_kind: str = "listing"


Cancel = Callable[[], Awaitable[bool]]


class SourceReader(Protocol):
    ats_type: ClassVar[AtsType]

    async def fetch(
        self, source: CareerSource, client: httpx.AsyncClient, query: SearchQuery, cancel: Cancel
    ) -> FetchResult: ...
