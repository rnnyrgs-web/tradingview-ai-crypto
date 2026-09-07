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
