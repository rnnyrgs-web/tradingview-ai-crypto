import basis_falsification_research as bfr
import basis_profitability_robustness as bpr


def _dataset_from_block_returns(block_returns, basis_signs, horizon=24):
    hours = horizon * len(block_returns)
    index = []
    basis = []
    level = 1000.0
    for i in range(hours + 1):
        block = min(i // horizon, len(block_returns) - 1)
        basis.append(float(basis_signs[block]))
        if i > 0 and i % horizon == 0:
            level *= 1.0 + block_returns[(i // horizon) - 1] / 10000.0
        index.append(level)
    return {
        "research_only": True,
        "candidate_id": "DATA-BASIS-001",
        "available": True,
        "points": [
            {"ts": i * bfr.HOUR_MS, "basis_bps": value}
            for i, value in enumerate(basis)
        ],
        "index_points": [
            {"ts": i * bfr.HOUR_MS, "value": value}
            for i, value in enumerate(index)
        ],
    }


def test_basis_must_beat_training_only_constant_direction_without_oos_tuning():
    # Alternating basis predicts alternating returns while a constant direction
    # cannot capture the pattern. A small positive imbalance in training makes
    # the comparator direction deterministic without consulting OOS.
    signs = [1 if i % 2 == 0 else -1 for i in range(40)]
    returns = [80.0 * sign for sign in signs]
    returns[0] = 100.0
    data = _dataset_from_block_returns(returns, signs)

    out = bpr.evaluate_basis_profitability_robustness(data, 24, cost_bps=12.0)

    assert out["available"] is True
    assert out["threshold_tuning"] is False
    assert out["untouched_oos_opened"] is False
    assert out["beats_training_only_constant_baseline"] is True
    assert out["incremental_vs_constant_avg_net_bps"] > 0
    assert out["basis_oos_hit_rate"] > out["constant_baseline_oos_hit_rate"]
    assert out["cost_stress"]["1x"]["cost_bps_round_trip"] == 12.0
    assert out["cost_stress"]["2x"]["cost_bps_round_trip"] == 24.0
    assert out["cost_stress"]["3x"]["cost_bps_round_trip"] == 36.0
    assert out["promotion_authority"] is False
    assert out["production_authority"] is False


def test_constant_market_direction_can_falsify_apparent_basis_profitability():
    # Basis stays positive while the market rises. The basis rule may look
    # profitable, but it adds no value over a training-only constant long.
    signs = [1.0] * 40
    returns = [60.0 + (i % 3) for i in range(40)]
    data = _dataset_from_block_returns(returns, signs)

    out = bpr.evaluate_basis_profitability_robustness(data, 24, cost_bps=12.0)

    # Constant basis has zero covariance, so the feature is rejected rather
    # than being credited for unconditional market drift.
    assert out["available"] is False
    assert out["reason"] == "training_direction_unavailable"


def test_small_robustness_oos_fails_closed():
    signs = [1 if i % 2 == 0 else -1 for i in range(12)]
    returns = [70.0 * sign for sign in signs]
    data = _dataset_from_block_returns(returns, signs)

    out = bpr.evaluate_basis_profitability_robustness(data, 24, cost_bps=12.0)

    assert out["available"] is False
    assert out["reason"] == "insufficient_oos_samples_before_robustness"
    assert out["minimum_oos_samples"] == bfr.DEFAULT_MIN_OOS_SAMPLES
