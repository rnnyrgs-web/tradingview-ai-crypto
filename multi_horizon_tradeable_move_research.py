"""Research-only multi-horizon discovery for economically tradeable crypto moves.

This runner expands ACC-002 research beyond only 24h/7d without changing any
production forecast, calibration, paper-trading, promotion, or broker behavior.
Each horizon is predeclared before evaluation and reuses the canonical ACC-002
chronological/purged/non-overlapping/OOS/cost-stress pipeline.

The purpose is to discover which fixed horizon, if any, contains genuine
cross-sectional after-cost edge. It is deliberately restrictive: a horizon may
produce useful research evidence, but this module has no authority to turn that
evidence into a production or live trade.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path

import cross_asset_runner


# Fixed before seeing any result from this runner. Coarser bars on 48h+ horizons
# keep independent-sample history requirements inside the canonical 5,000-bar
# ceiling while retaining full-horizon non-overlapping evaluation.
MULTI_HORIZON_PROFILES = {
    "6h": {
        "bar": "1H",
        "forward_bars": 6,
        "lookback_grid": cross_asset_runner.FIXED_LOOKBACK_GRID,
        "forward_hours": 6,
    },
    "12h": {
        "bar": "1H",
        "forward_bars": 12,
        "lookback_grid": cross_asset_runner.FIXED_LOOKBACK_GRID,
        "forward_hours": 12,
    },
    "24h": {
        **cross_asset_runner.HORIZON_PROFILES["24h"],
        "forward_hours": 24,
    },
    "48h": {
        "bar": "4H",
        "forward_bars": 12,
        "lookback_grid": ((3, 12, 42), (6, 24, 84), (12, 42, 126)),
        "forward_hours": 48,
    },
    "72h": {
        "bar": "4H",
        "forward_bars": 18,
        "lookback_grid": ((3, 12, 42), (6, 24, 84), (12, 42, 126)),
        "forward_hours": 72,
    },
    "7d": {
        **cross_asset_runner.HORIZON_PROFILES["7d"],
        "forward_hours": 168,
    },
}

HORIZON_ORDER = ("6h", "12h", "24h", "48h", "72h", "7d")

_ENV_KEYS = (
    "CROSS_ASSET_HORIZON",
    "CROSS_ASSET_UNIVERSE_SIZE",
    "CROSS_ASSET_BARS",
    "CROSS_ASSET_ROUND_TRIP_COST_BPS",
)


@contextmanager
def _temporary_environment(values: dict[str, str]):
    previous = {key: os.environ.get(key) for key in values}
    try:
        for key, value in values.items():
            os.environ[key] = str(value)
        yield
    finally:
        for key, value in previous.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value


def _bars_for_profile(profile: dict) -> int:
    """Use enough history for canonical independent OOS requirements, capped safely."""
    forward_bars = int(profile["forward_bars"])
    max_lookback = max(max(grid) for grid in profile["lookback_grid"])
    minimum = max_lookback + forward_bars + 5 * cross_asset_runner.MIN_INDEPENDENT_OOS_SAMPLES * forward_bars
    return min(cross_asset_runner.MAX_HISTORY_BARS, max(3000, minimum))


def _public_result(horizon: str, result: dict) -> dict:
    selected = result.get("selected_evaluation") if isinstance(result, dict) else None
    selected = selected if isinstance(selected, dict) else {}
    oos = selected.get("untouched_oos") if isinstance(selected, dict) else None
    oos = oos if isinstance(oos, dict) else {}
    metrics = oos.get("metrics") if isinstance(oos, dict) else None
    metrics = metrics if isinstance(metrics, dict) else {}
    stress = metrics.get("cost_stress") if isinstance(metrics, dict) else None
    stress = stress if isinstance(stress, dict) else {}
    worst = stress[max(stress, key=lambda key: float(key))] if stress else {}
    return {
        "horizon": horizon,
        "forward_hours": MULTI_HORIZON_PROFILES[horizon]["forward_hours"],
        "bar": MULTI_HORIZON_PROFILES[horizon]["bar"],
        "research_blocked": bool(result.get("research_blocked")) if isinstance(result, dict) else True,
        "research_blocked_reason": result.get("research_blocked_reason") if isinstance(result, dict) else "missing_result",
        "candidate_count": int(result.get("candidate_count") or 0) if isinstance(result, dict) else 0,
        "selected_candidate": selected.get("index"),
        "mean_rank_ic_oos": metrics.get("mean_rank_ic"),
        "positive_rank_ic_rate_oos": metrics.get("positive_rank_ic_rate"),
        "worst_cost_mean_net_top_minus_bottom": worst.get("mean_net_top_minus_bottom") if isinstance(worst, dict) else None,
        "worst_cost_positive_net_spread_rate": worst.get("positive_net_spread_rate") if isinstance(worst, dict) else None,
        "independent_oos_samples": metrics.get("timestamps"),
        "acc002_research_pass": bool(selected.get("acc002_research_pass")),
        "point_in_time_universe_pass": bool(selected.get("acc011_survivorship_pass")),
        "eligible_for_promotion_review": bool(selected.get("eligible_for_promotion_review")),
        "research_only": True,
        "trade_authority": False,
        "promotion_authority": False,
    }


def run_multi_horizon(*, universe_size: int = 30, cost_bps: float = 12.0) -> dict:
    """Evaluate every predeclared horizon through the canonical ACC-002 runner.

    Results from separate horizons are not pooled into one sample count. Choosing a
    horizon after inspecting these results is itself model selection and must remain
    inside the multiple-testing/promotion firewall.
    """
    original_profiles = dict(cross_asset_runner.HORIZON_PROFILES)
    cross_asset_runner.HORIZON_PROFILES.update(MULTI_HORIZON_PROFILES)
    results = []
    try:
        for horizon in HORIZON_ORDER:
            profile = MULTI_HORIZON_PROFILES[horizon]
            env = {
                "CROSS_ASSET_HORIZON": horizon,
                "CROSS_ASSET_UNIVERSE_SIZE": str(max(8, min(int(universe_size), 60))),
                "CROSS_ASSET_BARS": str(_bars_for_profile(profile)),
                "CROSS_ASSET_ROUND_TRIP_COST_BPS": str(float(cost_bps)),
            }
            with _temporary_environment(env):
                raw = cross_asset_runner.run()
            results.append(_public_result(horizon, raw))
    finally:
        cross_asset_runner.HORIZON_PROFILES.clear()
        cross_asset_runner.HORIZON_PROFILES.update(original_profiles)

    passing = [row["horizon"] for row in results if row["eligible_for_promotion_review"]]
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "research_only": True,
        "trade_authority": False,
        "promotion_authority": False,
        "broker_authority": False,
        "objective": "discover significant crypto movement horizons with genuine after-cost cross-sectional edge",
        "predeclared_horizons": list(HORIZON_ORDER),
        "horizon_results": results,
        "passing_research_horizons": passing,
        "selection_warning": "Do not promote the best-looking horizon by inspection. Horizon selection is multiple testing and still requires the canonical promotion chain plus genuine forward proof.",
        "production_changed": False,
        "paper_trading_changed": False,
        "calibration_changed": False,
    }


def main():
    report = run_multi_horizon()
    summary_path = os.getenv("MULTI_HORIZON_RESEARCH_SUMMARY_PATH", "").strip()
    if summary_path:
        target = Path(summary_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(report, sort_keys=True, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()
