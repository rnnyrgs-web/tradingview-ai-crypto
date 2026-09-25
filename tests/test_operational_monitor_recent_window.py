import operational_monitor as monitor


def _reset_monitor_state():
    with monitor._lock:
        monitor._errors.clear()
        monitor._counts.clear()
        monitor._last_scan = None


def test_recent_health_errors_expire_without_erasing_lifetime_counts(monkeypatch):
    _reset_monitor_state()
    clock = {"now": 100.0}
    monkeypatch.setattr(monitor, "RECENT_ERROR_WINDOW_SECONDS", 60)
    monkeypatch.setattr(monitor.time, "monotonic", lambda: clock["now"])

    monitor.record_error("runtime_acceptance", RuntimeError("boom"))

    active = monitor.health_snapshot()
    assert active["recent_error_count"] == 1
    assert active["recent_error_window_seconds"] == 60
    assert active["recent_errors"][0]["component"] == "runtime_acceptance"
    assert "recorded_monotonic" not in active["recent_errors"][0]
    assert active["error_counts_by_component"] == {"runtime_acceptance": 1}

    clock["now"] = 161.0
    recovered = monitor.health_snapshot()
    assert recovered["recent_error_count"] == 0
    assert recovered["recent_errors"] == []
    assert recovered["error_counts_by_component"] == {"runtime_acceptance": 1}


def test_new_error_after_expiry_remains_fail_closed(monkeypatch):
    _reset_monitor_state()
    clock = {"now": 200.0}
    monkeypatch.setattr(monitor, "RECENT_ERROR_WINDOW_SECONDS", 60)
    monkeypatch.setattr(monitor.time, "monotonic", lambda: clock["now"])

    monitor.record_error("old_component", ValueError("old"))
    clock["now"] = 261.0
    monitor.record_error("new_component", RuntimeError("new"))

    snapshot = monitor.health_snapshot()
    assert snapshot["recent_error_count"] == 1
    assert [row["component"] for row in snapshot["recent_errors"]] == ["new_component"]
    assert snapshot["error_counts_by_component"] == {
        "old_component": 1,
        "new_component": 1,
    }


def test_recent_error_window_config_is_bounded_and_malformed_values_fall_back(monkeypatch):
    monkeypatch.setenv("OPERATIONAL_RECENT_ERROR_WINDOW_SECONDS", "not-an-int")
    assert monitor._configured_recent_error_window_seconds() == 900

    monkeypatch.setenv("OPERATIONAL_RECENT_ERROR_WINDOW_SECONDS", "5")
    assert monitor._configured_recent_error_window_seconds() == 60

    monkeypatch.setenv("OPERATIONAL_RECENT_ERROR_WINDOW_SECONDS", "99999")
    assert monitor._configured_recent_error_window_seconds() == 3600

    monkeypatch.setenv("OPERATIONAL_RECENT_ERROR_WINDOW_SECONDS", "1200")
    assert monitor._configured_recent_error_window_seconds() == 1200
