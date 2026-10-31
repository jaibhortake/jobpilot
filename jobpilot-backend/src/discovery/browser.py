import asyncio
from dataclasses import dataclass
from urllib.parse import urljoin

from src.common.urls import UnsafeUrl, safe_http_url


@dataclass
class Link:
    text: str
    href: str


@dataclass
class RenderedPage:
    final_url: str
    title: str
    text: str
    links: list[Link]


def _render_sync(url: str) -> RenderedPage:
    # Playwright's sync API runs in its own thread, so it never needs the server's event loop
    # (asyncio subprocess support is missing on some Windows loops).
    from playwright.sync_api import Error, sync_playwright
    from playwright.sync_api import TimeoutError as PwTimeout

    with sync_playwright() as pw:
        browser = pw.chromium.launch(headless=True)
        try:
            page = browser.new_page()
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            try:
                page.wait_for_load_state("networkidle", timeout=10000)
            except PwTimeout:
                pass  # continue with the DOM so far
            try:
                text = page.inner_text("body")
            except Error:
                text = ""
            raw = page.eval_on_selector_all(
                "a[href]", "els => els.map(e => [e.innerText.trim(), e.getAttribute('href')])"
            )
            links: list[Link] = []
            for label, href in raw:
                try:
                    links.append(Link(label[:120], safe_http_url(urljoin(page.url, href))))
                except UnsafeUrl:
                    continue
            return RenderedPage(page.url, page.title(), text, links)
        finally:
            browser.close()


async def render_page(url: str) -> RenderedPage:
    return await asyncio.to_thread(_render_sync, safe_http_url(url))
