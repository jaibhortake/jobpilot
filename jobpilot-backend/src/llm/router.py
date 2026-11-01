import json
import os
import re
from pathlib import Path
from typing import Any, Literal, TypeVar, overload

from pydantic import BaseModel, ValidationError

from src.config.settings import settings
from src.llm.errors import LlmBadOutput, LlmUnavailable, RateLimited, RequestTooLarge

LlmTask = Literal["extract", "classify"]
T = TypeVar("T", bound=BaseModel)

# Preset name / per-task model overrides; the settings API writes these. They are saved to
# data/llm_state.json so the choice made in the UI survives a restart.
STATE_FILE = Path(__file__).resolve().parents[2] / "data" / "llm_state.json"
KEEP_ALIVE = "30m"  # how long Ollama keeps the model loaded after its last call
_state: dict[str, Any] = {"preset": None, "overrides": {}}


def _load_state() -> None:
    try:
        saved = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    preset = saved.get("preset")
    if isinstance(preset, str) and preset in settings.llm.presets:
        _state["preset"] = preset
    overrides = saved.get("overrides")
    if isinstance(overrides, dict):
        _state["overrides"] = {str(k): str(v) for k, v in overrides.items()}


def _save_state() -> None:
    try:
        STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
        STATE_FILE.write_text(json.dumps(_state), encoding="utf-8")
    except OSError:
        pass  # the choice still applies until the next restart


def active_preset() -> str:
    return str(_state["preset"] or settings.llm.active_preset)


def set_state(preset: str | None, overrides: dict[str, str] | None) -> None:
    if preset:
        _state["preset"] = preset
    if overrides is not None:
        _state["overrides"] = overrides
    _save_state()


_load_state()


def model_for(task: LlmTask) -> str:
    override = _state["overrides"].get(task)
    return str(override or settings.llm.presets[active_preset()][task])


def input_budget(task: LlmTask) -> int:
    family = model_for(task).split("/", 1)[0]
    return int(settings.llm.budgets.get(family, 12000))


def strip_think(text: str) -> str:
    """qwen3 emits reasoning ending in </think> even with think=false."""
    return text.rsplit("</think>", 1)[-1].strip()


def _first_json(text: str) -> str:
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise LlmBadOutput("no JSON object in reply")
    return m.group(0)


@overload
async def complete(
    task: LlmTask, messages: list[dict[str, str]], *, max_tokens: int = ...
) -> str: ...
@overload
async def complete(
    task: LlmTask, messages: list[dict[str, str]], *, schema: type[T], max_tokens: int = ...
) -> T: ...
async def complete(
    task: LlmTask, messages: list[dict[str, str]], *, schema: type[T] | None = None,
    max_tokens: int = 2000,
) -> str | T:
    # offline tokenizer cache (the download fails behind TLS inspection); must precede import
    cache = Path(__file__).resolve().parents[2] / "data" / "tiktoken"
    os.environ.setdefault("TIKTOKEN_CACHE_DIR", str(cache))
    os.environ.setdefault("CUSTOM_TIKTOKEN_CACHE_DIR", str(cache))
    os.environ.setdefault("LITELLM_LOCAL_MODEL_COST_MAP", "True")
    bundle = cache.parent / "ca-bundle.pem"  # Windows trusted roots (TLS-inspecting proxy)
    if bundle.exists():
        os.environ.setdefault("SSL_CERT_FILE", str(bundle))
        os.environ.setdefault("REQUESTS_CA_BUNDLE", str(bundle))
    import litellm
    model = model_for(task)
    kwargs: dict[str, Any] = {"model": model, "messages": list(messages), "max_tokens": max_tokens}
    if model.startswith("ollama/"):
        kwargs["api_base"] = os.environ.get("OLLAMA_API_BASE") or settings.get(
            "OLLAMA_API_BASE", "http://localhost:11434"
        )
        kwargs["extra_body"] = {"think": False, "keep_alive": KEEP_ALIVE}
    elif model.startswith("groq/"):
        kwargs["api_key"] = os.environ.get("GROQ_API_KEY") or settings.get("GROQ_API_KEY")
    elif model.startswith("anthropic/"):
        kwargs["api_key"] = os.environ.get("ANTHROPIC_API_KEY") or settings.get("ANTHROPIC_API_KEY")
    if schema is not None:
        kwargs["messages"] = [
            {"role": "system", "content": "Reply with one JSON object matching this schema, "
             "no prose: " + json.dumps(schema.model_json_schema())},
            *messages,
        ]
        if not model.startswith("ollama/"):
            kwargs["response_format"] = {"type": "json_object"}

    last: Exception | None = None
    for _ in range(2 if schema else 1):
        try:
            resp = await litellm.acompletion(**kwargs)
        except litellm.RateLimitError as exc:
            raise RateLimited(str(exc)) from exc
        except litellm.ContextWindowExceededError as exc:
            raise RequestTooLarge(str(exc)) from exc
        except (litellm.AuthenticationError, litellm.APIConnectionError) as exc:
            raise LlmUnavailable(str(exc)) from exc
        except litellm.APIError as exc:
            if getattr(exc, "status_code", None) == 413:
                raise RequestTooLarge(str(exc)) from exc
            raise LlmUnavailable(str(exc)) from exc
        except Exception as exc:  # provider-specific errors (e.g. server/connect failures)
            raise LlmUnavailable(f"{type(exc).__name__}: {str(exc)[:200]}") from exc
        text = strip_think(resp.choices[0].message.content or "")
        if schema is None:
            return text
        try:
            return schema.model_validate_json(_first_json(text))
        except (ValidationError, LlmBadOutput) as exc:
            last = exc
    raise LlmBadOutput(str(last))
