"""Continuous ACC-002 cross-asset research runner.

A small fixed lookback grid is evaluated on train+validation only. Candidate
parameters must also survive predeclared liquidity subsets before the untouched
holdout is opened exactly once on the largest supported subset. This reduces
selection bias and rejects edges that exist only in one narrow universe.

ACC-011 adds a separate survivorship gate. Selecting today's liquid universe and
pulling those survivors backward is useful research but is not promotion-grade
point-in-time evidence. Promotion safety requires explicit timestamped investable-
universe snapshots with provenance; missing historical members fail closed.
"""

from __future__ import annotations

import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path

from cross_asset_rank import (
    CrossAssetConfig,
    build_cross_section_panel,
    evaluate_pre_oos,
    evaluate_untouched_oos,
)
from market_data import build_universe, get_history
from point_in_time_universe import filter_histories, load_manifest
from research_artifact import seal_research_payload


MIN_INDEPENDENT_OOS_SAMPLES = 20
MIN_STABLE_CANDIDATES = 2
MIN_STABLE_LIQUIDITY_SUBSETS = 2
MIN_LIQUIDITY_SUBSET_COVERAGE = 0.80
MAX_HISTORY_BARS = 5000
FIXED_LOOKBACK_GRID = ((4, 16, 64), (6, 24, 72), (8, 32, 96))
HORIZON_PROFILES = {
    "24h": {"bar": "1H", "forward_bars": 24, "lookback_grid": FIXED_LOOKBACK_GRID},
    "7d": {
        "bar": "4H",
        "forward_bars": 42,
        "lookback_grid": ((3, 12, 42), (6, 24, 84), (12, 42, 126)),
    },
}
LIQUIDITY_SUBSETS = (15, 30, 45)


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


def _build_liquidity_subsets(symbols: list[str], histories: dict[str, list[dict]]) -> dict[int, dict[str, list[dict]]]:
    """Return predeclared Top-N subsets only when enough of that Top-N resolved.

    Ordering comes from today's build_universe() unless verified ACC-011 snapshots
    prove that every historical member needed by this research was fetched. Failed
    histories are never replaced by lower-ranked assets.
    """
    subsets = {}
    for requested in LIQUIDITY_SUBSETS:
        if len(symbols) < requested:
            continue
        requested_symbols = symbols[:requested]
        resolved = {symbol: histories[symbol] for symbol in requested_symbols if symbol in histories}
        minimum = max(8, int(math.ceil(requested * MIN_LIQUIDITY_SUBSET_COVERAGE)))
        if len(resolved) >= minimum:
            subsets[requested] = resolved
    return subsets


def _candidate_selection_score(candidate: dict) -> tuple[float, float]:
    scores = [
        _robust_selection_score(item["pre_oos"])
        for item in candidate["liquidity_subsets"].values()
        if item["eligible_pre_oos"]
    ]
    if not scores:
        return -1e9, -1e9
    return min(score[0] for score in scores), min(score[1] for score in scores)


def _horizon_settings() -> tuple[str, str, int, tuple[tuple[int, ...], ...]]:
    horizon = os.getenv("CROSS_ASSET_HORIZON", "").strip().lower()
    if not horizon:
        return (
            "custom",
            os.getenv("CROSS_ASSET_BAR", "1H"),
            _int_env("CROSS_ASSET_FORWARD_BARS", 24, 1, 168),
            FIXED_LOOKBACK_GRID,
        )
    if horizon not in HORIZON_PROFILES:
        raise ValueError("CROSS_ASSET_HORIZON must be one of: 24h, 7d")
    profile = HORIZON_PROFILES[horizon]
    return horizon, profile["bar"], profile["forward_bars"], profile["lookback_grid"]


def _blocked_payload(*, horizon: str, bar: str, universe_size: int, requested_bars: int, bars: int, minimum_bars: int, histories: dict, failures: list, survivorship: dict, liquidity_histories: dict, reason: str) -> dict:
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "acc": "ACC-002",
        "research_only": True,
        "research_blocked": True,
        "research_blocked_reason": reason,
        "live_approved": False,
        "trade_authority": False,
        "source": "OKX public historical API",
        "selection_policy": "fixed_grid_train_validation_parameter_and_liquidity_stability_then_open_one_untouched_oos",
        "survivorship_policy": (
            "Today's liquid universe is not historical membership evidence. Cross-sectional promotion review requires "
            "timestamped investable-universe snapshots with provenance and all manifest members actually fetched."
        ),
        "point_in_time_universe": survivorship,
        "parameter_stability": {"minimum_eligible_candidates": MIN_STABLE_CANDIDATES, "eligible_candidate_count": 0, "passes": False},
        "liquidity_stability_policy": {
            "predeclared_subsets": list(LIQUIDITY_SUBSETS),
            "supported_subsets": sorted(liquidity_histories),
            "minimum_subset_coverage": MIN_LIQUIDITY_SUBSET_COVERAGE,
            "minimum_passing_subsets_per_candidate": MIN_STABLE_LIQUIDITY_SUBSETS,
            "primary_oos_subset": None,
            "oos_subset_count": 0,
        },
        "untouched_oos_opened_for_candidate_count": 0,
        "candidate_count": 0,
        "candidates": [],
        "selected_evaluation": None,
        "universe_requested": universe_size,
        "universe_resolved": len(histories),
        "universe_selection_origin": "current_liquid_universe_unless_acc011_snapshots_verified",
        "symbols": sorted(histories),
        "failed_symbols": failures,
        "bar": bar,
        "horizon": horizon,
        "bars_requested_env": requested_bars,
        "bars_effective": bars,
        "minimum_history_bars": minimum_bars,
        "minimum_independent_oos_samples": MIN_INDEPENDENT_OOS_SAMPLES,
        "eligible_for_promotion_review": False,
    }
    return seal_research_payload(payload)


def run() -> dict:
    universe_size = _int_env("CROSS_ASSET_UNIVERSE_SIZE", 45, 8, 60)
    requested_bars = _int_env("CROSS_ASSET_BARS", 3000, 300, MAX_HISTORY_BARS)
    horizon, bar, forward_bars, lookback_grid = _horizon_settings()
    cost_bps = float(os.getenv("CROSS_ASSET_ROUND_TRIP_COST_BPS", "12"))

    configs = [CrossAssetConfig(lookbacks=lookbacks, forward_bars=forward_bars, round_trip_cost_bps=cost_bps, min_assets=8) for lookbacks in lookback_grid]
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

    manifest = load_manifest(os.getenv("POINT_IN_TIME_UNIVERSE_MANIFEST", "").strip() or None)
    research_histories, survivorship = filter_histories(manifest, histories)

    research_symbols = [symbol for symbol in symbols if symbol in research_histories]
    liquidity_histories = _build_liquidity_subsets(research_symbols, research_histories)
    if len(liquidity_histories) < MIN_STABLE_LIQUIDITY_SUBSETS:
        return _blocked_payload(
            horizon=horizon,
            bar=bar,
            universe_size=universe_size,
            requested_bars=requested_bars,
            bars=bars,
            minimum_bars=minimum_bars,
            histories=research_histories,
            failures=failures,
            survivorship=survivorship,
            liquidity_histories=liquidity_histories,
            reason="insufficient_supported_liquidity_subsets",
        )
    primary_subset_size = max(liquidity_histories)

    candidates = []
    for index, config in enumerate(configs):
        subset_evidence = {}
        primary_panel = None
        primary_pre = None
        for subset_size, subset_histories in liquidity_histories.items():
            panel = build_cross_section_panel(subset_histories, config)
            pre = evaluate_pre_oos(panel, config)
            eligible_pre_oos = _pre_oos_candidate_ok(pre)
            subset_evidence[str(subset_size)] = {
                "requested_assets": subset_size,
                "resolved_assets": len(subset_histories),
                "pre_oos": pre,
                "eligible_pre_oos": eligible_pre_oos,
            }
            if subset_size == primary_subset_size:
                primary_panel = panel
                primary_pre = pre
        stable_subset_count = sum(1 for item in subset_evidence.values() if item["eligible_pre_oos"])
        liquidity_stability_pass = stable_subset_count >= MIN_STABLE_LIQUIDITY_SUBSETS
        candidates.append({
            "index": index,
            "lookbacks": list(config.lookbacks),
            "pre_oos": primary_pre,
            "eligible_pre_oos": liquidity_stability_pass,
            "liquidity_stability": {
                "minimum_passing_subsets": MIN_STABLE_LIQUIDITY_SUBSETS,
                "passing_subset_count": stable_subset_count,
                "passes": liquidity_stability_pass,
            },
            "liquidity_subsets": subset_evidence,
            "_panel": primary_panel,
            "_config": config,
        })

    eligible = [candidate for candidate in candidates if candidate["eligible_pre_oos"]]
    stability_pass = len(eligible) >= MIN_STABLE_CANDIDATES
    selected = max(eligible, key=_candidate_selection_score) if stability_pass else None
    selected_evaluation = None
    if selected is not None:
        oos = evaluate_untouched_oos(selected["_panel"], selected["_config"])
        if oos["metrics"]["timestamps"] < MIN_INDEPENDENT_OOS_SAMPLES:
            raise ValueError("insufficient independent untouched-OOS observations after alignment")
        acc002_pass = bool(oos.get("passes_acc002_research_gate"))
        selected_evaluation = {
            "index": selected["index"],
            "lookbacks": selected["lookbacks"],
            "primary_liquidity_subset": primary_subset_size,
            "pre_oos": selected["pre_oos"],
            "liquidity_stability": selected["liquidity_stability"],
            "untouched_oos": oos,
            "acc002_research_pass": acc002_pass,
            "acc011_survivorship_pass": survivorship["promotion_allowed"],
            "eligible_for_promotion_review": acc002_pass and survivorship["promotion_allowed"],
        }

    public_candidates = [{
        "index": c["index"],
        "lookbacks": c["lookbacks"],
        "pre_oos": c["pre_oos"],
        "eligible_pre_oos": c["eligible_pre_oos"],
        "liquidity_stability": c["liquidity_stability"],
        "liquidity_subsets": c["liquidity_subsets"],
    } for c in candidates]
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "acc": "ACC-002",
        "research_only": True,
        "live_approved": False,
        "trade_authority": False,
        "source": "OKX public historical API",
        "selection_policy": "fixed_grid_train_validation_parameter_and_liquidity_stability_then_open_one_untouched_oos",
        "survivorship_policy": (
            "Today's liquid universe is not historical membership evidence. Cross-sectional promotion review requires "
            "timestamped investable-universe snapshots with provenance and all manifest members actually fetched."
        ),
        "point_in_time_universe": survivorship,
        "parameter_stability": {"minimum_eligible_candidates": MIN_STABLE_CANDIDATES, "eligible_candidate_count": len(eligible), "passes": stability_pass},
        "liquidity_stability_policy": {
            "predeclared_subsets": list(LIQUIDITY_SUBSETS),
            "supported_subsets": sorted(liquidity_histories),
            "minimum_subset_coverage": MIN_LIQUIDITY_SUBSET_COVERAGE,
            "minimum_passing_subsets_per_candidate": MIN_STABLE_LIQUIDITY_SUBSETS,
            "primary_oos_subset": primary_subset_size,
            "oos_subset_count": 1,
        },
        "untouched_oos_opened_for_candidate_count": 1 if selected is not None else 0,
        "candidate_count": len(public_candidates),
        "candidates": public_candidates,
        "selected_evaluation": selected_evaluation,
        "universe_requested": universe_size,
        "universe_resolved": len(histories),
        "universe_selection_origin": "current_liquid_universe_unless_acc011_snapshots_verified",
        "symbols": sorted(research_histories),
        "failed_symbols": failures,
        "bar": bar,
        "horizon": horizon,
        "bars_requested_env": requested_bars,
        "bars_effective": bars,
        "minimum_history_bars": minimum_bars,
        "minimum_independent_oos_samples": MIN_INDEPENDENT_OOS_SAMPLES,
    }
    return seal_research_payload(payload)


def summarize_evidence(envelope: dict) -> dict:
    """Produce bounded live evidence without copying raw bootstrap/sample arrays."""
    payload = envelope["payload"]
    candidate_summaries = []
    for candidate in payload["candidates"]:
        subsets = {}
        for size, item in candidate["liquidity_subsets"].items():
            pre = item["pre_oos"]
            subsets[size] = {
                "resolved_assets": item["resolved_assets"],
                "eligible_pre_oos": item["eligible_pre_oos"],
                "train": {
                    "samples": pre["train"]["timestamps"],
                    "rank_ic": pre["train"]["mean_rank_ic"],
                    "max_cost_net_spread": _worst_stress(pre["train"])["mean_net_top_minus_bottom"],
                },
                "validation": {
                    "samples": pre["validation"]["timestamps"],
                    "rank_ic": pre["validation"]["mean_rank_ic"],
                    "max_cost_net_spread": _worst_stress(pre["validation"])["mean_net_top_minus_bottom"],
                },
            }
        candidate_summaries.append({
            "lookbacks": candidate["lookbacks"],
            "eligible_pre_oos": candidate["eligible_pre_oos"],
            "passing_liquidity_subsets": candidate["liquidity_stability"]["passing_subset_count"],
            "liquidity_subsets": subsets,
        })

    selected = payload["selected_evaluation"]
    oos_summary = None
    if selected is not None:
        oos = selected["untouched_oos"]
        metrics = oos["metrics"]
        bootstrap = oos["bootstrap_robustness"]
        oos_summary = {
            "lookbacks": selected["lookbacks"],
            "primary_liquidity_subset": selected["primary_liquidity_subset"],
            "samples": metrics["timestamps"],
            "rank_ic": metrics["mean_rank_ic"],
            "max_cost_net_spread": _worst_stress(metrics)["mean_net_top_minus_bottom"],
            "rank_ic_95pct_lower_bound": bootstrap["rank_ic_mean_95pct_lower_bound"],
            "max_cost_net_spread_95pct_lower_bound": bootstrap["max_cost_net_spread_mean_95pct_lower_bound"],
            "acc002_research_pass": selected["acc002_research_pass"],
            "acc011_survivorship_pass": selected["acc011_survivorship_pass"],
            "eligible_for_promotion_review": selected["eligible_for_promotion_review"],
        }
    return {
        "generated_at": payload["generated_at"],
        "horizon": payload["horizon"],
        "bar": payload["bar"],
        "research_blocked": bool(payload.get("research_blocked")),
        "research_blocked_reason": payload.get("research_blocked_reason"),
        "supported_liquidity_subsets": payload["liquidity_stability_policy"]["supported_subsets"],
        "parameter_stability": payload["parameter_stability"],
        "point_in_time_universe": payload["point_in_time_universe"],
        "untouched_oos_opened": selected is not None,
        "selected_oos": oos_summary,
        "candidates": candidate_summaries,
        "universe_requested": payload["universe_requested"],
        "universe_resolved": payload["universe_resolved"],
        "failed_symbol_count": len(payload["failed_symbols"]),
        "research_only": True,
        "live_approved": False,
        "trade_authority": False,
        "payload_sha256": envelope["integrity"]["payload_sha256"],
    }


def main() -> None:
    envelope = run()
    summary_path = os.getenv("CROSS_ASSET_SUMMARY_PATH", "").strip()
    if summary_path:
        target = Path(summary_path)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(summarize_evidence(envelope), sort_keys=True), encoding="utf-8")
        temporary.replace(target)
    print(json.dumps(envelope, default=str), flush=True)


if __name__ == "__main__":
    main()
