import pytest

import cross_asset_runner as runner
from cross_asset_rank import CrossAssetConfig


def test_runner_env_bounds(monkeypatch):
    monkeypatch.setenv("CROSS_ASSET_UNIVERSE_SIZE", "999")
    assert runner._int_env("CROSS_ASSET_UNIVERSE_SIZE", 45, 8, 60) == 60
    monkeypatch.setenv("CROSS_ASSET_UNIVERSE_SIZE", "1")
    assert runner._int_env("CROSS_ASSET_UNIVERSE_SIZE", 45, 8, 60) == 8


def test_required_history_supports_20_non_overlapping_oos_samples():
    cfg = CrossAssetConfig(lookbacks=(4, 16, 64), forward_bars=24)
    required = runner.required_history_bars(cfg)
    assert required == 64 + 24 + (5 * 20 * 24)
    assert required <= runner.MAX_HISTORY_BARS


def test_fixed_grid_and_liquidity_subsets_are_predeclared():
    assert runner.FIXED_LOOKBACK_GRID == ((4, 16, 64), (6, 24, 72), (8, 32, 96))
    assert runner.MIN_STABLE_CANDIDATES == 2
    assert runner.LIQUIDITY_SUBSETS == (15, 30, 45)
    assert runner.MIN_STABLE_LIQUIDITY_SUBSETS == 2
    assert runner.MIN_LIQUIDITY_SUBSET_COVERAGE == 0.80
    assert runner.HORIZON_PROFILES["24h"]["bar"] == "1H"
    assert runner.HORIZON_PROFILES["24h"]["forward_bars"] == 24
    assert runner.HORIZON_PROFILES["7d"]["bar"] == "4H"
    assert runner.HORIZON_PROFILES["7d"]["forward_bars"] == 42
    longest = CrossAssetConfig(
        lookbacks=max(runner.HORIZON_PROFILES["7d"]["lookback_grid"], key=max),
        forward_bars=42,
    )
    assert runner.required_history_bars(longest) <= runner.MAX_HISTORY_BARS


def test_horizon_profiles_override_ad_hoc_bar_settings(monkeypatch):
    monkeypatch.setenv("CROSS_ASSET_HORIZON", "7d")
    monkeypatch.setenv("CROSS_ASSET_BAR", "15m")
    monkeypatch.setenv("CROSS_ASSET_FORWARD_BARS", "1")
    horizon, bar, forward, grid = runner._horizon_settings()
    assert (horizon, bar, forward) == ("7d", "4H", 42)
    assert grid == runner.HORIZON_PROFILES["7d"]["lookback_grid"]


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


def test_liquidity_subsets_keep_top_n_provenance_and_require_80pct_coverage():
    symbols = [f"S{i}" for i in range(45)]
    histories = {symbol: [{"ts": 1, "close": 1.0}] for symbol in symbols}
    subsets = runner._build_liquidity_subsets(symbols, histories)
    assert sorted(subsets) == [15, 30, 45]
    assert set(subsets[15]) == set(symbols[:15])

    # Remove four of the actual Top-15. Eleven resolved is below ceil(15*0.8)=12,
    # and lower-ranked symbols must not be substituted into that Top-15 subset.
    degraded = dict(histories)
    for symbol in symbols[:4]:
        degraded.pop(symbol)
    subsets = runner._build_liquidity_subsets(symbols, degraded)
    assert 15 not in subsets
    assert 30 in subsets
    assert all(symbol in symbols[:30] for symbol in subsets[30])


def test_candidate_selection_uses_worst_passing_liquidity_subset():
    strong = {"train": _segment(worst_net=0.02), "validation": _segment(worst_net=0.02)}
    weaker = {"train": _segment(worst_net=0.004), "validation": _segment(worst_net=0.005)}
    candidate = {
        "liquidity_subsets": {
            "15": {"eligible_pre_oos": True, "pre_oos": strong},
            "30": {"eligible_pre_oos": True, "pre_oos": weaker},
            "45": {"eligible_pre_oos": False, "pre_oos": strong},
        }
    }
    assert runner._candidate_selection_score(candidate) == runner._robust_selection_score(weaker)


def test_long_horizon_fails_closed_when_depth_cap_is_insufficient(monkeypatch):
    monkeypatch.setenv("CROSS_ASSET_FORWARD_BARS", "168")
    monkeypatch.setenv("CROSS_ASSET_BARS", "5000")
    with pytest.raises(ValueError, match="use a coarser bar interval"):
        runner.run()
