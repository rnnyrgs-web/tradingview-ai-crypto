"""Continuous ACC-002 cross-asset research runner.

A small fixed lookback grid is evaluated on train+validation only. The untouched
holdout is opened exactly once, and only when nearby parameterizations show a
stable edge. This reduces selection bias while keeping research cheap.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from cross_asset_rank import (
    CrossAssetConfig,
    build_cross_section_panel,
    evaluate_pre_oos,
    evaluate_untouched_oos,
)
from market_data import build_universe, get_history
from research_artifact import seal_research_payload


MIN_INDEPENDENT_OOS_SAMPLES = 20
MIN_STABLE_CANDIDATES = 2
MAX_HISTORY_BARS = 5000
FIXED_LOOKBACK_GRID = ((4, 16, 64), (6, 24, 72), (8, 32, 96))


def _int_env(name: str, default: int, low: int, high: int) -> int:
    return max(low, min(int(os.getenv(name, str(default))), high))


def required_history_bars(config: CrossAssetConfig, min_oos_samples: int = MIN_INDEPENDENT_OOS_SAMPLES) -> int:
    panel_required = 5 * max(1, int(min_oos_samples)) * max(1, int(config.forward_bars))
    return max(config.lookbacks) + config.forward_bars + panel_required


def _worst_stress(segment: dict) -> dict:
    stress = segment["cost_stress"]
    return stress[max(stress, key=lambda x: float(x))]


def _pre_oos_candidate_ok(pre: dict) -> bool:
    train, validation = pre["train"], pre["validation"]
    train_worst, validation_worst = _worst_stress(train), _worst_stress(validation)
    return bool(
        train["timestamps"] >= 20
        and validation["timestamps"] >= 20
        and (train["mean_rank_ic"] or 0.0) > 0.0
        and (validation["mean_rank_ic"] or 0.0) > 0.0
        and (train_worst["mean_net_top_minus_bottom"] or 0.0) > 0.0
        and (validation_worst["mean_net_top_minus_bottom"] or 0.0) > 0.0
        and validation_worst["positive_net_spread_rate"] >= 0.50
    )


def _robust_selection_score(pre: dict) -> tuple[float, float]:
    train_worst, validation_worst = _worst_stress(pre["train"]), _worst_stress(pre["validation"])
    worst_net = min(float(train_worst["mean_net_top_minus_bottom"] or -1e9), float(validation_worst["mean_net_top_minus_bottom"] or -1e9))
    worst_ic = min(float(pre["train"]["mean_rank_ic"] or -1e9), float(pre["validation"]["mean_rank_ic"] or -1e9))
    return worst_net, worst_ic


def run() -> dict:
    universe_size = _int_env("CROSS_ASSET_UNIVERSE_SIZE", 30, 8, 60)
    requested_bars = _int_env("CROSS_ASSET_BARS", 3000, 300, MAX_HISTORY_BARS)
    bar = os.getenv("CROSS_ASSET_BAR", "1H")
    forward_bars = _int_env("CROSS_ASSET_FORWARD_BARS", 24, 1, 168)
    cost_bps = float(os.getenv("CROSS_ASSET_ROUND_TRIP_COST_BPS", "12"))

    configs = [CrossAssetConfig(lookbacks=lookbacks, forward_bars=forward_bars, round_trip_cost_bps=cost_bps, min_assets=8) for lookbacks in FIXED_LOOKBACK_GRID]
    minimum_bars = max(required_history_bars(config) for config in configs)
    if minimum_bars > MAX_HISTORY_BARS:
        raise ValueError(f"forward horizon requires at least {minimum_bars} bars for {MIN_INDEPENDENT_OOS_SAMPLES} independent OOS observations; maximum supported is {MAX_HISTORY_BARS}; use a coarser bar interval")
    bars = max(requested_bars, minimum_bars)

    symbols = [row["symbol"] for row in build_universe()[:universe_size]]
    histories, failures = {}, []
    for symbol in symbols:
        try:
            rows = get_history(symbol, bar=bar, bars=bars)
            if len(rows) >= minimum_bars:
                histories[symbol] = rows
            else:
                failures.append({"symbol": symbol, "error_type": "InsufficientHistory", "bars_received": len(rows), "bars_required": minimum_bars})
        except Exception as exc:
            failures.append({"symbol": symbol, "error_type": type(exc).__name__})

    candidates = []
    for index, config in enumerate(configs):
        panel = build_cross_section_panel(histories, config)
        pre = evaluate_pre_oos(panel, config)
        candidates.append({"index": index, "lookbacks": list(config.lookbacks), "pre_oos": pre, "eligible_pre_oos": _pre_oos_candidate_ok(pre), "_panel": panel, "_config": config})

    eligible = [candidate for candidate in candidates if candidate["eligible_pre_oos"]]
    stability_pass = len(eligible) >= MIN_STABLE_CANDIDATES
    selected = max(eligible, key=lambda item: _robust_selection_score(item["pre_oos"])) if stability_pass else None
    selected_evaluation = None
    if selected is not None:
        oos = evaluate_untouched_oos(selected["_panel"], selected["_config"])
        if oos["metrics"]["timestamps"] < MIN_INDEPENDENT_OOS_SAMPLES:
            raise ValueError("insufficient independent untouched-OOS observations after alignment")
        selected_evaluation = {"index": selected["index"], "lookbacks": selected["lookbacks"], "pre_oos": selected["pre_oos"], "untouched_oos": oos}

    public_candidates = [{"index": c["index"], "lookbacks": c["lookbacks"], "pre_oos": c["pre_oos"], "eligible_pre_oos": c["eligible_pre_oos"]} for c in candidates]
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "acc": "ACC-002",
        "research_only": True,
        "live_approved": False,
        "trade_authority": False,
        "source": "OKX public historical API",
        "selection_policy": "fixed_grid_train_validation_stability_then_open_one_untouched_oos",
        "parameter_stability": {"minimum_eligible_candidates": MIN_STABLE_CANDIDATES, "eligible_candidate_count": len(eligible), "passes": stability_pass},
        "untouched_oos_opened_for_candidate_count": 1 if selected is not None else 0,
        "candidate_count": len(public_candidates),
        "candidates": public_candidates,
        "selected_evaluation": selected_evaluation,
        "universe_requested": universe_size,
        "universe_resolved": len(histories),
        "symbols": sorted(histories),
        "failed_symbols": failures,
        "bar": bar,
        "bars_requested_env": requested_bars,
        "bars_effective": bars,
        "minimum_history_bars": minimum_bars,
        "minimum_independent_oos_samples": MIN_INDEPENDENT_OOS_SAMPLES,
    }
    return seal_research_payload(payload)


def main() -> None:
    print(json.dumps(run(), default=str), flush=True)


if __name__ == "__main__":
    main()
