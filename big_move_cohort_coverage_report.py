"""Actionable, outcome-blind diagnostics for Cohort 001 PIT coverage.

This module does not validate evidence itself and must never open labels. It consumes
only the fail-closed result emitted by ``big_move_cohort_preflight.evaluate_coverage``
and turns exclusions/threshold shortfalls into a deterministic data-build report.

The purpose is operational: when real retained PIT evidence is incomplete, workers
should know exactly which evidence family is blocking coverage instead of weakening
scientific gates or opening outcomes early.
"""

from __future__ import annotations

from collections import Counter
import hashlib
import json
from typing import Any

REPORT_SCHEMA = "two_x_cohort_coverage_blocker_report.v1"
COVERAGE_RESULT_SCHEMA = "two_x_cohort_coverage_result.v1"

# Frozen acquisition order from issue #514 / Cohort 001 handoff. This is not a
# ranking feature and cannot change cohort membership or matched-control pools.
BUILD_GROUPS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("stable_identity", ("identity",)),
    ("historical_membership_listing", ("member", "tradable", "listing_age_days")),
    ("price_liquidity_returns", ("price", "liquidity_usd", "return_30d", "volatility_30d")),
    ("pit_market_cap", ("market_cap_usd",)),
    ("pit_float_supply", ("float_supply",)),
    ("pit_sector", ("sector",)),
    ("btc_regime", ("regime",)),
)


def _digest(value: Any) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _nonnegative_int(value: Any, *, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a nonnegative integer")
    return value


def _validate_inputs(contract: dict[str, Any], coverage: dict[str, Any]) -> None:
    if not isinstance(contract, dict) or not isinstance(coverage, dict):
        raise ValueError("contract and coverage must be objects")
    required = contract.get("required_features")
    if not isinstance(required, list) or not required or any(
        not isinstance(field, str) or not field for field in required
    ):
        raise ValueError("contract.required_features must be a non-empty string list")
    thresholds = contract.get("coverage_thresholds")
    if not isinstance(thresholds, dict):
        raise ValueError("contract.coverage_thresholds missing")
    for key in ("minimum_assets", "minimum_snapshots", "minimum_decisions_per_asset"):
        value = thresholds.get(key)
        if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
            raise ValueError(f"contract.coverage_thresholds.{key} must be a positive integer")

    if coverage.get("schema") != COVERAGE_RESULT_SCHEMA:
        raise ValueError("unexpected coverage result schema")
    if coverage.get("status") not in {"COVERAGE_BLOCKED", "READY_FOR_LABEL_OPEN"}:
        raise ValueError("unexpected coverage status")
    if coverage.get("prediction_authority") is not False or coverage.get("trade_authority") is not False:
        raise ValueError("coverage result must not grant prediction/trade authority")
    if coverage.get("broker_connected") is not False:
        raise ValueError("coverage result must keep broker disconnected")
    for key in (
        "accepted_snapshot_count",
        "eligible_snapshot_count",
        "excluded_snapshot_count",
        "eligible_asset_count",
        "duplicate_snapshot_key_count",
    ):
        _nonnegative_int(coverage.get(key), field=f"coverage.{key}")
    if not isinstance(coverage.get("exclusions"), list):
        raise ValueError("coverage.exclusions must be a list")
    if not isinstance(coverage.get("per_asset_snapshot_counts"), dict):
        raise ValueError("coverage.per_asset_snapshot_counts must be an object")


def _reason_feature_hits(reason: str, required_features: list[str]) -> set[str]:
    hits = {field for field in required_features if field in reason}
    if "identity" in reason:
        hits.add("identity")
    return hits


def build_blocker_report(contract: dict[str, Any], coverage: dict[str, Any]) -> dict[str, Any]:
    """Build deterministic missingness/shortfall diagnostics without opening outcomes."""
    _validate_inputs(contract, coverage)
    required_features = list(contract["required_features"])
    reason_counts: Counter[str] = Counter()
    blocker_counts: Counter[str] = Counter()

    for exclusion in coverage["exclusions"]:
        if not isinstance(exclusion, dict):
            raise ValueError("coverage exclusion must be an object")
        reasons = exclusion.get("reasons")
        if not isinstance(reasons, list) or any(not isinstance(reason, str) for reason in reasons):
            raise ValueError("coverage exclusion reasons must be a string list")
        for reason in reasons:
            reason_counts[reason] += 1
            for field in _reason_feature_hits(reason, required_features):
                blocker_counts[field] += 1

    per_asset: dict[str, int] = {}
    for asset, count in coverage["per_asset_snapshot_counts"].items():
        if not isinstance(asset, str) or not asset:
            raise ValueError("coverage per-asset key must be a non-empty string")
        per_asset[asset] = _nonnegative_int(count, field=f"coverage.per_asset_snapshot_counts.{asset}")

    thresholds = contract["coverage_thresholds"]
    min_assets = thresholds["minimum_assets"]
    min_snapshots = thresholds["minimum_snapshots"]
    min_decisions = thresholds["minimum_decisions_per_asset"]
    eligible_assets = coverage["eligible_asset_count"]
    eligible_snapshots = coverage["eligible_snapshot_count"]

    asset_decision_shortfalls = {
        asset: max(0, min_decisions - count)
        for asset, count in sorted(per_asset.items())
        if count < min_decisions
    }

    group_blockers: dict[str, int] = {}
    for group_name, fields in BUILD_GROUPS:
        group_blockers[group_name] = sum(blocker_counts.get(field, 0) for field in fields)

    if coverage["status"] == "READY_FOR_LABEL_OPEN":
        next_priority = "LABEL_STAGE_HANDOFF_ONLY_NO_OUTCOME_OPEN_IN_REPORTER"
    else:
        next_priority = next(
            (group_name for group_name, _ in BUILD_GROUPS if group_blockers[group_name] > 0),
            "POPULATE_REAL_PIT_MANIFEST_AND_RERUN_PREFLIGHT",
        )

    report: dict[str, Any] = {
        "schema": REPORT_SCHEMA,
        "coverage_status": coverage["status"],
        "coverage_result_digest": coverage.get("result_digest"),
        "contract_digest": coverage.get("contract_digest"),
        "threshold_shortfalls": {
            "assets_needed": max(0, min_assets - eligible_assets),
            "eligible_snapshots_needed": max(0, min_snapshots - eligible_snapshots),
            "minimum_decisions_per_asset": min_decisions,
            "asset_decision_shortfalls": asset_decision_shortfalls,
        },
        "blocker_counts_by_feature": dict(sorted(blocker_counts.items())),
        "blocker_counts_by_build_group": group_blockers,
        "exclusion_reason_counts": dict(sorted(reason_counts.items())),
        "duplicate_snapshot_key_count": coverage["duplicate_snapshot_key_count"],
        "next_data_build_priority": next_priority,
        "scientific_rules": {
            "outcomes_opened": False,
            "thresholds_weakened": False,
            "already_moved_assets_backfilled": False,
            "matched_control_membership_changed": False,
        },
        "outcome_access": "SEALED_IN_THIS_REPORTER",
        "forward_formation_status": "BLOCKED_UNTIL_TRUSTED_RECEIPT",
        "prediction_authority": False,
        "trade_authority": False,
        "broker_connected": False,
    }
    report["report_digest"] = _digest(report)
    return report
