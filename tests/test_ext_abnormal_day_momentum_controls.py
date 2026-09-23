from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from orchestration.external_replication.abnormal_day_momentum_controls import (
    evaluate_frozen_nonrandom_controls,
)
from orchestration.external_replication.abnormal_day_momentum_runner import SignalEvent
from orchestration.external_replication.run_ext_abnormal_day_momentum_001_stage1 import (
    EXECUTION_CONTRACT_PATH,
)

UTC = timezone.utc
PROTECTED = "2026-09-01T00:00:00Z"


def _execution() -> dict:
    return json.loads(Path(EXECUTION_CONTRACT_PATH).read_text(encoding="utf-8"))


def _signal(day: datetime, *, hour: int, baseline_direction: int) -> SignalEvent:
    signal_ts = day.replace(hour=hour, minute=0, second=0, microsecond=0, tzinfo=UTC)
    return SignalEvent(
        instrument="BTC-USDT-SWAP",
        period="train",
        signal_timestamp=signal_ts,
        entry_timestamp=signal_ts + timedelta(hours=1),
        exit_timestamp=(signal_ts + timedelta(days=1)).replace(hour=0),
        direction=1,
        baseline_direction=baseline_direction,
        intraday_return=0.03,
        reference_mean=0.0,
        reference_std=0.01,
    )


def _rows_for(*signals: SignalEvent) -> list[dict[str, object]]:
    rows: dict[datetime, dict[str, object]] = {}
    for signal in signals:
        timestamps = (
            signal.entry_timestamp,
            signal.entry_timestamp + timedelta(hours=1),
            signal.exit_timestamp,
        )
        for offset, ts in enumerate(timestamps):
            # Deterministic upward path. Duplicate timestamps across synthetic events
            # collapse to the same market observation rather than fabricating rows.
            rows[ts] = {
                "instrument": signal.instrument,
                "timestamp": ts,
                "open": 100.0 + 2.0 * offset,
                "close": 100.0 + 2.0 * offset,
            }
    return list(rows.values())


def test_nonrandom_controls_preserve_candidate_windows_and_fixed_sizing() -> None:
    normal = _signal(datetime(2025, 6, 1, tzinfo=UTC), hour=12, baseline_direction=1)
    late = _signal(datetime(2025, 6, 3, tzinfo=UTC), hour=22, baseline_direction=1)
    controls = evaluate_frozen_nonrandom_controls(
        _rows_for(normal, late),
        (normal, late),
        execution=_execution(),
        protected_oos_start=PROTECTED,
    )

    baseline = controls["primary_one_hour_momentum"]
    sign_flip = controls["sign_flip_falsifier"]
    delayed = controls["one_bar_delayed_candidate"]

    assert baseline["scheduled_candidate_windows"] == 2
    assert baseline["scored_windows"] == 2
    assert baseline["structural_no_hold_windows"] == 0
    assert sign_flip["scored_windows"] == 2

    # The 22:00 candidate has entry 23:00 and midnight exit. A one-bar delay has
    # no holding interval and is omitted by the frozen price-independent rule only.
    assert delayed["scheduled_candidate_windows"] == 2
    assert delayed["scored_windows"] == 1
    assert delayed["structural_no_hold_windows"] == 1

    assert baseline["train"]["portfolio_sizing"]["nav_fraction_per_eligible_instrument"] == pytest.approx(1.0 / 3.0)
    assert baseline["train"]["portfolio_sizing"]["final_same_day_signal_count_normalization_allowed"] is False
    assert baseline["protected_oos_opened"] is False
    assert baseline["trade_authority"] is False


def test_zero_one_hour_baseline_keeps_window_as_zero_position() -> None:
    signal = _signal(datetime(2025, 6, 5, tzinfo=UTC), hour=12, baseline_direction=0)
    controls = evaluate_frozen_nonrandom_controls(
        _rows_for(signal),
        (signal,),
        execution=_execution(),
        protected_oos_start=PROTECTED,
    )
    baseline = controls["primary_one_hour_momentum"]

    assert baseline["scheduled_candidate_windows"] == 1
    assert baseline["scored_windows"] == 1
    assert baseline["train"]["independent_utc_signal_day_blocks"] == 1
    assert baseline["train"]["total_net_return"] == pytest.approx(0.0)
    assert baseline["train"]["total_2x_cost_return"] == pytest.approx(0.0)
    assert baseline["train"]["total_3x_cost_return"] == pytest.approx(0.0)


def test_sign_flip_uses_same_window_but_opposite_direction() -> None:
    signal = _signal(datetime(2025, 6, 7, tzinfo=UTC), hour=12, baseline_direction=1)
    controls = evaluate_frozen_nonrandom_controls(
        _rows_for(signal),
        (signal,),
        execution=_execution(),
        protected_oos_start=PROTECTED,
    )
    baseline_total = controls["primary_one_hour_momentum"]["train"]["total_net_return"]
    sign_flip_total = controls["sign_flip_falsifier"]["train"]["total_net_return"]

    assert baseline_total > 0.0
    assert sign_flip_total < 0.0
    assert controls["primary_one_hour_momentum"]["scored_windows"] == controls[
        "sign_flip_falsifier"
    ]["scored_windows"]


def test_controls_fail_closed_if_candidate_sizing_contract_is_weakened() -> None:
    signal = _signal(datetime(2025, 6, 9, tzinfo=UTC), hour=12, baseline_direction=1)
    execution = _execution()
    execution["portfolio_sizing"]["controls_use_same_sizing_and_aggregation"] = False

    with pytest.raises(RuntimeError, match="frozen candidate sizing"):
        evaluate_frozen_nonrandom_controls(
            _rows_for(signal),
            (signal,),
            execution=execution,
            protected_oos_start=PROTECTED,
        )
