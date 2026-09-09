import pytest

import research_learning_state as state


def test_default_state_uses_persistent_store_when_configured(monkeypatch):
    expected = {
        "lessons": [{"fingerprint": "persisted"}],
        "updated_at": "2026-09-09T00:00:00+00:00",
        "conclusive_trial_count": 11,
    }
    monkeypatch.setattr(state.persistent_store, "configured", lambda: True)
    monkeypatch.setattr(state.persistent_store, "load_state", lambda: expected)
    assert state.load_state() == expected


def test_default_append_uses_atomic_persistent_store_when_configured(monkeypatch):
    captured = []
    monkeypatch.setattr(state.persistent_store, "configured", lambda: True)
    monkeypatch.setattr(state.persistent_store, "append_lesson", captured.append)
    compact = state.append_lesson({
        "fingerprint": "abc",
        "hypothesis": "restrict weak group",
        "outcome": "validation_failed",
    })
    assert captured == [compact]
    assert compact["research_only"] is True
    assert compact["trade_authority"] is False
    assert compact["promotion_authority"] is False


def test_configured_persistent_read_failure_does_not_fall_back_to_empty_tmp(monkeypatch):
    monkeypatch.setattr(state.persistent_store, "configured", lambda: True)

    def fail():
        raise RuntimeError("persistent store unavailable")

    monkeypatch.setattr(state.persistent_store, "load_state", fail)
    with pytest.raises(RuntimeError, match="persistent store unavailable"):
        state.load_state()


def test_explicit_test_path_still_uses_local_file_even_if_persistent_is_configured(tmp_path, monkeypatch):
    monkeypatch.setattr(state.persistent_store, "configured", lambda: True)
    path = tmp_path / "learning.json"
    state.append_lesson({"fingerprint": "local", "outcome": "validation_failed"}, path=path)
    loaded = state.load_state(path=path)
    assert loaded["conclusive_trial_count"] == 1
    assert loaded["lessons"][0]["fingerprint"] == "local"
