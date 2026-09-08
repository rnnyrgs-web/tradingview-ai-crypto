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


def test_long_horizon_fails_closed_when_depth_cap_is_insufficient(monkeypatch):
    monkeypatch.setenv("CROSS_ASSET_FORWARD_BARS", "168")
    monkeypatch.setenv("CROSS_ASSET_BARS", "5000")
    with pytest.raises(ValueError, match="use a coarser bar interval"):
        runner.run()
