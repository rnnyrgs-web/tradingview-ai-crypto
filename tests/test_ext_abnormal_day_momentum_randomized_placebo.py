from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from orchestration.external_replication.abnormal_day_momentum_randomized_placebo import (
    RandomizedTimingPlaceboInconclusiveError,
    evaluate_randomized_timing_placebo,
    form_randomized_timing_placebo_schedule,
)
from orchestration.external_replication.abnormal_day_momentum_runner import SignalEvent
from orchestration.external_replication.run_ext_abnormal_day_momentum_001_stage1 import (
    EXECUTION_CONTRACT_PATH,
)

UTC = timezone.utc
ROOT = Path(__file__).resolve().parents[1]
PLACEBO_CONTRACT_PATH = (
    ROOT
    / "orchestration/external_replication/ext_abnormal_day_momentum_001_randomized_timing_placebo.json"
)


def _contract() -> dict:
    return json.loads(PLACEBO_CONTRACT_PATH.read_text(encoding="utf-8"))


def _execution() -> dict:
    return json.loads(Path(EXECUTION_CONTRACT_PATH).read_text(encoding="utf-8"))


def _signal(
    day: datetime,
    *,
    instrument: str = "BTC-USDT-SWAP",
    hour: int = 12,
    direction: int = 1,
    period: str = "train",
) -> SignalEvent:
    signal_ts = day.astimezone(UTC).replace(
        hour=hour, minute=0, second=0, microsecond=0
    )
    return SignalEvent(
        instrument=instrument,
        period=period,
        signal_timestamp=signal_ts,
        entry_timestamp=signal_ts + timedelta(hours=1),
        exit_timestamp=signal_ts.replace(hour=0) + timedelta(days=1),
        direction=direction,
        baseline_direction=None,
        intraday_return=0.0,
        reference_mean=0.0,
        reference_std=0.01,
    )


def _rows(
    start: datetime,
    end: datetime,
    *,
    instruments: tuple[str, ...] = ("BTC-USDT-SWAP", "ETH-USDT-SWAP"),
    entry_open_multiplier: float = 1.0,
) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    day = start.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    final_day = end.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)
    index = 0
    while day <= final_day:
        daily_return = ((index % 9) - 4) * 0.001
        for instrument_index, instrument in enumerate(instruments):
            base = 100.0 + instrument_index * 20.0 + index * 0.01
            for hour in range(24):
                ts = day + timedelta(hours=hour)
                open_price = base
                if hour not in {0, 23}:
                    open_price *= entry_open_multiplier
                close_price = base * (
                    1.0 + daily_return * float(hour + 1) / 24.0
                )
                rows.append(
                    {
                        "instrument": instrument,
                        "timestamp": ts,
                        "open": open_price,
                        "close": close_price,
                    }
                )
        index += 1
        day += timedelta(days=1)
    return rows


def _shape(schedule: tuple[SignalEvent, ...]) -> list[tuple[str, int, int, str]]:
    return sorted(
        (
            event.instrument,
            event.signal_timestamp.hour,
            event.direction,
            event.period,
        )
        for event in schedule
    )


def test_contract_seed_is_frozen_from_preoutcome_identity() -> None:
    contract = _contract()
    formation = contract["formation"]
    payload = (
        formation["cohort_planning_id"]
        + "|"
        + contract["source_predeclaration_artifact_sha256"]
        + "|randomized_timing_v1"
    )
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()

    assert digest == formation["seed_sha256"]
    assert int(digest[:16], 16) == formation["seed_uint64"]
    assert formation["draw_count"] == 1
    assert formation["post_outcome_redraw_allowed"] is False
    assert contract["formed_before_replication_outcomes"] is True


def test_placebo_preserves_authoritative_day_blocks_direction_hours_and_instruments() -> None:
    rows = _rows(
        datetime(2025, 5, 7, tzinfo=UTC),
        datetime(2025, 11, 30, tzinfo=UTC),
    )
    source = (
        _signal(
            datetime(2025, 9, 15, tzinfo=UTC),
            instrument="BTC-USDT-SWAP",
            hour=12,
            direction=1,
        ),
        _signal(
            datetime(2025, 9, 15, tzinfo=UTC),
            instrument="ETH-USDT-SWAP",
            hour=14,
            direction=-1,
        ),
        _signal(
            datetime(2025, 9, 20, tzinfo=UTC),
            instrument="BTC-USDT-SWAP",
            hour=12,
            direction=-1,
        ),
    )

    placebo = form_randomized_timing_placebo_schedule(
        rows, source, contract=_contract()
    )
    candidate_days = {event.signal_timestamp.date() for event in source}
    placebo_days = {event.signal_timestamp.date() for event in placebo}

    assert len(placebo) == len(source)
    assert len(placebo_days) == 2
    assert placebo_days.isdisjoint(candidate_days)

    source_blocks: dict[object, list[SignalEvent]] = {}
    placebo_blocks: dict[object, list[SignalEvent]] = {}
    for event in source:
        source_blocks.setdefault(event.signal_timestamp.date(), []).append(event)
    for event in placebo:
        placebo_blocks.setdefault(event.signal_timestamp.date(), []).append(event)

    assert sorted(_shape(tuple(block)) for block in source_blocks.values()) == sorted(
        _shape(tuple(block)) for block in placebo_blocks.values()
    )


def test_formation_is_deterministic_and_ignores_forward_entry_price_values() -> None:
    start = datetime(2025, 5, 7, tzinfo=UTC)
    end = datetime(2025, 11, 30, tzinfo=UTC)
    source = (
        _signal(datetime(2025, 9, 15, tzinfo=UTC), hour=10, direction=1),
        _signal(
            datetime(2025, 9, 18, tzinfo=UTC),
            instrument="ETH-USDT-SWAP",
            hour=16,
            direction=-1,
        ),
    )
    normal_rows = _rows(start, end, entry_open_multiplier=1.0)
    changed_forward_entry_rows = _rows(start, end, entry_open_multiplier=1.37)

    first = form_randomized_timing_placebo_schedule(
        normal_rows, source, contract=_contract()
    )
    second = form_randomized_timing_placebo_schedule(
        changed_forward_entry_rows, source, contract=_contract()
    )

    assert [
        (e.instrument, e.signal_timestamp, e.direction) for e in first
    ] == [
        (e.instrument, e.signal_timestamp, e.direction) for e in second
    ]


def test_placebo_preserves_validation_half_instead_of_crossing_robustness_boundary() -> None:
    rows = _rows(
        datetime(2025, 5, 7, tzinfo=UTC),
        datetime(2026, 8, 31, tzinfo=UTC),
        instruments=("BTC-USDT-SWAP",),
    )
    source = (
        _signal(
            datetime(2026, 5, 20, tzinfo=UTC),
            hour=9,
            direction=1,
            period="validation",
        ),
        _signal(
            datetime(2026, 7, 20, tzinfo=UTC),
            hour=9,
            direction=-1,
            period="validation",
        ),
    )
    placebo = form_randomized_timing_placebo_schedule(
        rows, source, contract=_contract()
    )

    first = [e for e in placebo if e.signal_timestamp < datetime(2026, 7, 1, tzinfo=UTC)]
    second = [e for e in placebo if e.signal_timestamp >= datetime(2026, 7, 1, tzinfo=UTC)]
    assert len(first) == 1
    assert len(second) == 1
    assert first[0].exit_timestamp <= datetime(2026, 6, 30, 23, tzinfo=UTC)
    assert second[0].exit_timestamp <= datetime(2026, 8, 31, 23, tzinfo=UTC)


def test_insufficient_distinct_placebo_days_fails_closed_without_sample_shrinking() -> None:
    rows = _rows(
        datetime(2025, 5, 7, tzinfo=UTC),
        datetime(2025, 9, 16, tzinfo=UTC),
        instruments=("BTC-USDT-SWAP",),
    )
    source = (
        _signal(datetime(2025, 9, 15, tzinfo=UTC), hour=12, direction=1),
    )
    contract = _contract()
    contract["frozen_windows"]["train_start_utc"] = "2025-09-15T00:00:00Z"
    contract["frozen_windows"]["train_end_utc"] = "2025-09-15T23:00:00Z"

    with pytest.raises(
        RandomizedTimingPlaceboInconclusiveError,
        match="DATA/PIT_INCONCLUSIVE_RANDOMIZED_PLACEBO_POOL",
    ):
        form_randomized_timing_placebo_schedule(rows, source, contract=contract)


def test_contract_rejects_postoutcome_redraws() -> None:
    rows = _rows(
        datetime(2025, 5, 7, tzinfo=UTC),
        datetime(2025, 11, 30, tzinfo=UTC),
        instruments=("BTC-USDT-SWAP",),
    )
    source = (
        _signal(datetime(2025, 9, 15, tzinfo=UTC), hour=12, direction=1),
    )
    contract = copy.deepcopy(_contract())
    contract["formation"]["draw_count"] = 2

    with pytest.raises(RuntimeError, match="exactly one deterministic draw"):
        form_randomized_timing_placebo_schedule(rows, source, contract=contract)


def test_evaluator_keeps_research_authority_off_and_same_independent_day_count() -> None:
    rows = _rows(
        datetime(2025, 5, 7, tzinfo=UTC),
        datetime(2025, 11, 30, tzinfo=UTC),
    )
    source = (
        _signal(
            datetime(2025, 9, 15, tzinfo=UTC),
            instrument="BTC-USDT-SWAP",
            hour=12,
            direction=1,
        ),
        _signal(
            datetime(2025, 9, 15, tzinfo=UTC),
            instrument="ETH-USDT-SWAP",
            hour=14,
            direction=-1,
        ),
    )

    result = evaluate_randomized_timing_placebo(
        rows,
        source,
        execution=_execution(),
        contract=_contract(),
    )

    assert result["scheduled_candidate_windows"] == 2
    assert result["scored_windows"] == 2
    assert result["independent_candidate_utc_signal_days"] == 1
    assert result["independent_placebo_utc_signal_days"] == 1
    assert result["train"]["portfolio_sizing"][
        "nav_fraction_per_eligible_instrument"
    ] == pytest.approx(1.0 / 3.0)
    assert result["protected_oos_opened"] is False
    assert result["genuine_forward_opened"] is False
    assert result["promotion_authority"] is False
    assert result["broker_connected"] is False
    assert result["trade_authority"] is False
