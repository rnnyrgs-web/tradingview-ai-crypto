from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from orchestration.external_replication.abnormal_day_momentum_runner import ScoredEvent, SignalEvent
from orchestration.external_replication.run_ext_abnormal_day_momentum_001_stage1 import (
    EXECUTION_CONTRACT_PATH,
    PREDECLARATION_PATH,
    _portfolio_summary,
    _validate_contracts,
    evaluate_stage1_gates,
)

UTC = timezone.utc


def _json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _event(
    day: datetime,
    *,
    period: str,
    net: float = 0.01,
    stress: float | None = None,
    instrument: str = "BTC-USDT-SWAP",
) -> ScoredEvent:
    signal_ts = day.replace(hour=12, minute=0, second=0, microsecond=0, tzinfo=UTC)
    signal = SignalEvent(
        instrument=instrument,
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
    stress_return = gross - 0.0072 if stress is None else stress
    return ScoredEvent(
        signal=signal,
        entry_price=100.0,
        exit_price=100.0 * (1.0 + gross),
        gross_return=gross,
        net_return=net,
        stress_3x_net_return=stress_return,
    )


def _daily_events(
    start: datetime, count: int, *, period: str, net: float = 0.01
) -> tuple[ScoredEvent, ...]:
    return tuple(
        _event(start + timedelta(days=index), period=period, net=net)
        for index in range(count)
    )


def _healthy_validation() -> tuple[ScoredEvent, ...]:
    return _daily_events(
        datetime(2026, 5, 1, tzinfo=UTC), 12, period="validation"
    ) + _daily_events(datetime(2026, 7, 1, tzinfo=UTC), 12, period="validation")


def test_execution_contract_is_bound_to_reviewed_predeclaration_and_closed_oos() -> None:
    predecl = _json(PREDECLARATION_PATH)
    execution = _json(EXECUTION_CONTRACT_PATH)
    _validate_contracts(predecl, execution)
    assert execution["formed_before_outcomes"] is True
    assert execution["dataset_contract"]["protected_ohlcv_may_be_decoded"] is False
    assert execution["screen"]["base_total_cost_bps"] == 24.0
    assert execution["screen"]["middle_cost_multiplier"] == 2.0
    assert execution["screen"]["stress_multiplier"] == 3.0
    assert execution["portfolio_sizing"]["nav_fraction_per_eligible_instrument"] == pytest.approx(
        1.0 / 3.0
    )
    assert execution["portfolio_sizing"]["max_gross_nav_fraction"] == 1.0
    assert (
        execution["portfolio_sizing"]["final_same_day_signal_count_normalization_allowed"]
        is False
    )
    assert execution["successor_policy"]["no_threshold_tuning_after_result"] is True
    assert "independent_utc_signal_day_block" in execution["stage1_gates"][
        "single_winner_dependence_veto"
    ]
    assert "independent_utc_signal_day_block" in execution["stage1_gates"][
        "catastrophic_tail_veto"
    ]
    assert execution["failure_learning_diagnostics"]["intermediate_total_cost_bps"] == 48.0
    assert execution["authority"]["trade_authority"] is False


def test_execution_contract_fails_closed_if_protected_ohlcv_is_enabled() -> None:
    predecl = _json(PREDECLARATION_PATH)
    execution = _json(EXECUTION_CONTRACT_PATH)
    execution["dataset_contract"]["protected_ohlcv_may_be_decoded"] = True
    with pytest.raises(RuntimeError, match="protected OHLCV"):
        _validate_contracts(predecl, execution)


def test_execution_contract_fails_closed_if_independent_block_veto_drifts() -> None:
    predecl = _json(PREDECLARATION_PATH)
    execution = _json(EXECUTION_CONTRACT_PATH)
    execution["stage1_gates"]["single_winner_dependence_veto"] = (
        "leave_largest_raw_asset_event_out"
    )
    with pytest.raises(RuntimeError, match="independent UTC-day block"):
        _validate_contracts(predecl, execution)


def test_execution_contract_forbids_future_same_day_signal_count_normalization() -> None:
    predecl = _json(PREDECLARATION_PATH)
    execution = _json(EXECUTION_CONTRACT_PATH)
    execution["portfolio_sizing"]["final_same_day_signal_count_normalization_allowed"] = True
    with pytest.raises(RuntimeError, match="portfolio sizing"):
        _validate_contracts(predecl, execution)


def test_fixed_one_third_nav_sizing_caps_three_signal_day_at_one_nav() -> None:
    execution = _json(EXECUTION_CONTRACT_PATH)
    day = datetime(2025, 6, 1, tzinfo=UTC)

    one_signal = _portfolio_summary(
        (_event(day, period="train", net=0.01, instrument="BTC-USDT-SWAP"),),
        execution,
    )
    three_signals = _portfolio_summary(
        tuple(
            _event(day, period="train", net=0.01, instrument=instrument)
            for instrument in ("BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP")
        ),
        execution,
    )

    assert one_signal["total_net_return"] == pytest.approx(0.01 / 3.0)
    assert three_signals["total_net_return"] == pytest.approx(0.01)
    assert three_signals["total_net_return"] == pytest.approx(
        3.0 * one_signal["total_net_return"]
    )
    assert one_signal["total_net_return"] != pytest.approx(three_signals["total_net_return"])
    assert three_signals["portfolio_sizing"]["max_gross_nav_fraction"] == 1.0


def test_authoritative_summary_persists_48bps_and_uses_day_block_profit_factor() -> None:
    execution = _json(EXECUTION_CONTRACT_PATH)
    day1 = datetime(2025, 6, 1, tzinfo=UTC)
    day2 = day1 + timedelta(days=1)
    events = (
        _event(day1, period="train", net=0.03, instrument="BTC-USDT-SWAP"),
        _event(day1, period="train", net=-0.01, instrument="ETH-USDT-SWAP"),
        _event(day2, period="train", net=-0.005, instrument="BTC-USDT-SWAP"),
    )
    summary = _portfolio_summary(events, execution)

    assert summary["total_2x_cost_return"] == pytest.approx(
        sum((event.gross_return - 0.0048) / 3.0 for event in events)
    )
    assert summary["raw_event_diagnostics_non_authoritative"]["profit_factor"] == pytest.approx(
        2.0
    )
    assert summary["profit_factor"] == pytest.approx(4.0)


def test_authoritative_summary_rejects_duplicate_instrument_same_day() -> None:
    execution = _json(EXECUTION_CONTRACT_PATH)
    day = datetime(2025, 6, 1, tzinfo=UTC)
    duplicate = (
        _event(day, period="train", instrument="BTC-USDT-SWAP"),
        _event(day.replace(hour=1), period="train", instrument="BTC-USDT-SWAP"),
    )
    with pytest.raises(RuntimeError, match="duplicate instrument"):
        _portfolio_summary(duplicate, execution)


def test_stage1_survivor_requires_all_frozen_gates_and_both_validation_halves() -> None:
    execution = _json(EXECUTION_CONTRACT_PATH)
    train = _daily_events(datetime(2025, 6, 1, tzinfo=UTC), 45, period="train")
    first = _daily_events(datetime(2026, 5, 1, tzinfo=UTC), 12, period="validation")
    second = _daily_events(datetime(2026, 7, 1, tzinfo=UTC), 12, period="validation")
    classification, gates, summaries = evaluate_stage1_gates(train, first + second, execution)
    assert classification == "STAGE1_SURVIVOR_REQUIRES_FROZEN_CONTROLS"
    assert all(gates.values())
    assert summaries["train"]["independent_utc_signal_days"] == 45
    assert summaries["train"]["independent_utc_signal_day_blocks"] == 45
    assert summaries["validation"]["independent_utc_signal_days"] == 24
    assert summaries["validation_first_half"]["n"] == 12
    assert summaries["validation_second_half"]["n"] == 12
    assert summaries["train"]["total_2x_cost_return"] > 0.0


def test_stage1_is_underpowered_before_economic_failure_labels() -> None:
    execution = _json(EXECUTION_CONTRACT_PATH)
    train = _daily_events(datetime(2025, 6, 1, tzinfo=UTC), 39, period="train")
    validation = _daily_events(
        datetime(2026, 5, 1, tzinfo=UTC), 10, period="validation"
    ) + _daily_events(datetime(2026, 7, 1, tzinfo=UTC), 9, period="validation")
    classification, gates, _ = evaluate_stage1_gates(train, validation, execution)
    assert classification == "UNDERPOWERED"
    assert gates["minimum_independent_days_train"] is False
    assert gates["minimum_independent_days_validation"] is False


def test_negative_second_validation_half_rejects_without_retuning() -> None:
    execution = _json(EXECUTION_CONTRACT_PATH)
    train = _daily_events(datetime(2025, 6, 1, tzinfo=UTC), 45, period="train")
    first = _daily_events(
        datetime(2026, 5, 1, tzinfo=UTC), 12, period="validation", net=0.02
    )
    second = _daily_events(
        datetime(2026, 7, 1, tzinfo=UTC), 12, period="validation", net=-0.01
    )
    classification, gates, _ = evaluate_stage1_gates(train, first + second, execution)
    assert classification == "STAGE1_REJECTED"
    assert gates["validation_second_half_positive"] is False


def test_correlated_multi_asset_winning_day_cannot_evade_concentration_veto() -> None:
    execution = _json(EXECUTION_CONTRACT_PATH)
    start = datetime(2025, 6, 1, tzinfo=UTC)
    train = list(_daily_events(start, 39, period="train", net=-0.001))
    dominant_day = start + timedelta(days=39)
    train.extend(
        _event(dominant_day, period="train", net=0.02, instrument=instrument)
        for instrument in ("BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP")
    )

    classification, gates, summaries = evaluate_stage1_gates(
        tuple(train), _healthy_validation(), execution
    )

    assert (
        summaries["train"]["raw_event_diagnostics_non_authoritative"][
            "leave_largest_winner_out_total"
        ]
        > 0.0
    )
    assert summaries["train"]["leave_largest_independent_day_block_out_total"] < 0.0
    assert gates["single_winner_veto_train"] is False
    assert classification == "STAGE1_REJECTED"


def test_correlated_multi_asset_adverse_day_cannot_evade_tail_veto() -> None:
    execution = _json(EXECUTION_CONTRACT_PATH)
    start = datetime(2025, 6, 1, tzinfo=UTC)
    train = list(_daily_events(start, 39, period="train", net=0.0015))
    adverse_day = start + timedelta(days=39)
    train.extend(
        _event(adverse_day, period="train", net=-0.01, stress=-0.02, instrument=instrument)
        for instrument in ("BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP")
    )

    classification, gates, summaries = evaluate_stage1_gates(
        tuple(train), _healthy_validation(), execution
    )

    assert (
        summaries["train"]["raw_event_diagnostics_non_authoritative"][
            "repeat_worst_event_stressed_total"
        ]
        > 0.0
    )
    assert summaries["train"]["repeat_worst_independent_day_block_total"] < 0.0
    assert gates["catastrophic_tail_veto_train"] is False
    assert classification == "STAGE1_REJECTED"
