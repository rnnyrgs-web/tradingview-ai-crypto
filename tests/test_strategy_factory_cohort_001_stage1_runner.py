from datetime import datetime, timedelta, timezone
import math

import pytest

from orchestration.cohorts.strategy_factory_cohort_001_stage1_runner import (
    Bar,
    CANDIDATE_IDS,
    PROTECTED_START,
    Trade,
    cluster_independent_events,
    evaluate_stage1,
    population_std,
    run_synthetic_or_caller_supplied_stage1,
    type7_quantile,
    validate_histories,
)

UTC = timezone.utc


def _trade(candidate, entry, exit_, gross, instrument="BTC-USDT-SWAP", weight=1.0):
    return Trade(
        candidate,
        instrument,
        entry - timedelta(hours=1),
        entry,
        exit_,
        gross,
        weight,
    )


def test_type7_and_population_std_are_frozen() -> None:
    assert type7_quantile([0.0, 10.0], 0.25) == pytest.approx(2.5)
    assert type7_quantile([1.0, 2.0, 3.0, 4.0], 0.5) == pytest.approx(2.5)
    assert population_std([1.0, 2.0, 3.0]) == pytest.approx(math.sqrt(2.0 / 3.0))


def test_half_open_overlap_clustering_and_gross_notional_weighting() -> None:
    cid = CANDIDATE_IDS[0]
    t0 = datetime(2026, 1, 1, 0, tzinfo=UTC)
    first = _trade(cid, t0, t0 + timedelta(hours=3), 0.01, weight=2.0)
    overlapping = _trade(
        cid,
        t0 + timedelta(hours=2),
        t0 + timedelta(hours=5),
        -0.01,
        "ETH-USDT-SWAP",
        1.0,
    )
    equality_is_independent = _trade(
        cid,
        t0 + timedelta(hours=5),
        t0 + timedelta(hours=6),
        0.02,
        "SOL-USDT-SWAP",
    )
    events = cluster_independent_events([equality_is_independent, overlapping, first])
    assert len(events) == 2
    assert len(events[0].trades) == 2
    expected = (2.0 * (0.01 - 0.0024) + 1.0 * (-0.01 - 0.0024)) / 3.0
    assert events[0].return_at_cost(24.0) == pytest.approx(expected)
    assert events[1].entry_time == events[0].exit_time


def test_stage1_requires_power_before_any_survivor_label() -> None:
    cid = CANDIDATE_IDS[1]
    train_entry = datetime(2026, 1, 1, 0, tzinfo=UTC)
    val_entry = datetime(2026, 5, 10, 0, tzinfo=UTC)
    trades = [
        _trade(cid, train_entry + timedelta(days=i), train_entry + timedelta(days=i, hours=1), 0.02)
        for i in range(5)
    ] + [
        _trade(cid, val_entry + timedelta(days=i), val_entry + timedelta(days=i, hours=1), 0.02)
        for i in range(5)
    ]
    result = evaluate_stage1(cid, trades)
    assert result.classification == "INCONCLUSIVE_POWER"
    assert result.gate_results["positive_72bps_training"] is True
    assert result.gate_results["minimum_training_events"] is False
    assert result.protected_oos_opened is False
    assert result.trade_authority is False


def test_full_gate_can_only_pass_with_train_validation_halves_and_72bps() -> None:
    cid = CANDIDATE_IDS[1]
    trades = []
    train_start = datetime(2025, 8, 1, 0, tzinfo=UTC)
    for i in range(45):
        entry = train_start + timedelta(days=5 * i)
        trades.append(_trade(cid, entry, entry + timedelta(hours=1), 0.02))
    val1 = datetime(2026, 5, 2, 0, tzinfo=UTC)
    for i in range(11):
        entry = val1 + timedelta(days=4 * i)
        trades.append(_trade(cid, entry, entry + timedelta(hours=1), 0.02))
    val2 = datetime(2026, 7, 2, 0, tzinfo=UTC)
    for i in range(11):
        entry = val2 + timedelta(days=4 * i)
        trades.append(_trade(cid, entry, entry + timedelta(hours=1), 0.02))
    result = evaluate_stage1(cid, trades)
    assert result.training.independent_events == 45
    assert result.validation.independent_events == 22
    assert result.classification == "PASS_STAGE1_DEVELOPMENT_ONLY"
    assert all(result.gate_results.values())
    assert all(value is not None and value > 0 for value in result.validation_half_means_24bps)
    assert result.promotion_authority is False
    assert result.trade_authority is False


def test_72bps_gate_rejects_nominal_base_cost_edge() -> None:
    cid = CANDIDATE_IDS[2]
    trades = []
    train_start = datetime(2025, 8, 1, 0, tzinfo=UTC)
    for i in range(45):
        entry = train_start + timedelta(days=5 * i)
        trades.append(_trade(cid, entry, entry + timedelta(hours=1), 0.005))
    for start in (datetime(2026, 5, 2, tzinfo=UTC), datetime(2026, 7, 2, tzinfo=UTC)):
        for i in range(11):
            entry = start + timedelta(days=4 * i)
            trades.append(_trade(cid, entry, entry + timedelta(hours=1), 0.005))
    result = evaluate_stage1(cid, trades)
    assert result.gate_results["positive_24bps_training"] is True
    assert result.gate_results["positive_72bps_training"] is False
    assert result.classification == "FAIL_ECONOMIC_OR_ROBUSTNESS_GATE"


def test_protected_rows_and_trades_fail_closed() -> None:
    with pytest.raises(ValueError, match="protected"):
        Trade(
            CANDIDATE_IDS[0],
            "ETH-USDT-SWAP",
            PROTECTED_START - timedelta(hours=2),
            PROTECTED_START - timedelta(hours=1),
            PROTECTED_START,
            0.01,
        )


def _flat_histories(count: int = 2200):
    start = datetime(2025, 5, 7, 5, tzinfo=UTC)
    result = {}
    for n, instrument in enumerate(("BTC-USDT-SWAP", "ETH-USDT-SWAP", "SOL-USDT-SWAP")):
        bars = []
        price = 100.0 + n * 10
        for i in range(count):
            ts = start + timedelta(hours=i)
            close = price * (1.0001 if i % 2 else 0.9999)
            high = max(price, close) * 1.0005
            low = min(price, close) * 0.9995
            bars.append(Bar(ts, price, high, low, close, 1_000_000.0 + (i % 17)))
            price = close
        result[instrument] = bars
    return result


def test_all_six_frozen_builders_are_deterministic_on_caller_supplied_bars() -> None:
    histories = _flat_histories()
    for candidate in CANDIDATE_IDS:
        a = run_synthetic_or_caller_supplied_stage1(candidate, histories)
        b = run_synthetic_or_caller_supplied_stage1(candidate, histories)
        assert a == b
        assert a.candidate_id == candidate
        assert a.protected_oos_opened is False
        assert a.genuine_forward_opened is False
        assert a.trade_authority is False


def test_histories_require_exact_frozen_universe_alignment_and_hourly_grid() -> None:
    histories = _flat_histories(10)
    missing = dict(histories)
    missing.pop("SOL-USDT-SWAP")
    with pytest.raises(ValueError, match="exactly"):
        validate_histories(missing)

    broken = {key: list(value) for key, value in histories.items()}
    row = broken["ETH-USDT-SWAP"][5]
    broken["ETH-USDT-SWAP"][5] = Bar(
        row.timestamp + timedelta(hours=1),
        row.open,
        row.high,
        row.low,
        row.close,
        row.quote_volume,
    )
    with pytest.raises(ValueError, match="aligned"):
        validate_histories(broken)
