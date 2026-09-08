import pytest

import cross_asset_runner as runner
from cross_asset_rank import CrossAssetConfig


def test_runner_env_bounds(monkeypatch):
    monkeypatch.setenv("CROSS_ASSET_UNIVERSE_SIZE", "999")
    assert runner._int_env("CROSS_ASSET_UNIVERSE_SIZE", 30, 8, 60) == 60
    monkeypatch.setenv("CROSS_ASSET_UNIVERSE_SIZE", "1")
    assert runner._int_env("CROSS_ASSET_UNIVERSE_SIZE", 30, 8, 60) == 8


def test_required_history_supports_20_non_overlapping_oos_samples():
    cfg = CrossAssetConfig(lookbacks=(4, 16, 64), forward_bars=24)
    required = runner.required_history_bars(cfg)
    assert required == 64 + 24 + (5 * 20 * 24)
    assert required <= runner.MAX_HISTORY_BARS


def test_fixed_grid_is_small_predeclared_and_requires_neighbor_stability():
    assert runner.FIXED_LOOKBACK_GRID == ((4, 16, 64), (6, 24, 72), (8, 32, 96))
    assert runner.MIN_STABLE_CANDIDATES == 2


def _segment(ic=0.1, worst_net=0.01, positive_rate=0.6):
    return {
        "timestamps": 30,
        "mean_rank_ic": ic,
        "cost_stress": {
            "1.0": {"mean_net_top_minus_bottom": worst_net + 0.01, "positive_net_spread_rate": 0.7},
            "3.0": {"mean_net_top_minus_bottom": worst_net, "positive_net_spread_rate": positive_rate},
        },
    }


def test_pre_oos_gate_requires_both_train_and_validation_to_survive_worst_cost():
    good = {"train": _segment(), "validation": _segment()}
    assert runner._pre_oos_candidate_ok(good)
    bad = {"train": _segment(), "validation": _segment(worst_net=-0.001)}
    assert not runner._pre_oos_candidate_ok(bad)


def test_robust_selection_rewards_worst_split_not_one_lucky_split():
    stable = {"train": _segment(worst_net=0.008), "validation": _segment(worst_net=0.009)}
    lucky_validation = {"train": _segment(worst_net=0.002), "validation": _segment(worst_net=0.030)}
    assert runner._robust_selection_score(stable) > runner._robust_selection_score(lucky_validation)


def test_long_horizon_fails_closed_when_depth_cap_is_insufficient(monkeypatch):
    monkeypatch.setenv("CROSS_ASSET_FORWARD_BARS", "168")
    monkeypatch.setenv("CROSS_ASSET_BARS", "5000")
    with pytest.raises(ValueError, match="use a coarser bar interval"):
        runner.run()
