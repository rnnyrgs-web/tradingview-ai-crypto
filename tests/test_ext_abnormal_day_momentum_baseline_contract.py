from __future__ import annotations

from datetime import datetime, timedelta, timezone

from orchestration.external_replication.abnormal_day_momentum_runner import build_signal_schedule


UTC = timezone.utc
INSTRUMENT = "BTC-USDT-SWAP"


def _midnight_signal_rows() -> tuple[list[dict[str, object]], datetime]:
    """Build 90 complete PIT reference days followed by one 00:00 abnormal signal.

    The last completed reference day closes below the signal-day 00:00 close, so
    the frozen simple one-hour momentum baseline must be LONG from the exact
    previous completed hourly close across the UTC day boundary.
    """

    start = datetime(2025, 1, 1, tzinfo=UTC)
    rows: list[dict[str, object]] = []
    for day_index in range(90):
        day = start + timedelta(days=day_index)
        final_close = 101.0 if day_index % 2 == 0 else 99.0
        for hour in range(24):
            rows.append(
                {
                    "instrument": INSTRUMENT,
                    "timestamp": day + timedelta(hours=hour),
                    "open": 100.0,
                    "close": final_close if hour == 23 else 100.0,
                }
            )

    signal_day = start + timedelta(days=90)
    rows.append(
        {
            "instrument": INSTRUMENT,
            "timestamp": signal_day,
            "open": 100.0,
            "close": 110.0,
        }
    )
    return rows, signal_day


def test_midnight_candidate_baseline_uses_previous_utc_day_23_close() -> None:
    """The #517 simple-trend control must preserve the exact candidate window.

    The frozen #587 predeclaration defines the primary baseline as the sign of
    the immediately preceding completed 1h close-to-close return. At 00:00 UTC,
    that predecessor is 23:00 UTC on the previous day; resetting the predecessor
    to None at the day boundary silently turns a valid baseline observation into
    direction=0 and later drops the candidate window from baseline scoring.
    """

    rows, signal_day = _midnight_signal_rows()
    schedule = build_signal_schedule(
        rows,
        train_start="2025-01-01T00:00:00Z",
        train_end="2025-06-30T23:00:00Z",
        validation_start="2025-07-01T00:00:00Z",
        validation_end="2025-07-31T23:00:00Z",
        protected_oos_start="2025-08-01T00:00:00Z",
        reference_days=90,
        sigma_multiple=1.5,
        latest_signal_hour_utc=22,
    )

    events = [event for event in schedule if event.signal_timestamp == signal_day]
    assert len(events) == 1
    event = events[0]
    assert event.signal_timestamp.hour == 0
    # Previous completed 1h close is prior-day 23:00 = 99; current 00:00 close
    # is 110, so the predeclared one-hour momentum baseline is unambiguously long.
    assert event.baseline_direction == 1
