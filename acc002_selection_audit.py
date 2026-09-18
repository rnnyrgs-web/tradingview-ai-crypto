"""Immutable, fail-closed audit wrapper for the focused ACC-002 24h screen.

The continuous ACC-002 runner remains the source of strategy logic. This module
captures the exact normalized histories and ranked Top-N inputs passed through the
existing runner, then binds them to a deterministic dataset hash and a complete
pre-OOS predicate/split audit. It never opens untouched OOS and has no broker,
promotion, deployment, or live-trade authority.
"""

from __future__ import annotations

import copy
import json
import os
from pathlib import Path

import cross_asset_runner as runner
from acc002_evidence_contract import (
    build_dataset_manifest,
    declared_search_contract,
    selection_predicate_details,
    split_timestamp_boundaries,
)
from cross_asset_rank import CrossAssetConfig, build_cross_section_panel, purged_split_ranges
from research_artifact import seal_research_payload, verify_research_envelope


AUDIT_SCHEMA_VERSION = 1
DEFAULT_OUTPUT_PATH = "research_output/acc002_selection_audit.json"


def _copy_histories(histories: dict[str, list[dict]]) -> dict[str, list[dict]]:
    return {str(symbol): copy.deepcopy(rows) for symbol, rows in histories.items()}


def _capture_selection_inputs() -> tuple[dict, dict]:
    """Run the canonical screen once while capturing the exact scored inputs."""
    if os.getenv("SINGLE_STRATEGY_DEEP_MODE", "").strip() == "1":
        raise RuntimeError("ACC-002 selection audit refuses deep/OOS mode")

    horizon, _, _, _ = runner._horizon_settings()
    if horizon != "24h":
        raise RuntimeError("ACC-002 selection audit currently supports only the focused 24h lane")

    previous_selection_mode = os.environ.get("SINGLE_STRATEGY_SELECTION_MODE")
    os.environ["SINGLE_STRATEGY_SELECTION_MODE"] = "1"
    captured: dict[str, object] = {}
    original_filter = runner.filter_histories
    original_subsets = runner._build_liquidity_subsets

    def capture_filter(manifest, histories):
        filtered, survivorship = original_filter(manifest, histories)
        captured["research_histories"] = _copy_histories(filtered)
        captured["survivorship"] = copy.deepcopy(survivorship)
        return filtered, survivorship

    def capture_subsets(symbols, histories):
        subsets = original_subsets(symbols, histories)
        captured["ranked_symbols"] = list(symbols)
        captured["liquidity_histories"] = {
            int(size): _copy_histories(rows)
            for size, rows in subsets.items()
        }
        return subsets

    runner.filter_histories = capture_filter
    runner._build_liquidity_subsets = capture_subsets
    try:
        envelope = runner.run()
    finally:
        runner.filter_histories = original_filter
        runner._build_liquidity_subsets = original_subsets
        if previous_selection_mode is None:
            os.environ.pop("SINGLE_STRATEGY_SELECTION_MODE", None)
        else:
            os.environ["SINGLE_STRATEGY_SELECTION_MODE"] = previous_selection_mode

    return envelope, captured


def _base_round_trip_cost_bps(pre_oos: dict) -> float:
    stress = pre_oos["train"]["cost_stress"]
    minimum_key = min(stress, key=lambda item: float(item))
    evidence = stress[minimum_key]
    multiplier = float(evidence["cost_multiplier"])
    if multiplier <= 0:
        raise RuntimeError("invalid base cost multiplier in ACC-002 evidence")
    return float(evidence["round_trip_cost_bps"]) / multiplier


def _pit_manifest_status(survivorship: dict) -> dict:
    status = copy.deepcopy(survivorship) if isinstance(survivorship, dict) else {}
    status["survivorship_safe"] = status.get("promotion_allowed") is True
    return status


def build_selection_audit(envelope: dict, captured: dict) -> dict:
    """Build an immutable audit artifact from one canonical selection-mode run."""
    if not verify_research_envelope(envelope):
        raise RuntimeError("canonical ACC-002 research envelope failed integrity verification")
    payload = envelope["payload"]
    if payload.get("acc") != "ACC-002":
        raise RuntimeError("unexpected research payload type")
    if payload.get("horizon") != "24h":
        raise RuntimeError("audit refuses non-24h ACC-002 evidence")
    if payload.get("selection_mode") is not True:
        raise RuntimeError("audit requires canonical SELECTION mode")
    if int(payload.get("untouched_oos_opened_for_candidate_count") or 0) != 0:
        raise RuntimeError("audit refuses evidence after untouched OOS was opened")

    selected = payload.get("selected_evaluation")
    if isinstance(selected, dict):
        untouched = selected.get("untouched_oos")
        if not isinstance(untouched, dict) or untouched.get("status") != "LOCKED_UNTOUCHED_OOS":
            raise RuntimeError("selected ACC-002 candidate does not preserve locked untouched OOS")

    ranked_symbols = captured.get("ranked_symbols")
    research_histories = captured.get("research_histories")
    liquidity_histories = captured.get("liquidity_histories")
    survivorship = captured.get("survivorship")
    if not isinstance(ranked_symbols, list) or not ranked_symbols:
        raise RuntimeError("ranked universe was not captured")
    if not isinstance(research_histories, dict) or not research_histories:
        raise RuntimeError("exact normalized research histories were not captured")
    if not isinstance(liquidity_histories, dict):
        raise RuntimeError("liquidity subset inputs were not captured")

    source_by_symbol = {
        symbol: f"OKX completed history, /api/v5/market/history-candles, instId={symbol}"
        for symbol in research_histories
    }
    dataset_manifest = build_dataset_manifest(
        research_histories,
        ranked_symbols=[str(symbol) for symbol in ranked_symbols],
        bar=str(payload["bar"]),
        source_by_symbol=source_by_symbol,
        point_in_time_universe=_pit_manifest_status(survivorship if isinstance(survivorship, dict) else {}),
    )

    policy = payload["liquidity_stability_policy"]
    predeclared_subsets = [int(value) for value in policy["predeclared_subsets"]]
    candidates = payload.get("candidates") or []
    if candidates:
        lookback_grid = [candidate["lookbacks"] for candidate in candidates]
        first_pre = next(iter(candidates[0]["liquidity_subsets"].values()))["pre_oos"]
        base_cost_bps = _base_round_trip_cost_bps(first_pre)
        stress_grid = sorted(float(value) for value in first_pre["train"]["cost_stress"])
    else:
        lookback_grid = runner.HORIZON_PROFILES["24h"]["lookback_grid"]
        base_cost_bps = float(os.getenv("CROSS_ASSET_ROUND_TRIP_COST_BPS", "12"))
        stress_grid = list(CrossAssetConfig().cost_stress_multipliers)

    declared_contract = declared_search_contract(
        lookback_grid=lookback_grid,
        liquidity_subsets=predeclared_subsets,
        minimum_passing_liquidity_subsets=int(policy["minimum_passing_subsets_per_candidate"]),
        minimum_stable_candidates=int(payload["parameter_stability"]["minimum_eligible_candidates"]),
        cost_stress_multipliers=stress_grid,
    )

    audited_candidates = []
    primary_subset = policy.get("primary_oos_subset")
    for candidate in candidates:
        subset_audits = {}
        for size_text, subset in candidate["liquidity_subsets"].items():
            size = int(size_text)
            exact_histories = liquidity_histories.get(size)
            if not isinstance(exact_histories, dict) or not exact_histories:
                raise RuntimeError(f"exact scored histories missing for Top-{size}")
            pre_oos = subset["pre_oos"]
            predicate = selection_predicate_details(pre_oos)
            if predicate["passes_all"] is not bool(subset["eligible_pre_oos"]):
                raise RuntimeError(f"selection predicate drift detected for Top-{size}")

            config = CrossAssetConfig(
                lookbacks=tuple(int(value) for value in candidate["lookbacks"]),
                forward_bars=int(pre_oos["forward_bars"]),
                round_trip_cost_bps=_base_round_trip_cost_bps(pre_oos),
                min_assets=8,
            )
            if primary_subset is not None:
                expected_fingerprint = runner._candidate_fingerprint(
                    horizon=str(payload["horizon"]),
                    bar=str(payload["bar"]),
                    config=config,
                    primary_liquidity_subset=int(primary_subset),
                )
                if expected_fingerprint != candidate.get("candidate_fingerprint"):
                    raise RuntimeError("candidate fingerprint/configuration drift detected")

            panel = build_cross_section_panel(exact_histories, config)
            recomputed_pre_oos = runner.evaluate_pre_oos(panel, config)
            if runner.sha256_hex(recomputed_pre_oos) != runner.sha256_hex(pre_oos):
                raise RuntimeError(f"pre-OOS evidence does not reproduce from captured Top-{size} rows")
            ranges = purged_split_ranges(len(panel), config.forward_bars)
            expected_pre_ranges = {
                "train": list(ranges["train"]),
                "validation": list(ranges["validation"]),
            }
            if pre_oos.get("split_ranges") != expected_pre_ranges:
                raise RuntimeError(f"chronological split drift detected for Top-{size}")
            boundaries = split_timestamp_boundaries(panel, ranges)

            subset_audits[str(size)] = {
                "requested_assets": int(subset["requested_assets"]),
                "resolved_assets": int(subset["resolved_assets"]),
                "scored_symbols": sorted(exact_histories),
                "selection_predicate": predicate,
                "split_boundaries": boundaries,
                "pre_oos_reproduced_from_dataset": True,
                "untouched_oos_scored": False,
                "research_only": True,
                "trade_authority": False,
            }
        audited_candidates.append({
            "index": int(candidate["index"]),
            "lookbacks": list(candidate["lookbacks"]),
            "candidate_fingerprint": candidate.get("candidate_fingerprint"),
            "liquidity_stability": copy.deepcopy(candidate["liquidity_stability"]),
            "eligible_pre_oos": bool(candidate["eligible_pre_oos"]),
            "liquidity_subsets": subset_audits,
        })

    audit_payload = {
        "artifact_type": "ACC002_SELECTION_EVIDENCE_AUDIT",
        "audit_schema_version": AUDIT_SCHEMA_VERSION,
        "source_research_payload_sha256": envelope["integrity"]["payload_sha256"],
        "source_generated_at": payload["generated_at"],
        "horizon": payload["horizon"],
        "bar": payload["bar"],
        "dataset_manifest": dataset_manifest,
        "declared_search_contract": declared_contract,
        "supported_liquidity_subsets": list(policy["supported_subsets"]),
        "candidates": audited_candidates,
        "point_in_time_universe": copy.deepcopy(payload["point_in_time_universe"]),
        "cost_evidence": {
            "base_round_trip_cost_bps": base_cost_bps,
            "stress_multipliers": stress_grid,
            "metric_semantics": (
                "cross-sectional top-minus-bottom return spread proxy net of declared round-trip cost; "
                "this is research evidence, not executable portfolio P&L or real profit"
            ),
        },
        "selection_result": {
            "parameter_stability": copy.deepcopy(payload["parameter_stability"]),
            "selected_candidate_present": selected is not None,
            "untouched_oos_status": "LOCKED_UNTOUCHED_OOS",
            "untouched_oos_opened_for_candidate_count": 0,
            "eligible_for_promotion_review": False,
        },
        "scientific_limitations": {
            "point_in_time_membership_verified": payload["point_in_time_universe"].get("promotion_allowed") is True,
            "promotion_grade": payload["point_in_time_universe"].get("promotion_allowed") is True,
            "raw_rows_archived_in_artifact": False,
            "dataset_bound_by_sha256": True,
            "pre_oos_reproduced_from_captured_rows": True,
            "warning": (
                "A dataset hash binds the exact normalized rows scored in this run. It does not repair unavailable "
                "historical point-in-time membership and does not turn the spread proxy into executable P&L."
            ),
        },
        "research_only": True,
        "live_approved": False,
        "trade_authority": False,
        "promotion_authority": False,
    }
    return seal_research_payload(audit_payload)


def run_audited_selection() -> dict:
    envelope, captured = _capture_selection_inputs()
    return build_selection_audit(envelope, captured)


def main() -> None:
    audit = run_audited_selection()
    target = Path(os.getenv("ACC002_SELECTION_AUDIT_PATH", DEFAULT_OUTPUT_PATH))
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_suffix(target.suffix + ".tmp")
    temporary.write_text(json.dumps(audit, sort_keys=True), encoding="utf-8")
    temporary.replace(target)
    payload = audit["payload"]
    print(json.dumps({
        "artifact_type": payload["artifact_type"],
        "source_generated_at": payload["source_generated_at"],
        "dataset_sha256": payload["dataset_manifest"]["dataset_sha256"],
        "point_in_time_membership_verified": payload["scientific_limitations"]["point_in_time_membership_verified"],
        "eligible_candidate_count": payload["selection_result"]["parameter_stability"]["eligible_candidate_count"],
        "untouched_oos_status": payload["selection_result"]["untouched_oos_status"],
        "research_only": True,
        "trade_authority": False,
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
