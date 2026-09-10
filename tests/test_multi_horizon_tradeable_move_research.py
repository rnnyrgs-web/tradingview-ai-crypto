from __future__ import annotations

import os

import multi_horizon_tradeable_move_research as multi


def _fake_result(horizon):
    return {
        "candidate_count": 3,
        "selected_evaluation": {
            "index": 1,
            "acc002_research_pass": True,
            "acc011_survivorship_pass": True,
            "eligible_for_promotion_review": True,
            "untouched_oos": {
                "metrics": {
                    "timestamps": 25,
                    "mean_rank_ic": 0.08,
                    "positive_rank_ic_rate": 0.60,
                    "cost_stress": {
                        "1.0": {"mean_net_top_minus_bottom": 0.01, "positive_net_spread_rate": 0.60},
                        "3.0": {"mean_net_top_minus_bottom": 0.004, "positive_net_spread_rate": 0.56},
                    },
                }
            },
        },
        "horizon": horizon,
        "research_only": True,
        "trade_authority": False,
    }


def test_horizon_grid_is_fixed_and_covers_short_to_weekly_moves():
    assert multi.HORIZON_ORDER == ("6h", "12h", "24h", "48h", "72h", "7d")
    assert [multi.MULTI_HORIZON_PROFILES[h]["forward_hours"] for h in multi.HORIZON_ORDER] == [6, 12, 24, 48, 72, 168]
    assert multi.MULTI_HORIZON_PROFILES["48h"]["bar"] == "4H"
    assert multi.MULTI_HORIZON_PROFILES["72h"]["bar"] == "4H"


def test_history_requests_fit_existing_canonical_cap():
    for profile in multi.MULTI_HORIZON_PROFILES.values():
        bars = multi._bars_for_profile(profile)
        assert 3000 <= bars <= multi.cross_asset_runner.MAX_HISTORY_BARS


def test_runner_evaluates_every_horizon_without_granting_trade_authority(monkeypatch):
    seen = []

    def fake_run():
        horizon = os.environ["CROSS_ASSET_HORIZON"]
        seen.append((horizon, os.environ["CROSS_ASSET_BARS"]))
        return _fake_result(horizon)

    original_profiles = dict(multi.cross_asset_runner.HORIZON_PROFILES)
    monkeypatch.setattr(multi.cross_asset_runner, "run", fake_run)
    report = multi.run_multi_horizon(universe_size=30, cost_bps=12)

    assert [h for h, _bars in seen] == list(multi.HORIZON_ORDER)
    assert report["predeclared_horizons"] == list(multi.HORIZON_ORDER)
    assert report["research_only"] is True
    assert report["trade_authority"] is False
    assert report["promotion_authority"] is False
    assert report["broker_authority"] is False
    assert report["production_changed"] is False
    assert report["paper_trading_changed"] is False
    assert report["calibration_changed"] is False
    assert multi.cross_asset_runner.HORIZON_PROFILES == original_profiles
    assert all(row["trade_authority"] is False for row in report["horizon_results"])
    assert all(row["promotion_authority"] is False for row in report["horizon_results"])


def test_missing_or_blocked_horizon_cannot_look_promotion_ready():
    row = multi._public_result(
        "6h",
        {
            "research_blocked": True,
            "research_blocked_reason": "insufficient_supported_liquidity_subsets",
            "candidate_count": 0,
            "selected_evaluation": None,
        },
    )
    assert row["research_blocked"] is True
    assert row["eligible_for_promotion_review"] is False
    assert row["acc002_research_pass"] is False
    assert row["trade_authority"] is False
