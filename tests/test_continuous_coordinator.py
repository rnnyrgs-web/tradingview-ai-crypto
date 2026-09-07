import pytest

import continuous_coordinator as coordinator


def test_health_validation_is_fail_closed():
    assert coordinator.validate_production_health(
        {"ok": True, "operations": {"recent_error_count": 0}}
    )
    assert not coordinator.validate_production_health({"ok": True})
    assert not coordinator.validate_production_health(
        {"ok": True, "operations": {"recent_error_count": 1}}
    )
    assert not coordinator.validate_production_health({"ok": False, "operations": {}})


def test_state_requires_explicit_last_updated_line():
    assert coordinator.parse_state_last_updated(
        "# AI DEVELOPMENT STATE\nLast updated: 2026-09-07\n"
    ) == "2026-09-07"
    assert coordinator.parse_state_last_updated("# AI DEVELOPMENT STATE\n") is None


def test_check_state_recovers_after_success():
    with coordinator._lock:
        coordinator._status["consecutive_failures"] = 2
    coordinator.apply_check(
        {
            "last_check_at": "now",
            "production_ok": True,
            "state_ok": True,
            "state_last_updated": "2026-09-07",
            "last_error_type": None,
        }
    )
    with coordinator._lock:
        assert coordinator._status["consecutive_failures"] == 0


def test_ai_assessment_requires_bounded_known_states():
    parsed = coordinator.parse_ai_assessment(
        '{"status":"INVESTIGATE","priority":"HIGH","summary":"check scan validator",'
        '"next_action":"verify exact workflow evidence"}'
    )
    assert parsed["status"] == "INVESTIGATE"
    assert parsed["priority"] == "HIGH"
    with pytest.raises(ValueError):
        coordinator.parse_ai_assessment(
            '{"status":"TRADE","priority":"HIGH","summary":"buy",'
            '"next_action":"bypass validation"}'
        )


def test_ai_cycle_missing_key_fails_closed(monkeypatch):
    monkeypatch.setattr(coordinator, "OPENAI_API_KEY", "")

    class NeverCalled:
        async def get(self, *_args, **_kwargs):
            raise AssertionError("network must not be called without AI configuration")

    import asyncio

    result = asyncio.run(coordinator.run_ai_cycle(NeverCalled()))
    assert result == {"configured": False, "error_type": "MissingAIConfiguration"}


def test_health_exposes_no_trade_or_write_authority():
    payload = coordinator.health()
    assert payload["trade_authority"] is False
    assert payload["write_authority"] is False
    assert payload["promotion_authority"] is False
    assert payload["mode"] == "continuous_ai_observer"
