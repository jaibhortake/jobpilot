import asyncio
import os
from dataclasses import dataclass
from typing import Protocol

import httpx


@dataclass
class SearchHit:
    title: str
    url: str
    snippet: str


class SearchProvider(Protocol):
    async def search(self, q: str, n: int) -> list[SearchHit]: ...


class DdgsProvider:
    async def search(self, q: str, n: int) -> list[SearchHit]:
        def run() -> list[SearchHit]:
            from ddgs import DDGS

            return [
                SearchHit(r.get("title", ""), r.get("href", ""), r.get("body", ""))
                for r in DDGS().text(q, max_results=n)
            ]

        return await asyncio.to_thread(run)


class BraveProvider:
    def __init__(self, key: str) -> None:
        self.key = key

    async def search(self, q: str, n: int) -> list[SearchHit]:
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(
                "https://api.search.brave.com/res/v1/web/search",
                params={"q": q, "count": n}, headers={"X-Subscription-Token": self.key},
            )
            r.raise_for_status()
        return [
            SearchHit(x["title"], x["url"], x.get("description", ""))
            for x in r.json().get("web", {}).get("results", [])
        ]


def get_search_provider() -> SearchProvider:
    from src.config.settings import settings

    key = os.environ.get("BRAVE_API_KEY") or settings.get("BRAVE_API_KEY")
    return BraveProvider(key) if key else DdgsProvider()
