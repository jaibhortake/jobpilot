import asyncio
import ssl
from collections import defaultdict
from typing import Any
from urllib.parse import urlsplit

import httpx

from src.config.settings import settings

USER_AGENT = "JobPilot/0.1 (personal job search)"
_total = asyncio.Semaphore(int(settings.http.total))
_hosts: dict[str, asyncio.Semaphore] = defaultdict(lambda: asyncio.Semaphore(1))


class SourceFetchError(Exception):
    pass


def get_client() -> httpx.AsyncClient:
    # system trust store (Windows cert store), so TLS-inspecting proxies don't break requests
    return httpx.AsyncClient(
        verify=ssl.create_default_context(),
        timeout=float(settings.http.timeout),
        headers={"User-Agent": USER_AGENT, "Accept": "application/json, text/html"},
        follow_redirects=True,
    )


async def request_with_retry(
    client: httpx.AsyncClient, method: str, url: str, **kw: Any
) -> httpx.Response:
    host = urlsplit(url).hostname or ""
    last: Exception | None = None
    for attempt in range(int(settings.http.retries)):
        try:
            async with _total, _hosts[host]:
                resp = await client.request(method, url, **kw)
            if resp.status_code in (429, 500, 502, 503, 504):
                last = SourceFetchError(f"HTTP {resp.status_code} from {host}")
            else:
                if resp.status_code >= 400:
                    raise SourceFetchError(f"HTTP {resp.status_code} from {host}")
                return resp
        except httpx.HTTPError as exc:
            last = SourceFetchError(f"{type(exc).__name__} contacting {host}")
        await asyncio.sleep(2**attempt)
    raise last or SourceFetchError(f"request to {host} failed")
