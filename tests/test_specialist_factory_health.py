from datetime import datetime, timedelta, timezone

import continuous_specialist_factory as factory
from deployment_canary import (
    CANARY_GRACE_SECONDS,
    evaluate_canary,
    evaluate_specialist_factory_health,
)


def _factory_state(now: datetime, **overrides):
    state = {
        "enabled": True,
        "started_at": (now - timedelta(hours=1)).isoformat(),
        "last_refresh_at": (now - timedelta(minutes=1)).isoformat(),
        "last_success_at": (now - timedelta(minutes=1)).isoformat(),
        "last_error_type": None,
        "consecutive_failures": 0,
        "refresh_seconds": 300,
        "cycles_completed": 3,
    }
    state.update(overrides)
    return state


def _runtime_inputs():
    coordinator = {
        "production_ok": True,
        "state_ok": True,
        "state_failure_reason": None,
        "consecutive_failures": 0,
    }
    army = {
        "supervisor": {
            "healthy": True,
            "stale_workers": [],
            "crashed_workers": [],
            "task_restarts": 0,
        },
        "observability": {
            "workers": {
                "completed": 10,
                "failed": 0,
                "timeouts": 0,
                "failure_rate": 0.0,
            }
        },
    }
    return coordinator, army


def test_fresh_successful_factory_is_healthy():
    now = datetime(2026, 9, 23, 14, 0, tzinfo=timezone.utc)
    result = evaluate_specialist_factory_health(
        _factory_state(now), uptime_seconds=3600, now=now
    )
    assert result["healthy"] is True
    assert result["status"] == "healthy"
    assert result["reason"] is None


def test_one_transient_failure_stays_visible_without_failing_health():
    now = datetime(2026, 9, 23, 14, 0, tzinfo=timezone.utc)
    result = evaluate_specialist_factory_health(
        _factory_state(
            now,
            last_error_type="TimeoutError",
            consecutive_failures=1,
        ),
        uptime_seconds=3600,
        now=now,
    )
    assert result["healthy"] is True
    assert result["status"] == "transient_failure"
    assert result["consecutive_failures"] == 1


def test_repeated_failures_fail_closed_and_reach_canary():
    now = datetime.now(timezone.utc)
    bad_factory = _factory_state(
        now,
        last_error_type="RuntimeError",
        consecutive_failures=2,
    )
    health = evaluate_specialist_factory_health(
        bad_factory, uptime_seconds=3600, now=now
    )
    assert health["healthy"] is False
    assert health["reason"] == "specialist_factory_repeated_failures"

    coordinator, army = _runtime_inputs()
    canary = evaluate_canary(
        coordinator,
        army,
        uptime_seconds=CANARY_GRACE_SECONDS + 1,
        specialist_factory=bad_factory,
    )
    assert "specialist_factory_repeated_failures" in canary["reasons"]
    assert canary["specialist_factory_health"]["healthy"] is False
    assert canary["rollback_recommended"] is True


def test_stale_refresh_fails_closed():
    now = datetime(2026, 9, 23, 14, 0, tzinfo=timezone.utc)
    # refresh_seconds=300 => stale after 720 seconds.
    result = evaluate_specialist_factory_health(
        _factory_state(
            now,
            last_refresh_at=(now - timedelta(seconds=721)).isoformat(),
        ),
        uptime_seconds=3600,
        now=now,
    )
    assert result["healthy"] is False
    assert result["reason"] == "specialist_factory_stale_refresh"


def test_missing_refresh_is_tolerated_only_during_bounded_startup():
    now = datetime(2026, 9, 23, 14, 0, tzinfo=timezone.utc)
    warming = evaluate_specialist_factory_health(
        _factory_state(
            now,
            last_refresh_at=None,
            last_success_at=None,
            cycles_completed=0,
        ),
        uptime_seconds=100,
        now=now,
    )
    assert warming["healthy"] is True
    assert warming["status"] == "warming"

    stalled = evaluate_specialist_factory_health(
        _factory_state(
            now,
            last_refresh_at=None,
            last_success_at=None,
            cycles_completed=0,
        ),
        uptime_seconds=721,
        now=now,
    )
    assert stalled["healthy"] is False
    assert stalled["reason"] == "specialist_factory_never_refreshed"


def test_disabled_factory_is_explicitly_safe(monkeypatch):
    monkeypatch.setenv("SPECIALIST_FACTORY_ENABLED", "0")
    result = evaluate_specialist_factory_health(
        {"last_error_type": "RuntimeError", "consecutive_failures": 99},
        uptime_seconds=99999,
    )
    assert result["healthy"] is True
    assert result["status"] == "disabled"
    assert result["reason"] is None


def test_refresh_once_records_success_then_consecutive_failures(monkeypatch):
    original = factory.snapshot()
    try:
        first = factory.refresh_once(rows=[])
        assert first["last_success_at"] is not None
        assert first["last_refresh_at"] == first["last_success_at"]
        assert first["last_error_type"] is None
        assert first["consecutive_failures"] == 0
        successful_at = first["last_success_at"]

        def fail_build(_rows):
            raise RuntimeError("synthetic factory failure")

        monkeypatch.setattr(factory, "build_specialist_snapshot", fail_build)
        once = factory.refresh_once(rows=[])
        assert once["last_error_type"] == "RuntimeError"
        assert once["consecutive_failures"] == 1
        assert once["last_success_at"] == successful_at

        twice = factory.refresh_once(rows=[])
        assert twice["last_error_type"] == "RuntimeError"
        assert twice["consecutive_failures"] == 2
        assert twice["last_success_at"] == successful_at
    finally:
        with factory._lock:
            factory._state.clear()
            factory._state.update(original)
