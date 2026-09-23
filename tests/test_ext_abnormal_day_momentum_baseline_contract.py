from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from orchestration.external_replication.abnormal_day_momentum_runner import (
    DataPitInconclusiveError,
    build_signal_schedule,
    score_schedule,
)


UTC = timezone.utc
INSTRUMENT = "BTC-USDT-SWAP"
PROTECTED_START = "2025-08-01T00:00:00Z"


def _signal_rows(
    *,
    signal_hour: int = 0,
    prior_close: float = 99.0,
    omit_immediate_prior_bar: bool = False,
) -> tuple[list[dict[str, object]], datetime]:
    """Build PIT reference history plus one abnormal signal and scoreable window."""

    start = datetime(2025, 1, 1, tzinfo=UTC)
    reference_calendar_days = 91 if omit_immediate_prior_bar else 90
    rows: list[dict[str, object]] = []

    for day_index in range(reference_calendar_days):
        day = start + timedelta(days=day_index)
        final_close = 101.0 if day_index % 2 == 0 else 99.0
        if day_index == reference_calendar_days - 1:
            final_close = prior_close
        for hour in range(24):
            if (
                omit_immediate_prior_bar
                and day_index == reference_calendar_days - 1
                and hour == 23
            ):
                continue
            rows.append(
                {
                    "instrument": INSTRUMENT,
                    "timestamp": day + timedelta(hours=hour),
                    "open": 100.0,
                    "close": final_close if hour == 23 else 100.0,
                }
            )

    signal_day = start + timedelta(days=reference_calendar_days)
    signal_timestamp = signal_day + timedelta(hours=signal_hour)
    for hour in range(signal_hour + 1):
        rows.append(
            {
                "instrument": INSTRUMENT,
                "timestamp": signal_day + timedelta(hours=hour),
                "open": 100.0,
                "close": 110.0 if hour == signal_hour else 100.0,
            }
        )

    # Freeze the same candidate window for control scoring: next-hour entry and
    # following UTC-day 00:00 exit both exist and are independent of direction.
    rows.append(
        {
            "instrument": INSTRUMENT,
            "timestamp": signal_timestamp + timedelta(hours=1),
            "open": 111.0,
            "close": 111.0,
        }
    )
    rows.append(
        {
            "instrument": INSTRUMENT,
            "timestamp": signal_day + timedelta(days=1),
            "open": 112.0,
            "close": 112.0,
        }
    )
    return rows, signal_timestamp


def _schedule(rows: list[dict[str, object]]):
    return build_signal_schedule(
        rows,
        train_start="2025-01-01T00:00:00Z",
        train_end="2025-06-30T23:00:00Z",
        validation_start="2025-07-01T00:00:00Z",
        validation_end="2025-07-31T23:00:00Z",
        protected_oos_start=PROTECTED_START,
        reference_days=90,
        sigma_multiple=1.5,
        latest_signal_hour_utc=22,
    )


def test_midnight_candidate_baseline_uses_previous_utc_day_23_close() -> None:
    """The #517 simple-trend control must cross the UTC day boundary exactly."""

    rows, signal_timestamp = _signal_rows(prior_close=99.0)
    schedule = _schedule(rows)

    events = [event for event in schedule if event.signal_timestamp == signal_timestamp]
    assert len(events) == 1
    event = events[0]
    assert event.signal_timestamp.hour == 0
    assert event.baseline_direction == 1


def test_midnight_candidate_baseline_can_be_short_across_day_boundary() -> None:
    rows, signal_timestamp = _signal_rows(prior_close=120.0)
    schedule = _schedule(rows)

    events = [event for event in schedule if event.signal_timestamp == signal_timestamp]
    assert len(events) == 1
    assert events[0].baseline_direction == -1


def test_missing_prior_baseline_bar_fails_closed_without_dropping_window() -> None:
    # The last calendar reference day is incomplete only because its 23:00 bar
    # is absent. Ninety earlier completed days still satisfy the frozen warmup,
    # so the candidate window legitimately forms but its control input is missing.
    rows, signal_timestamp = _signal_rows(
        prior_close=99.0,
        omit_immediate_prior_bar=True,
    )
    schedule = _schedule(rows)

    events = [event for event in schedule if event.signal_timestamp == signal_timestamp]
    assert len(events) == 1
    assert events[0].baseline_direction is None

    with pytest.raises(DataPitInconclusiveError) as excinfo:
        score_schedule(
            rows,
            schedule,
            protected_oos_start=PROTECTED_START,
            direction_source="baseline",
        )

    issues = excinfo.value.issues
    assert any(issue.reason == "MISSING_REQUIRED_BASELINE_BAR" for issue in issues)
    baseline_issue = next(
        issue for issue in issues if issue.reason == "MISSING_REQUIRED_BASELINE_BAR"
    )
    assert baseline_issue.required_timestamp == signal_timestamp - timedelta(hours=1)


def test_exact_zero_prior_hour_return_preserves_zero_economic_control_observation() -> None:
    rows, signal_timestamp = _signal_rows(prior_close=110.0)
    schedule = _schedule(rows)

    events = [event for event in schedule if event.signal_timestamp == signal_timestamp]
    assert len(events) == 1
    assert events[0].baseline_direction == 0

    scored = score_schedule(
        rows,
        schedule,
        protected_oos_start=PROTECTED_START,
        direction_source="baseline",
    )
    matching = [event for event in scored if event.signal.signal_timestamp == signal_timestamp]
    assert len(matching) == 1
    assert matching[0].gross_return == 0.0
    assert matching[0].net_return == 0.0
    assert matching[0].stress_3x_net_return == 0.0


def test_non_midnight_baseline_semantics_remain_unchanged() -> None:
    rows, signal_timestamp = _signal_rows(signal_hour=1, prior_close=99.0)
    schedule = _schedule(rows)

    events = [event for event in schedule if event.signal_timestamp == signal_timestamp]
    assert len(events) == 1
    assert signal_timestamp.hour == 1
    # 00:00 close is 100 and 01:00 close is 110, so the exact t-1h baseline is long.
    assert events[0].baseline_direction == 1
