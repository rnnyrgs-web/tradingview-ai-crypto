from datetime import datetime, timedelta, timezone

import pytest

from coordination_state_health import evaluate_state_handoff_timestamp


NOW = datetime(2026, 9, 23, 12, 0, 0, tzinfo=timezone.utc)
MAX_AGE = 3600
FUTURE_SKEW = 60


def _evaluate(value, *, exact_next_step=True):
    return evaluate_state_handoff_timestamp(
        value,
        has_exact_next_step=exact_next_step,
        now=NOW,
        max_age_seconds=MAX_AGE,
        max_future_skew_seconds=FUTURE_SKEW,
    )


def _stamp(moment: datetime) -> str:
    return moment.isoformat().replace("+00:00", "Z")


def test_fresh_timestamp_is_healthy():
    result = _evaluate(_stamp(NOW - timedelta(minutes=5)))
    assert result["state_fresh"] is True
    assert result["state_structure_ok"] is True
    assert result["state_failure_reason"] is None
    assert result["state_age_seconds"] == 300.0


def test_timestamp_just_inside_max_age_is_fresh():
    result = _evaluate(_stamp(NOW - timedelta(seconds=MAX_AGE - 1)))
    assert result["state_fresh"] is True
    assert result["state_failure_reason"] is None


def test_timestamp_just_outside_max_age_is_stale():
    result = _evaluate(_stamp(NOW - timedelta(seconds=MAX_AGE + 1)))
    assert result["state_fresh"] is False
    assert result["state_failure_reason"] == "stale_timestamp"


@pytest.mark.parametrize("value", [None, ""])
def test_missing_timestamp_fails_closed(value):
    result = _evaluate(value)
    assert result["state_fresh"] is False
    assert result["state_failure_reason"] == "missing_timestamp"


@pytest.mark.parametrize("value", ["not-a-time", "2026-09-23T11:59:00"])
def test_malformed_or_naive_timestamp_fails_closed(value):
    result = _evaluate(value)
    assert result["state_fresh"] is False
    assert result["state_failure_reason"] == "malformed_timestamp"


def test_materially_future_timestamp_fails_closed():
    result = _evaluate(_stamp(NOW + timedelta(seconds=FUTURE_SKEW + 1)))
    assert result["state_fresh"] is False
    assert result["state_failure_reason"] == "future_timestamp"
    assert result["state_age_seconds"] == -(FUTURE_SKEW + 1)


def test_small_clock_skew_is_tolerated_but_remains_explicit():
    result = _evaluate(_stamp(NOW + timedelta(seconds=FUTURE_SKEW)))
    assert result["state_fresh"] is True
    assert result["state_age_seconds"] == -FUTURE_SKEW


def test_missing_exact_next_step_fails_structure_without_falsifying_freshness():
    result = _evaluate(_stamp(NOW - timedelta(minutes=5)), exact_next_step=False)
    assert result["state_fresh"] is True
    assert result["state_structure_ok"] is False
    assert result["state_failure_reason"] == "missing_exact_next_step"


def test_naive_now_is_rejected():
    with pytest.raises(ValueError, match="timezone-aware"):
        evaluate_state_handoff_timestamp(
            _stamp(NOW),
            has_exact_next_step=True,
            now=datetime(2026, 9, 23, 12, 0, 0),
            max_age_seconds=MAX_AGE,
            max_future_skew_seconds=FUTURE_SKEW,
        )
