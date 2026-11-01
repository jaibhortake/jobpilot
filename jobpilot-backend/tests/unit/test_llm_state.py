from pathlib import Path

import pytest

from src.llm import router


@pytest.fixture(autouse=True)
def isolated_state(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(router, "STATE_FILE", tmp_path / "llm_state.json")
    monkeypatch.setattr(router, "_state", {"preset": None, "overrides": {}})


def test_chosen_preset_is_saved_and_reloaded() -> None:
    router.set_state("local", None)
    assert router.model_for("extract").startswith("ollama/")
    router._state.update(preset=None, overrides={})  # as after a restart
    assert router.active_preset() == "free"
    router._load_state()
    assert router.active_preset() == "local"


def test_unknown_or_corrupt_saved_state_is_ignored() -> None:
    router.STATE_FILE.write_text('{"preset": "nope", "overrides": 3}', encoding="utf-8")
    router._load_state()
    assert router.active_preset() == "free"
    router.STATE_FILE.write_text("not json", encoding="utf-8")
    router._load_state()
    assert router.active_preset() == "free"


def test_ollama_calls_ask_to_keep_the_model_loaded() -> None:
    assert router.KEEP_ALIVE.endswith("m")
