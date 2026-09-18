"""Selection-only cheap screen for DISC-RESIDUAL-MOMENTUM-001-v1.

This runner deliberately does not open untouched OOS. It binds the exact public
OKX dataset used for the screen, reports current-survivor / point-in-time
limitations explicitly, and can only produce pre-OOS selection evidence.
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cross_asset_rank import CrossAssetConfig, build_cross_section_panel, evaluate_pre_oos
from market_data import build_universe, get_history
from point_in_time_universe import filter_histories, load_manifest
from research_artifact import seal_research_payload, sha256_hex
from residual_momentum_research import ResidualMomentumConfig, build_residual_momentum_panel

ROOT = Path(__file__).resolve().parent
CONTRACT_PATH = ROOT / "orchestration" / "disc_residual_momentum_001.json"

LOCKED_OOS = {
    "status": "LOCKED_UNTOUCHED_OOS",
    "reason": "selection-only cheap screen; central freeze is required before any untouched-OOS access",
}

REQUIRED_SUBSETS = (15, 30)
MINIMUM_SUBSET_COVERAGE = 0.80


def _load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    contract = json.loads(path.read_text(encoding="utf-8"))
    fingerprint = contract.get("contract_sha256")
    definition = contract.get("contract_fingerprint_definition")
    payload = dict(contract)
    payload.pop("contract_sha256", None)
    payload.pop("contract_fingerprint_definition", None)
    if not isinstance(fingerprint, str) or not fingerprint:
        raise RuntimeError("selection contract is missing contract_sha256")
    if not isinstance(definition, str) or not definition:
        raise RuntimeError("selection contract is missing fingerprint definition")
    if sha256_hex(payload) != fingerprint:
        raise RuntimeError("selection contract fingerprint mismatch")
    if contract.get("fingerprint_id") != "DISC-RESIDUAL-MOMENTUM-001-v1":
        raise RuntimeError("unexpected residual-momentum fingerprint")
    if contract.get("chronology", {}).get("untouched_oos") != "LOCKED":
        raise RuntimeError("selection contract must keep untouched OOS locked")
    return contract


def _config_from_contract(contract: dict[str, Any]) -> tuple[CrossAssetConfig, ResidualMomentumConfig]:
    feature = contract["feature"]
    costs = contract["costs"]
    cross = CrossAssetConfig(
        lookbacks=tuple(int(x) for x in feature["lookbacks_hours"]),
        forward_bars=int(feature["forward_bars"]),
        top_fraction=0.20,
        round_trip_cost_bps=float(costs["base_round_trip_bps"]),
        min_assets=8,
        cost_stress_multipliers=tuple(float(x) for x in costs["stress_multipliers"]),
        non_overlapping_evaluation=True,
    )
    residual = ResidualMomentumConfig(
        beta_window=int(feature["beta_window_hours"]),
        beta_clip=float(feature["beta_clip"]),
        minimum_beta_observations=int(feature["minimum_beta_observations"]),
    )
    return cross, residual


def _worst_stress(segment: dict[str, Any]) -> dict[str, Any]:
    stress = segment["cost_stress"]
    return stress[max(stress, key=lambda key: float(key))]


def _pre_oos_positive(pre: dict[str, Any]) -> bool:
    train = pre["train"]
    validation = pre["validation"]
    train_worst = _worst_stress(train)
    validation_worst = _worst_stress(validation)
    return bool(
        train["timestamps"] >= 20
        and validation["timestamps"] >= 20
        and (train["mean_rank_ic"] or 0.0) > 0.0
        and (validation["mean_rank_ic"] or 0.0) > 0.0
        and (train_worst["mean_net_top_minus_bottom"] or 0.0) > 0.0
        and (validation_worst["mean_net_top_minus_bottom"] or 0.0) > 0.0
        and validation_worst["positive_net_spread_rate"] >= 0.50
    )


def _beats_control(challenger: dict[str, Any], control: dict[str, Any]) -> bool:
    challenger_train = _worst_stress(challenger["train"])
    challenger_validation = _worst_stress(challenger["validation"])
    control_train = _worst_stress(control["train"])
    control_validation = _worst_stress(control["validation"])
    challenger_worst_net = min(
        float(challenger_train["mean_net_top_minus_bottom"] or -1e9),
        float(challenger_validation["mean_net_top_minus_bottom"] or -1e9),
    )
    control_worst_net = min(
        float(control_train["mean_net_top_minus_bottom"] or -1e9),
        float(control_validation["mean_net_top_minus_bottom"] or -1e9),
    )
    challenger_worst_ic = min(
        float(challenger["train"]["mean_rank_ic"] or -1e9),
        float(challenger["validation"]["mean_rank_ic"] or -1e9),
    )
    control_worst_ic = min(
        float(control["train"]["mean_rank_ic"] or -1e9),
        float(control["validation"]["mean_rank_ic"] or -1e9),
    )
    return challenger_worst_net > control_worst_net and challenger_worst_ic >= control_worst_ic


def _subset_coverage(ranked_symbols: list[str], histories: dict[str, list[dict]]) -> dict[str, dict[str, Any]]:
    result: dict[str, dict[str, Any]] = {}
    for requested in REQUIRED_SUBSETS:
        requested_symbols = ranked_symbols[:requested]
        resolved = [symbol for symbol in requested_symbols if symbol in histories]
        minimum = max(8, int(math.ceil(requested * MINIMUM_SUBSET_COVERAGE)))
        result[str(requested)] = {
            "requested_assets": requested,
            "resolved_assets": len(resolved),
            "minimum_required_assets": minimum,
            "coverage": len(resolved) / requested if requested else 0.0,
            "passes_coverage": len(resolved) >= minimum,
            "missing_symbols": [symbol for symbol in requested_symbols if symbol not in histories],
        }
    return result


def _history_manifest(ranked_symbols: list[str], histories: dict[str, list[dict]], *, source: str, bar: str) -> tuple[dict[str, Any], dict[str, Any]]:
    canonical_histories = {
        symbol: [
            {
                "ts": int(row["ts"]),
                "open": float(row["open"]),
                "high": float(row["high"]),
                "low": float(row["low"]),
                "close": float(row["close"]),
                "volume": float(row.get("volume", 0.0)),
                "quote_volume": float(row.get("quote_volume", 0.0)),
            }
            for row in histories[symbol]
        ]
        for symbol in sorted(histories)
    }
    dataset = {
        "source": source,
        "bar": bar,
        "ranked_symbols": list(ranked_symbols),
        "histories": canonical_histories,
    }
    per_symbol: dict[str, Any] = {}
    total_rows = 0
    first_all = None
    last_all = None
    for symbol, rows in canonical_histories.items():
        total_rows += len(rows)
        first_ts = int(rows[0]["ts"]) if rows else None
        last_ts = int(rows[-1]["ts"]) if rows else None
        per_symbol[symbol] = {
            "rows": len(rows),
            "first_ts": first_ts,
            "last_ts": last_ts,
        }
        if first_ts is not None:
            first_all = first_ts if first_all is None else min(first_all, first_ts)
        if last_ts is not None:
            last_all = last_ts if last_all is None else max(last_all, last_ts)
    manifest = {
        "source": source,
        "bar": bar,
        "ranked_symbols": list(ranked_symbols),
        "resolved_symbols": sorted(canonical_histories),
        "missing_ranked_symbols": [symbol for symbol in ranked_symbols if symbol not in canonical_histories],
        "normalized_row_count": total_rows,
        "coverage_start": first_all,
        "coverage_end": last_all,
        "per_symbol": per_symbol,
        "normalized_rows_sha256": sha256_hex(dataset),
    }
    return manifest, dataset


def evaluate_selection_from_histories(
    ranked_symbols: list[str],
    histories: dict[str, list[dict]],
    *,
    contract: dict[str, Any] | None = None,
    point_in_time_manifest: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = contract or _load_contract()
    cross_config, residual_config = _config_from_contract(contract)

    if point_in_time_manifest is None:
        point_in_time_manifest = load_manifest(None)
    research_histories, survivorship = filter_histories(point_in_time_manifest, histories)
    coverage = _subset_coverage(ranked_symbols, research_histories)

    subset_evidence: dict[str, Any] = {}
    passing_subsets = 0
    supported_subsets = 0
    for requested in REQUIRED_SUBSETS:
        coverage_row = coverage[str(requested)]
        if not coverage_row["passes_coverage"]:
            subset_evidence[str(requested)] = {
                "coverage": coverage_row,
                "supported": False,
                "challenger_pre_oos": None,
                "control_pre_oos": None,
                "challenger_pre_oos_positive": False,
                "challenger_beats_control_pre_oos": False,
                "passes_pre_oos": False,
            }
            continue

        requested_symbols = ranked_symbols[:requested]
        subset_histories = {
            symbol: research_histories[symbol]
            for symbol in requested_symbols
            if symbol in research_histories
        }
        supported_subsets += 1
        control_panel = build_cross_section_panel(subset_histories, cross_config)
        challenger_panel = build_residual_momentum_panel(subset_histories, cross_config, residual_config)
        control_pre = evaluate_pre_oos(control_panel, cross_config)
        challenger_pre = evaluate_pre_oos(challenger_panel, cross_config)
        positive = _pre_oos_positive(challenger_pre)
        beats_control = _beats_control(challenger_pre, control_pre)
        passes = bool(positive and beats_control)
        if passes:
            passing_subsets += 1
        subset_evidence[str(requested)] = {
            "coverage": coverage_row,
            "supported": True,
            "challenger_pre_oos": challenger_pre,
            "control_pre_oos": control_pre,
            "challenger_pre_oos_positive": positive,
            "challenger_beats_control_pre_oos": beats_control,
            "passes_pre_oos": passes,
        }

    minimum_passing = int(contract["pre_oos_pass_rule"]["minimum_passing_liquidity_subsets"])
    economic_pre_oos_pass = supported_subsets >= minimum_passing and passing_subsets >= minimum_passing
    point_in_time_verified = bool(survivorship.get("survivorship_safe") and survivorship.get("promotion_allowed"))
    eligible_for_deep_freeze = bool(economic_pre_oos_pass and point_in_time_verified)

    if supported_subsets < minimum_passing:
        screen_status = "INSUFFICIENT_EVIDENCE"
        next_action = "repair_exact_top_n_history_coverage_without_rank_substitution"
    elif not economic_pre_oos_pass:
        screen_status = (
            "EXPLORATORY_PRE_OOS_FAIL_SURVIVORSHIP_UNVERIFIED"
            if not point_in_time_verified
            else "PRE_OOS_FAIL"
        )
        next_action = "preserve_negative_evidence_and_pivot_to_next_materially_distinct_cheap_screen"
    elif not point_in_time_verified:
        screen_status = "PRE_OOS_PASS_BLOCKED_POINT_IN_TIME_UNIVERSE"
        next_action = "obtain_genuine_point_in_time_membership_or_pivot_to_cleaner_fixed_asset_hypothesis"
    else:
        screen_status = "PRE_OOS_PASS_ELIGIBLE_FOR_CENTRAL_FREEZE"
        next_action = "freeze_exact_fingerprint_and_dataset_before_single_candidate_deep_validation"

    return {
        "hypothesis_id": contract["hypothesis_id"],
        "fingerprint_id": contract["fingerprint_id"],
        "contract_sha256": contract["contract_sha256"],
        "research_only": True,
        "trade_authority": False,
        "promotion_authority": False,
        "screen_stage": "SELECTION_ONLY",
        "screen_status": screen_status,
        "economic_pre_oos_pass": economic_pre_oos_pass,
        "point_in_time_universe": survivorship,
        "point_in_time_verified": point_in_time_verified,
        "eligible_for_deep_freeze": eligible_for_deep_freeze,
        "terminal_rejection_authorized": bool(not economic_pre_oos_pass and point_in_time_verified),
        "supported_liquidity_subsets": supported_subsets,
        "passing_liquidity_subsets": passing_subsets,
        "minimum_passing_liquidity_subsets": minimum_passing,
        "liquidity_subsets": subset_evidence,
        "untouched_oos": dict(LOCKED_OOS),
        "untouched_oos_opened": False,
        "next_action": next_action,
    }


def run() -> tuple[dict[str, Any], dict[str, Any]]:
    contract = _load_contract()
    source = contract["source"]
    universe_size = int(source["universe_size"])
    bars = int(source["history_bars_per_asset"])
    bar = str(source["bar_interval"])

    ranked_symbols = [row["symbol"] for row in build_universe()[:universe_size]]
    histories: dict[str, list[dict]] = {}
    failures: list[dict[str, Any]] = []
    for symbol in ranked_symbols:
        try:
            rows = get_history(symbol, bar=bar, bars=bars, max_bars=bars)
        except Exception as exc:
            failures.append({"symbol": symbol, "error_type": type(exc).__name__})
            continue
        if len(rows) < max(300, int(max(contract["feature"]["lookbacks_hours"])) + int(contract["feature"]["forward_bars"]) + 120):
            failures.append(
                {
                    "symbol": symbol,
                    "error_type": "InsufficientHistory",
                    "bars_received": len(rows),
                }
            )
            continue
        histories[symbol] = rows

    manifest, dataset = _history_manifest(
        ranked_symbols,
        histories,
        source="OKX /api/v5/market/history-candles",
        bar=bar,
    )
    point_in_time = load_manifest(os.getenv("POINT_IN_TIME_UNIVERSE_MANIFEST", "").strip() or None)
    selection = evaluate_selection_from_histories(
        ranked_symbols,
        histories,
        contract=contract,
        point_in_time_manifest=point_in_time,
    )
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "artifact_type": "DISC_RESIDUAL_MOMENTUM_SELECTION_EVIDENCE",
        "hypothesis_id": contract["hypothesis_id"],
        "fingerprint_id": contract["fingerprint_id"],
        "contract_sha256": contract["contract_sha256"],
        "research_only": True,
        "live_approved": False,
        "trade_authority": False,
        "promotion_authority": False,
        "source": "OKX public historical API",
        "bar": bar,
        "dataset_manifest": manifest,
        "history_failures": failures,
        "selection": selection,
        "scientific_limitations": {
            "point_in_time_membership_verified": selection["point_in_time_verified"],
            "current_survivor_screen_only": not selection["point_in_time_verified"],
            "untouched_oos_opened": False,
            "warning": (
                "Current-survivor cross-sectional evidence is exploratory only when historical point-in-time "
                "membership is unverified. It cannot unlock deep validation or terminal rejection by itself."
            ),
        },
    }
    return seal_research_payload(payload), dataset


def _write_dataset(path: Path, dataset: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.suffix == ".gz":
        with gzip.open(path, "wt", encoding="utf-8") as handle:
            json.dump(dataset, handle, sort_keys=True, separators=(",", ":"))
    else:
        path.write_text(json.dumps(dataset, sort_keys=True, separators=(",", ":")), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path)
    parser.add_argument("--dataset-output", type=Path)
    args = parser.parse_args()

    envelope, dataset = run()
    text = json.dumps(envelope, indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(text + "\n", encoding="utf-8")
    else:
        print(text)
    if args.dataset_output:
        _write_dataset(args.dataset_output, dataset)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
