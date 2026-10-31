import os
import time

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from src.config.settings import settings
from src.llm import router as llm
from src.llm.errors import LlmError

router = APIRouter()


def _configured(var: str) -> bool:
    return bool(os.environ.get(var) or settings.get(var))


async def _ollama() -> dict[str, object]:
    base = os.environ.get("OLLAMA_API_BASE") or settings.get("OLLAMA_API_BASE", "")
    try:
        async with httpx.AsyncClient(timeout=2) as c:
            r = await c.get(f"{base}/api/tags")
        return {"reachable": True, "models": [m["name"] for m in r.json().get("models", [])]}
    except Exception:
        return {"reachable": False, "models": []}


@router.get("/settings/llm")
async def get_llm() -> dict[str, object]:
    return {
        "active_preset": llm.active_preset(),
        "presets": {k: dict(v) for k, v in settings.llm.presets.items()},
        "providers": {
            "groq": {"configured": _configured("GROQ_API_KEY")},
            "anthropic": {"configured": _configured("ANTHROPIC_API_KEY")},
            "ollama": await _ollama(),
        },
    }


class LlmIn(BaseModel):
    active_preset: str | None = None
    overrides: dict[str, str] | None = None


@router.put("/settings/llm")
async def put_llm(body: LlmIn) -> dict[str, object]:
    if body.active_preset and body.active_preset not in settings.llm.presets:
        body.active_preset = None
    llm.set_state(body.active_preset, body.overrides)
    return await get_llm()


class TestIn(BaseModel):
    task: llm.LlmTask


@router.post("/settings/llm/test")
async def test_llm(body: TestIn) -> dict[str, object]:
    start = time.monotonic()
    model = llm.model_for(body.task)
    try:
        await llm.complete(body.task, [{"role": "user", "content": "Reply with the word OK."}],
                           max_tokens=20)
    except LlmError as exc:
        return {"ok": False, "model": model, "ms": 0, "error": str(exc)[:300]}
    return {"ok": True, "model": model, "ms": int((time.monotonic() - start) * 1000)}
