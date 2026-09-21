"""Fail-closed validator for the pre-outcome 2x tradability contract.

This module deliberately validates only the frozen research contract. It does not open
historical outcomes, infer tradability from ADV alone, form prospective candidates, or
connect to a broker. Strict execution labels require later PIT microstructure evidence.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

SCHEMA = "two_x_tradability_precommitment.v1"
ARTIFACT_ID = "2X-TRADABILITY-001-v1"
EXPECTED_NOTIONAL_BANDS = (1_000, 10_000, 50_000, 100_000)
REQUIRED_PRIMARY_METRICS = {
    "precision_at_k",
    "tradable_precision_at_k_by_notional_band",
    "lift_over_matched_base_rate",
    "pr_auc",
}
FORBIDDEN_OUTCOME_KEYS = {
    "actual_2x",
    "actual_hit",
    "event_outcome",
    "future_return",
    "future_max_return",
    "future_min_return",
    "hit_time",
    "resolved_outcome",
    "winner",
}


def _finite_number(value: Any, *, field: str, positive: bool = False) -> float:
    if type(value) is bool:
        raise ValueError(f"{field} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if not math.isfinite(number):
        raise ValueError(f"{field} must be finite")
    if positive and number <= 0:
        raise ValueError(f"{field} must be > 0")
    return number


def _find_forbidden_outcome_key(value: Any, path: str = "root") -> str | None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_lower = str(key).lower()
            if key_lower in FORBIDDEN_OUTCOME_KEYS:
                return f"{path}.{key}"
            found = _find_forbidden_outcome_key(child, f"{path}.{key}")
            if found:
                return found
    elif isinstance(value, list):
        for index, child in enumerate(value):
            found = _find_forbidden_outcome_key(child, f"{path}[{index}]")
            if found:
                return found
    return None


def validate_tradability_contract(contract: dict[str, Any]) -> dict[str, Any]:
    """Validate a frozen, outcome-blind tradability precommitment.

    The return value is a small machine-readable readiness summary. ``READY_FOR_DATA``
    means only that the contract is safe to use for PIT data collection; it does not
    mean any asset/event is tradable and grants no prediction authority.
    """
    if not isinstance(contract, dict):
        raise ValueError("tradability contract must be an object")
    if contract.get("schema") != SCHEMA:
        raise ValueError("unexpected tradability contract schema")
    if contract.get("artifact_id") != ARTIFACT_ID:
        raise ValueError("unexpected tradability contract artifact_id")
    if contract.get("outcome_access_at_freeze") != "SEALED":
        raise ValueError("tradability contract must be frozen before outcome access")
    if contract.get("prospective_candidate_authority") is not False:
        raise ValueError("tradability contract cannot grant prospective candidate authority")

    leaked = _find_forbidden_outcome_key(contract)
    if leaked:
        raise ValueError(f"outcome-derived field is forbidden before label opening: {leaked}")

    principles = contract.get("principles")
    if not isinstance(principles, dict):
        raise ValueError("principles missing")
    required_principles = {
        "baseline_universe_effect": "NONE",
        "baseline_liquidity_gate_is_not_execution_proof": True,
        "adv_only_cannot_establish_strict_tradability": True,
        "missing_microstructure_policy": "UNKNOWN_TRADABILITY",
        "no_post_outcome_threshold_changes": True,
        "no_today_survivor_reconstruction": True,
    }
    for key, expected in required_principles.items():
        if principles.get(key) != expected:
            raise ValueError(f"principles.{key} must equal {expected!r}")

    bands = contract.get("execution_bands_usd")
    if not isinstance(bands, list) or tuple(bands) != EXPECTED_NOTIONAL_BANDS:
        raise ValueError("execution_bands_usd must equal frozen notional bands")
    for index, band in enumerate(bands):
        _finite_number(band, field=f"execution_bands_usd[{index}]", positive=True)

    window = contract.get("strict_microstructure_window")
    if not isinstance(window, dict):
        raise ValueError("strict_microstructure_window missing")
    lookback = _finite_number(window.get("lookback_hours"), field="lookback_hours", positive=True)
    snapshots = _finite_number(
        window.get("minimum_independent_snapshots"),
        field="minimum_independent_snapshots",
        positive=True,
    )
    max_age = _finite_number(
        window.get("maximum_snapshot_age_minutes"),
        field="maximum_snapshot_age_minutes",
        positive=True,
    )
    missing = _finite_number(
        window.get("maximum_missing_fraction"), field="maximum_missing_fraction"
    )
    if not 0 <= missing < 1:
        raise ValueError("maximum_missing_fraction must be in [0,1)")
    if snapshots < 2:
        raise ValueError("strict tradability requires multiple independent snapshots")
    if max_age > lookback * 60:
        raise ValueError("maximum snapshot age cannot exceed lookback window")
    raw_fields = window.get("required_raw_fields")
    required_raw = {
        "timestamp",
        "best_bid",
        "best_ask",
        "bid_depth_ladder",
        "ask_depth_ladder",
        "venue",
        "symbol",
    }
    if not isinstance(raw_fields, list) or not required_raw.issubset(set(raw_fields)):
        raise ValueError("strict microstructure window is missing required raw fields")

    strict = contract.get("strict_band_rules")
    if not isinstance(strict, dict):
        raise ValueError("strict_band_rules missing")
    _finite_number(strict.get("maximum_median_spread_bps"), field="maximum_median_spread_bps", positive=True)
    _finite_number(strict.get("maximum_entry_vwap_slippage_bps"), field="maximum_entry_vwap_slippage_bps", positive=True)
    _finite_number(strict.get("depth_horizon_bps"), field="depth_horizon_bps", positive=True)
    coverage_ratio = _finite_number(
        strict.get("minimum_depth_coverage_ratio"),
        field="minimum_depth_coverage_ratio",
        positive=True,
    )
    if coverage_ratio < 1:
        raise ValueError("minimum_depth_coverage_ratio cannot be below 1")

    proxy = contract.get("proxy_liquidity_tag")
    if not isinstance(proxy, dict):
        raise ValueError("proxy_liquidity_tag missing")
    if proxy.get("authority") != "DESCRIPTIVE_ONLY":
        raise ValueError("ADV proxy cannot receive strict tradability authority")
    _finite_number(
        proxy.get("minimum_median_quote_volume_usd"),
        field="minimum_median_quote_volume_usd",
        positive=True,
    )
    adv_fraction = _finite_number(
        proxy.get("maximum_band_to_median_daily_quote_volume_fraction"),
        field="maximum_band_to_median_daily_quote_volume_fraction",
        positive=True,
    )
    if adv_fraction >= 1:
        raise ValueError("ADV proxy fraction must be < 1")

    provenance = contract.get("data_provenance_contract")
    if not isinstance(provenance, dict):
        raise ValueError("data_provenance_contract missing")
    requirements = provenance.get("requirements")
    if not isinstance(requirements, list):
        raise ValueError("data provenance requirements missing")
    required_provenance = {
        "exact provider/venue identity",
        "raw capture or archive bytes retained",
        "dataset and raw-artifact hashes",
        "gap/outage/staleness masks",
        "PIT historical venue membership",
        "no silent proxy substitution",
    }
    if not required_provenance.issubset(set(requirements)):
        raise ValueError("data provenance contract is missing fail-closed requirements")

    evaluation = contract.get("evaluation_precommitment")
    if not isinstance(evaluation, dict):
        raise ValueError("evaluation_precommitment missing")
    metrics = evaluation.get("primary_metrics")
    if not isinstance(metrics, list) or not REQUIRED_PRIMARY_METRICS.issubset(set(metrics)):
        raise ValueError("rare-event primary metrics are incomplete")
    if evaluation.get("raw_accuracy_is_primary") is not False:
        raise ValueError("raw accuracy cannot be the primary rare-event metric")
    if evaluation.get("coverage_mask_must_be_frozen_before_outcomes") is not True:
        raise ValueError("coverage mask must be frozen before outcomes")
    minimum_events = evaluation.get("minimum_independent_2x_events_for_inferential_claim")
    if type(minimum_events) is bool or not isinstance(minimum_events, int) or minimum_events < 20:
        raise ValueError("inferential 2x claims require at least 20 independent events")

    authority = contract.get("authority")
    if not isinstance(authority, dict) or any(
        authority.get(key) is not False
        for key in ("prediction_authority", "promotion_authority", "broker_connected", "live_trading")
    ):
        raise ValueError("tradability precommitment cannot grant trading/prediction authority")

    return {
        "status": "READY_FOR_DATA",
        "artifact_id": ARTIFACT_ID,
        "execution_bands_usd": list(EXPECTED_NOTIONAL_BANDS),
        "outcomes_opened": False,
        "strict_tradability_established": False,
    }


def load_and_validate(path: str | Path) -> dict[str, Any]:
    try:
        raw = Path(path).read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError("tradability contract is unavailable") from exc
    try:
        contract = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("tradability contract must be valid JSON") from exc
    return validate_tradability_contract(contract)
