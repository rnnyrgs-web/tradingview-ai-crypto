from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from orchestration.external_replication.abnormal_day_momentum_runner import ScoredEvent, SignalEvent
from orchestration.external_replication.run_ext_abnormal_day_momentum_001_stage1 import (
    EXECUTION_CONTRACT_PATH,
    PREDECLARATION_PATH,
    _validate_contracts,
    evaluate_stage1_gates,
)

UTC = timezone.utc


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _event(day: datetime, *, period: str, net: float = 0.01, stress: float = 0.004) -> ScoredEvent:
    signal_ts = day.replace(hour=12, minute=0, second=0, microsecond=0, tzinfo=UTC)
    signal = SignalEvent(
        instrument="BTC-USDT-SWAP",
        period=period,
        signal_timestamp=signal_ts,
        entry_timestamp=signal_ts + timedelta(hours=1),
        exit_timestamp=(signal_ts + timedelta(days=1)).replace(hour=0),
        direction=1,
        baseline_direction=1,
        intraday_return=0.03,
        reference_mean=0.0,
        reference_std=0.01,
    )
    gross = net + 0.0024
    return ScoredEvent(
        signal=signal,
        entry_price=100.0,
        exit_price=100.0 * (1.0 + gross),
        gross_return=gross,
        net_return=net,
        stress_3x_net_return=stress,
    )


def _daily_events(start: datetime, count: int, *, period: str, net: float = 0.01) -> tuple[ScoredEvent, ...]:
    return tuple(_event(start + timedelta(days=index), period=period, net=net) for index in range(count))


def test_execution_contract_is_bound_to_reviewed_predeclaration_and_closed_oos() -> None:
    predecl = _json(PREDECLARATION_PATH)
    execution = _json(EXECUTION_CONTRACT_PATH)
    _validate_contracts(predecl, execution)
    assert execution["formed_before_outcomes"] is True
    assert execution["dataset_contract"]["protected_ohlcv_may_be_decoded"] is False
    assert execution["screen"]["base_total_cost_bps"] == 24.0
    assert execution["screen"]["stress_multiplier"] == 3.0
    assert execution["successor_policy"]["no_threshold_tuning_after_result"] is True
    assert execution["authority"]["trade_authority"] is False


def test_execution_contract_fails_closed_if_protected_ohlcv_is_enabled() -> None:
    predecl = _json(PREDECLARATION_PATH)
    execution = _json(EXECUTION_CONTRACT_PATH)
    execution["dataset_contract"]["protected_ohlcv_may_be_decoded"] = True
    with pytest.raises(RuntimeError, match="protected OHLCV"):
        _validate_contracts(predecl, execution)


def test_stage1_survivor_requires_all_frozen_gates_and_both_validation_halves() -> None:
    execution = _json(EXECUTION_CONTRACT_PATH)
    train = _daily_events(datetime(2025, 6, 1, tzinfo=UTC), 45, period="train")
    first = _daily_events(datetime(2026, 5, 1, tzinfo=UTC), 12, period="validation")
    second = _daily_events(datetime(2026, 7, 1, tzinfo=UTC), 12, period="validation")
    classification, gates, summaries = evaluate_stage1_gates(train, first + second, execution)
    assert classification == "STAGE1_SURVIVOR_REQUIRES_FROZEN_CONTROLS"
    assert all(gates.values())
    assert summaries["train"]["independent_utc_signal_days"] == 45
    assert summaries["validation"]["independent_utc_signal_days"] == 24
    assert summaries["validation_first_half"]["n"] == 12
    assert summaries["validation_second_half"]["n"] == 12


def test_stage1_is_underpowered_before_economic_failure_labels() -> None:
    execution = _json(EXECUTION_CONTRACT_PATH)
    train = _daily_events(datetime(2025, 6, 1, tzinfo=UTC), 39, period="train")
    validation = _daily_events(datetime(2026, 5, 1, tzinfo=UTC), 10, period="validation") + _daily_events(
        datetime(2026, 7, 1, tzinfo=UTC), 9, period="validation"
    )
    classification, gates, _ = evaluate_stage1_gates(train, validation, execution)
    assert classification == "UNDERPOWERED"
    assert gates["minimum_independent_days_train"] is False
    assert gates["minimum_independent_days_validation"] is False


def test_negative_second_validation_half_rejects_without_retuning() -> None:
    execution = _json(EXECUTION_CONTRACT_PATH)
    train = _daily_events(datetime(2025, 6, 1, tzinfo=UTC), 45, period="train")
    first = _daily_events(datetime(2026, 5, 1, tzinfo=UTC), 12, period="validation", net=0.02)
    second = _daily_events(datetime(2026, 7, 1, tzinfo=UTC), 12, period="validation", net=-0.01)
    classification, gates, _ = evaluate_stage1_gates(train, first + second, execution)
    assert classification == "STAGE1_REJECTED"
    assert gates["validation_second_half_positive"] is False
