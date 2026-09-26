from __future__ import annotations

from datetime import datetime, timedelta, timezone

from orchestration.external_replication.abnormal_day_momentum_runner import build_signal_schedule


UTC = timezone.utc
INSTRUMENT = "BTC-USDT-SWAP"


def _boundary_rows() -> list[dict[str, object]]:
    """Ninety completed reference days plus an abnormal final training day.

    The candidate signal forms at 22:00 on the exact final training day. Its
    next-open entry is still inside training at 23:00, but the frozen midnight
    exit is exactly the validation start. A chronologically disjoint Stage-1
    schedule must reject that event before any forward return is read.
    """

    signal_day = datetime(2025, 6, 30, tzinfo=UTC)
    start = signal_day - timedelta(days=90)
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

    for hour in range(24):
        rows.append(
            {
                "instrument": INSTRUMENT,
                "timestamp": signal_day + timedelta(hours=hour),
                "open": 100.0,
                "close": 110.0 if hour >= 22 else 100.0,
            }
        )

    # The first validation timestamp is deliberately present so the old bug
    # cannot hide behind missing-data handling. It must never be consumed as a
    # training trade's exit.
    rows.append(
        {
            "instrument": INSTRUMENT,
            "timestamp": datetime(2025, 7, 1, tzinfo=UTC),
            "open": 112.0,
            "close": 112.0,
        }
    )
    return rows


def test_training_schedule_cannot_exit_on_validation_start() -> None:
    schedule = build_signal_schedule(
        _boundary_rows(),
        train_start="2025-04-01T00:00:00Z",
        train_end="2025-06-30T23:00:00Z",
        validation_start="2025-07-01T00:00:00Z",
        validation_end="2025-07-31T23:00:00Z",
        protected_oos_start="2025-08-01T00:00:00Z",
        reference_days=90,
        sigma_multiple=1.5,
        latest_signal_hour_utc=22,
    )

    leaked = [
        event
        for event in schedule
        if event.period == "train"
        and event.exit_timestamp >= datetime(2025, 7, 1, tzinfo=UTC)
    ]
    assert leaked == []
