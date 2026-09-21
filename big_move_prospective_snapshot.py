"""Fail-closed prospective <=90-day 2x research snapshot boundary.

This module fingerprints outcome-blind evidence only. It grants no ranking, prediction,
formation, promotion, broker, or trading authority. A snapshot's own timestamps are
self-reported; downstream use as prospective evidence requires a trusted append-only,
server-time receipt.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from typing import Any, Iterable

CONTRACT_SCHEMA = "two_x_prospective_snapshot_contract.v1"
SNAPSHOT_SCHEMA = "two_x_prospective_snapshot.v1"
RESULT_SCHEMA = "two_x_prospective_snapshot_result.v1"
FEATURE_VALUE_SCHEMA = "two_x_feature_values.v1"
TRADABILITY_ARTIFACT_ID = "2X-TRADABILITY-001-v1"
TRADABILITY_CONTRACT_GIT_BLOB_SHA = "525b6a794e763569fbc9430f70fc725b10388b85"
TRADABILITY_PATH = Path(__file__).resolve().parent / "money_intelligence" / "2x_tradability_precommitment_v1.json"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SAFE_TOKEN_RE = re.compile(r"^[A-Za-z0-9_.:/+-]{1,128}$")
ALLOWED_CLASSIFICATIONS = {"FACT", "INFERENCE", "HYPOTHESIS", "UNKNOWN"}
ALLOWED_RECEIPT_KINDS = {
    "TRUSTED_REMOTE_ACQUISITION_ATTESTATION",
    "TRUSTED_DB_REFERENCE_RECEIPT",
    "PROVIDER_NATIVE_IMMUTABLE_RECEIPT",
    "UNVERIFIED_RESEARCH_RECEIPT",
}
FORBIDDEN_FUTURE_KEYS = {
    "outcome", "label", "reached_2x", "future_return", "forward_return",
    "max_forward_price", "first_target_hit_at", "target_hit_at", "resolved_at",
    "resolution", "realized_pnl", "realized_return", "prediction_probability",
    "calibrated_probability", "rank_score",
}
CONTRACT_KEYS = {
    "schema", "artifact_id", "frozen_at", "parent_issue", "cohort_issue",
    "intelligence_issue", "data_issue", "purpose", "outcome_access",
    "historical_selection_status", "target_multiple", "max_horizon_days",
    "feature_value_schema", "feature_families", "mandatory_for_mechanism_review",
    "freshness_max_age_seconds", "freshness_rationale", "strict_tradability_binding",
    "snapshot_semantics", "evidence_argument_policy",
    "minimum_independent_2x_events_for_inferential_claim", "below_minimum_policy",
    "primary_future_metrics_when_powered", "explicit_non_authorities",
    "formation_authority", "prediction_authority", "promotion_authority",
    "broker_connected", "live_trading",
}
SNAPSHOT_KEYS = {"schema", "snapshot_id", "information_cutoff", "created_at", "assets"}
ASSET_KEYS = {
    "asset_id", "venue_symbols", "horizon_days", "target_multiple", "invalidation_rule",
    "features", "evidence_for", "evidence_against",
}
KNOWN_RECORD_KEYS = {
    "status", "source_id", "source_locator", "source_observed_at", "source_available_at",
    "captured_at", "raw_sha256", "receipt_sha256", "receipt_kind", "transform_id",
    "transform_version", "value",
}
UNKNOWN_RECORD_KEYS = {"status", "reason"}
ARGUMENT_KEYS = {"statement", "classification", "feature_family", "record_sha256"}
STRICT_COMMON_KEYS = {
    "state", "contract_artifact_id", "contract_git_blob_sha", "execution_band_usd",
    "microstructure_evidence_sha256",
}
STRICT_MEASURED_KEYS = STRICT_COMMON_KEYS | {"window_start_at", "window_end_at", "metrics"}
STRICT_UNKNOWN_KEYS = STRICT_COMMON_KEYS | {"reason"}
STRICT_METRIC_KEYS = {
    "independent_snapshots", "missing_fraction", "median_spread_bps",
    "entry_vwap_slippage_bps", "depth_coverage_ratio",
}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()


def digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _git_blob_sha(raw: bytes) -> str:
    header = f"blob {len(raw)}\0".encode()
    return hashlib.sha1(header + raw, usedforsecurity=False).hexdigest()  # nosec B324


def _exact_keys(value: Any, expected: set[str], field: str) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"{field} must be object")
    actual = set(value)
    if actual != expected:
        unknown = sorted(actual - expected)
        missing = sorted(expected - actual)
        raise ValueError(f"{field} schema mismatch; unknown={unknown}, missing={missing}")


def _tradability_contract() -> dict[str, Any]:
    try:
        raw = TRADABILITY_PATH.read_bytes()
    except OSError as exc:
        raise ValueError("frozen tradability contract unavailable") from exc
    if _git_blob_sha(raw) != TRADABILITY_CONTRACT_GIT_BLOB_SHA:
        raise ValueError("frozen tradability contract Git blob mismatch")
    try:
        contract = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ValueError("frozen tradability contract malformed") from exc
    if contract.get("artifact_id") != TRADABILITY_ARTIFACT_ID:
        raise ValueError("frozen tradability contract artifact mismatch")
    return contract


def _utc(value: Any, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field} must be RFC3339 UTC ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{field} invalid timestamp") from exc
    if parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError(f"{field} must be UTC")
    return parsed


def _nonempty(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be non-empty")
    return value.strip()


def _safe_token(value: Any, field: str) -> str:
    text = _nonempty(value, field)
    if not SAFE_TOKEN_RE.fullmatch(text):
        raise ValueError(f"{field} must be a bounded safe token")
    return text


def _sha(value: Any, field: str) -> str:
    if not isinstance(value, str) or not SHA256_RE.fullmatch(value):
        raise ValueError(f"{field} must be lowercase SHA-256")
    return value


def _walk_forbidden(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if str(key).strip().lower() in FORBIDDEN_FUTURE_KEYS:
                raise ValueError(f"future/outcome-derived key forbidden: {path}.{key}")
            _walk_forbidden(child, f"{path}.{key}")
    elif isinstance(value, list):
        for i, child in enumerate(value):
            _walk_forbidden(child, f"{path}[{i}]")


def _number(value: Any, field: str, *, nonnegative: bool = False) -> float:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be numeric")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be numeric") from exc
    if not math.isfinite(number) or (nonnegative and number < 0):
        raise ValueError(f"{field} invalid numeric value")
    return number


def _fraction(value: Any, field: str, *, signed: bool = False) -> float:
    number = _number(value, field)
    low = -1.0 if signed else 0.0
    if not low <= number <= 1.0:
        raise ValueError(f"{field} must be in [{low},1]")
    return number


def _strict_value_shape(value: Any) -> None:
    if not isinstance(value, dict):
        raise ValueError("strict_tradability.value must be structured")
    state = value.get("state")
    if state == "UNKNOWN_TRADABILITY":
        _exact_keys(value, STRICT_UNKNOWN_KEYS, "strict_tradability.value")
        _nonempty(value.get("reason"), "strict_tradability.reason")
    elif state in {"STRICT_TRADABLE", "STRICT_NOT_TRADABLE"}:
        _exact_keys(value, STRICT_MEASURED_KEYS, "strict_tradability.value")
        _exact_keys(value.get("metrics"), STRICT_METRIC_KEYS, "strict_tradability.metrics")
    else:
        raise ValueError("strict_tradability state invalid")


def _validate_feature_value(family: str, value: Any) -> None:
    if family == "stable_identity":
        _exact_keys(value, {"canonical_asset_id"}, "stable_identity.value")
        _safe_token(value["canonical_asset_id"], "stable_identity.canonical_asset_id")
    elif family == "venue_membership":
        _exact_keys(value, {"active_spot"}, "venue_membership.value")
        if type(value["active_spot"]) is not bool:
            raise ValueError("venue_membership.active_spot must be boolean")
    elif family == "liquidity_proxy":
        _exact_keys(value, {"trailing_30d_quote_volume_usd"}, "liquidity_proxy.value")
        _number(value["trailing_30d_quote_volume_usd"], "liquidity_proxy.trailing_30d_quote_volume_usd", nonnegative=True)
    elif family == "strict_tradability":
        _strict_value_shape(value)
    elif family == "spot_participation_flow":
        expected = {
            "quote_notional_usd_7d", "aggressive_buy_share_7d", "net_flow_share_7d",
            "participation_acceleration_7d_vs_prior7d", "trade_count_acceleration_7d_vs_prior7d",
        }
        _exact_keys(value, expected, "spot_participation_flow.value")
        _number(value["quote_notional_usd_7d"], "spot_participation_flow.quote_notional_usd_7d", nonnegative=True)
        _fraction(value["aggressive_buy_share_7d"], "spot_participation_flow.aggressive_buy_share_7d")
        _fraction(value["net_flow_share_7d"], "spot_participation_flow.net_flow_share_7d", signed=True)
        _number(value["participation_acceleration_7d_vs_prior7d"], "spot_participation_flow.participation_acceleration_7d_vs_prior7d")
        _number(value["trade_count_acceleration_7d_vs_prior7d"], "spot_participation_flow.trade_count_acceleration_7d_vs_prior7d")
    elif family == "leverage_state":
        _exact_keys(value, {"funding_rate_8h", "open_interest_usd", "annualized_basis_bps"}, "leverage_state.value")
        _number(value["funding_rate_8h"], "leverage_state.funding_rate_8h")
        _number(value["open_interest_usd"], "leverage_state.open_interest_usd", nonnegative=True)
        _number(value["annualized_basis_bps"], "leverage_state.annualized_basis_bps")
    elif family == "supply_float":
        _exact_keys(value, {"circulating_supply", "free_float_supply", "unlock_90d_pct_of_float"}, "supply_float.value")
        circulating = _number(value["circulating_supply"], "supply_float.circulating_supply", nonnegative=True)
        free_float = _number(value["free_float_supply"], "supply_float.free_float_supply", nonnegative=True)
        if free_float > circulating:
            raise ValueError("supply_float.free_float_supply cannot exceed circulating_supply")
        _number(value["unlock_90d_pct_of_float"], "supply_float.unlock_90d_pct_of_float", nonnegative=True)
    elif family == "catalyst_state":
        _exact_keys(value, {"state", "category"}, "catalyst_state.value")
        if value["state"] not in {"NONE", "ACTIVE", "PENDING", "INVALIDATED"}:
            raise ValueError("catalyst_state.state invalid")
        if value["category"] not in {"NONE", "PRODUCT", "REGULATORY", "TREASURY", "EXCHANGE", "NETWORK", "OTHER"}:
            raise ValueError("catalyst_state.category invalid")
        if value["state"] == "NONE" and value["category"] != "NONE":
            raise ValueError("catalyst_state NONE must use category NONE")
    elif family == "market_regime":
        _exact_keys(value, {"regime"}, "market_regime.value")
        if value["regime"] not in {"BTC_RISK_ON", "BTC_RISK_OFF", "MIXED"}:
            raise ValueError("market_regime.regime invalid")
    elif family == "relationship_graph":
        _exact_keys(value, {"edge_types", "peer_asset_ids"}, "relationship_graph.value")
        edge_types = value["edge_types"]
        peers = value["peer_asset_ids"]
        allowed_edges = {"SECTOR", "ECOSYSTEM", "TREASURY", "FLOW", "VENUE", "OTHER"}
        if not isinstance(edge_types, list) or not edge_types or len(edge_types) != len(set(edge_types)) or not set(edge_types).issubset(allowed_edges):
            raise ValueError("relationship_graph.edge_types invalid")
        if not isinstance(peers, list) or not peers or len(peers) != len(set(peers)) or len(peers) > 64:
            raise ValueError("relationship_graph.peer_asset_ids invalid")
        for peer in peers:
            _safe_token(peer, "relationship_graph.peer_asset_id")
    else:
        raise ValueError(f"unsupported feature family: {family}")


def validate_contract(contract: dict[str, Any]) -> None:
    _walk_forbidden(contract)
    _exact_keys(contract, CONTRACT_KEYS, "contract")
    if contract.get("schema") != CONTRACT_SCHEMA or contract.get("artifact_id") != "2X-PROSPECTIVE-SNAPSHOT-001-v1":
        raise ValueError("unexpected prospective snapshot contract")
    if contract.get("feature_value_schema") != FEATURE_VALUE_SCHEMA:
        raise ValueError("unexpected feature value schema")
    _utc(contract.get("frozen_at"), "frozen_at")
    if contract.get("outcome_access") != "PROSPECTIVE_ONLY_NO_FUTURE_OUTCOMES":
        raise ValueError("contract must remain prospective-only")
    if contract.get("historical_selection_status") != "UNVALIDATED_NO_RANKING_AUTHORITY":
        raise ValueError("historical selection must remain unvalidated")
    for key in ("formation_authority", "prediction_authority", "promotion_authority", "broker_connected", "live_trading"):
        if contract.get(key) is not False:
            raise ValueError(f"{key} must be false")
    target = contract.get("target_multiple")
    if isinstance(target, bool) or not isinstance(target, (int, float)) or float(target) != 2.0:
        raise ValueError("target_multiple must be exactly 2.0")
    horizon = contract.get("max_horizon_days")
    if type(horizon) is not int or not 1 <= horizon <= 90:
        raise ValueError("max_horizon_days must be in [1,90]")

    families = contract.get("feature_families")
    expected_families = [
        "stable_identity", "venue_membership", "liquidity_proxy", "strict_tradability",
        "spot_participation_flow", "leverage_state", "supply_float", "catalyst_state",
        "market_regime", "relationship_graph",
    ]
    if families != expected_families:
        raise ValueError("feature_families must equal frozen v1 order")
    mandatory = contract.get("mandatory_for_mechanism_review")
    if not isinstance(mandatory, list) or not set(mandatory).issubset(families) or "strict_tradability" not in mandatory:
        raise ValueError("mandatory feature families invalid")
    freshness = contract.get("freshness_max_age_seconds")
    if not isinstance(freshness, dict) or set(freshness) != set(families):
        raise ValueError("freshness policy must exactly cover feature families")
    if any(type(v) is not int or v <= 0 for v in freshness.values()):
        raise ValueError("freshness ages must be positive integers")
    rationale = contract.get("freshness_rationale")
    if not isinstance(rationale, dict) or set(rationale) != set(families) or any(not isinstance(v, str) or not v.strip() for v in rationale.values()):
        raise ValueError("freshness rationale must exactly cover feature families")

    pinned = _tradability_contract()
    binding = contract.get("strict_tradability_binding")
    _exact_keys(
        binding,
        {"artifact_id", "git_blob_sha", "execution_bands_usd", "require_out_of_band_receipt_verification", "required_state_fields", "rule"},
        "strict_tradability_binding",
    )
    if binding.get("artifact_id") != TRADABILITY_ARTIFACT_ID or binding.get("git_blob_sha") != TRADABILITY_CONTRACT_GIT_BLOB_SHA:
        raise ValueError("strict tradability binding mismatch")
    if binding.get("execution_bands_usd") != pinned.get("execution_bands_usd"):
        raise ValueError("strict tradability execution bands drifted")
    if binding.get("require_out_of_band_receipt_verification") is not True:
        raise ValueError("strict tradability requires out-of-band receipt verification")
    if binding.get("required_state_fields") != ["state", "contract_artifact_id", "contract_git_blob_sha", "execution_band_usd", "microstructure_evidence_sha256"]:
        raise ValueError("strict tradability required fields drifted")
    max_micro_age = int(pinned["strict_microstructure_window"]["maximum_snapshot_age_minutes"]) * 60
    if freshness["strict_tradability"] > max_micro_age:
        raise ValueError("strict_tradability freshness exceeds frozen #519 maximum")


def _validate_record(record: Any, family: str, cutoff: datetime, created: datetime, contract: dict[str, Any]) -> None:
    if not isinstance(record, dict) or record.get("status") not in {"KNOWN", "UNKNOWN"}:
        raise ValueError(f"{family} record invalid")
    if record["status"] == "UNKNOWN":
        _exact_keys(record, UNKNOWN_RECORD_KEYS, f"{family} UNKNOWN record")
        _nonempty(record.get("reason"), f"{family}.reason")
        return

    _exact_keys(record, KNOWN_RECORD_KEYS, f"{family} KNOWN record")
    for key in ("source_id", "source_locator", "transform_id", "transform_version"):
        _nonempty(record.get(key), f"{family}.{key}")
    _sha(record.get("raw_sha256"), f"{family}.raw_sha256")
    _sha(record.get("receipt_sha256"), f"{family}.receipt_sha256")
    if record.get("receipt_kind") not in ALLOWED_RECEIPT_KINDS:
        raise ValueError(f"{family}.receipt_kind unsupported")
    observed = _utc(record.get("source_observed_at"), f"{family}.source_observed_at")
    available = _utc(record.get("source_available_at"), f"{family}.source_available_at")
    captured = _utc(record.get("captured_at"), f"{family}.captured_at")
    if not observed <= available <= captured <= cutoff <= created:
        raise ValueError(f"{family} chronology invalid")
    if (cutoff - observed).total_seconds() > contract["freshness_max_age_seconds"][family]:
        raise ValueError(f"{family} source_observed_at is stale under frozen freshness policy")
    _validate_feature_value(family, record["value"])


def _strict_state(record: dict[str, Any], cutoff: datetime, contract: dict[str, Any]) -> str:
    value = record["value"]
    _strict_value_shape(value)
    state = value["state"]
    binding = contract["strict_tradability_binding"]
    if value.get("contract_artifact_id") != binding["artifact_id"] or value.get("contract_git_blob_sha") != binding["git_blob_sha"]:
        raise ValueError("strict_tradability contract identity mismatch")
    if value.get("execution_band_usd") not in binding["execution_bands_usd"]:
        raise ValueError("strict_tradability execution band is not frozen")
    _sha(value.get("microstructure_evidence_sha256"), "strict_tradability.microstructure_evidence_sha256")
    if state == "UNKNOWN_TRADABILITY":
        return state

    pinned = _tradability_contract()
    window = pinned["strict_microstructure_window"]
    rules = pinned["strict_band_rules"]
    start = _utc(value.get("window_start_at"), "strict_tradability.window_start_at")
    end = _utc(value.get("window_end_at"), "strict_tradability.window_end_at")
    observed = _utc(record.get("source_observed_at"), "strict_tradability.source_observed_at")
    if end != observed or start > end or end > cutoff:
        raise ValueError("strict_tradability microstructure window invalid")
    if (end - start).total_seconds() > float(window["lookback_hours"]) * 3600:
        raise ValueError("strict_tradability window exceeds frozen lookback")
    if (cutoff - end).total_seconds() > float(window["maximum_snapshot_age_minutes"]) * 60:
        raise ValueError("strict_tradability microstructure evidence stale")

    metrics = value["metrics"]
    snapshots = metrics["independent_snapshots"]
    if type(snapshots) is not int or snapshots <= 0:
        raise ValueError("strict_tradability independent_snapshots invalid")
    missing = _number(metrics["missing_fraction"], "missing_fraction", nonnegative=True)
    spread = _number(metrics["median_spread_bps"], "median_spread_bps", nonnegative=True)
    slippage = _number(metrics["entry_vwap_slippage_bps"], "entry_vwap_slippage_bps", nonnegative=True)
    depth = _number(metrics["depth_coverage_ratio"], "depth_coverage_ratio", nonnegative=True)
    if missing > 1:
        raise ValueError("missing_fraction must be <= 1")
    passes = (
        snapshots >= int(window["minimum_independent_snapshots"])
        and missing <= float(window["maximum_missing_fraction"])
        and spread <= float(rules["maximum_median_spread_bps"])
        and slippage <= float(rules["maximum_entry_vwap_slippage_bps"])
        and depth >= float(rules["minimum_depth_coverage_ratio"])
    )
    if state == "STRICT_TRADABLE" and not passes:
        raise ValueError("STRICT_TRADABLE claim fails frozen #519 thresholds")
    if state == "STRICT_NOT_TRADABLE" and passes:
        raise ValueError("STRICT_NOT_TRADABLE contradicts frozen #519 thresholds")
    return state


def _verified(values: Iterable[str] | None) -> set[str]:
    if values is None:
        return set()
    if isinstance(values, (str, bytes)):
        raise ValueError("verified_receipt_sha256s must be an iterable")
    return {_sha(v, "verified_receipt_sha256") for v in values}


def _argument(arg: Any, records: dict[str, Any], families: set[str]) -> None:
    _exact_keys(arg, ARGUMENT_KEYS, "evidence argument")
    if arg.get("classification") not in ALLOWED_CLASSIFICATIONS:
        raise ValueError("evidence argument invalid")
    _nonempty(arg.get("statement"), "evidence statement")
    family = _nonempty(arg.get("feature_family"), "feature_family")
    if family not in families:
        raise ValueError("evidence feature family not frozen")
    if _sha(arg.get("record_sha256"), "record_sha256") != digest(records[family]):
        raise ValueError("evidence record_sha256 does not bind the frozen feature record")


def evaluate_snapshot(
    contract: dict[str, Any],
    snapshot: dict[str, Any],
    *,
    verified_receipt_sha256s: Iterable[str] | None = None,
) -> dict[str, Any]:
    validate_contract(contract)
    _walk_forbidden(snapshot)
    _exact_keys(snapshot, SNAPSHOT_KEYS, "snapshot")
    if snapshot.get("schema") != SNAPSHOT_SCHEMA:
        raise ValueError("unexpected prospective snapshot schema")
    _nonempty(snapshot.get("snapshot_id"), "snapshot_id")
    cutoff = _utc(snapshot.get("information_cutoff"), "information_cutoff")
    created = _utc(snapshot.get("created_at"), "created_at")
    if cutoff > created:
        raise ValueError("information_cutoff must be <= created_at")
    verified = _verified(verified_receipt_sha256s)

    assets = snapshot.get("assets")
    if not isinstance(assets, list) or not assets:
        raise ValueError("assets must be non-empty")
    families = set(contract["feature_families"])
    seen: set[str] = set()
    results = []
    for asset in assets:
        _exact_keys(asset, ASSET_KEYS, "asset")
        asset_id = _safe_token(asset.get("asset_id"), "asset_id")
        if asset_id in seen:
            raise ValueError(f"duplicate asset_id: {asset_id}")
        seen.add(asset_id)
        venue_symbols = asset.get("venue_symbols")
        if not isinstance(venue_symbols, dict) or not venue_symbols or len(venue_symbols) > 32:
            raise ValueError("venue_symbols missing or invalid")
        for venue, symbol in venue_symbols.items():
            _safe_token(venue, "venue_symbols venue")
            _safe_token(symbol, "venue_symbols symbol")
        horizon = asset.get("horizon_days")
        if type(horizon) is not int or not 1 <= horizon <= contract["max_horizon_days"]:
            raise ValueError("horizon_days outside frozen maximum")
        target = asset.get("target_multiple")
        if isinstance(target, bool) or not isinstance(target, (int, float)) or float(target) != 2.0:
            raise ValueError("target_multiple must be exactly 2.0")
        _nonempty(asset.get("invalidation_rule"), "invalidation_rule")

        records = asset.get("features")
        if not isinstance(records, dict) or set(records) != families:
            raise ValueError("features must exactly cover frozen feature_families")
        for family in sorted(families):
            _validate_record(records[family], family, cutoff, created, contract)

        evidence_for = asset.get("evidence_for")
        evidence_against = asset.get("evidence_against")
        if not isinstance(evidence_for, list) or not isinstance(evidence_against, list):
            raise ValueError("evidence_for/evidence_against must be lists")
        for arg in evidence_for + evidence_against:
            _argument(arg, records, families)

        blockers: list[str] = []
        for family in contract["mandatory_for_mechanism_review"]:
            rec = records[family]
            if rec["status"] != "KNOWN":
                blockers.append(f"MANDATORY_UNKNOWN:{family}")
            elif rec.get("receipt_kind") == "UNVERIFIED_RESEARCH_RECEIPT":
                blockers.append(f"MANDATORY_RECEIPT_KIND_UNTRUSTED:{family}")
            elif rec.get("receipt_sha256") not in verified:
                blockers.append(f"MANDATORY_RECEIPT_UNVERIFIED:{family}")

        strict = records["strict_tradability"]
        if strict["status"] != "KNOWN":
            blockers.append("STRICT_TRADABILITY_UNKNOWN")
        else:
            state = _strict_state(strict, cutoff, contract)
            if state != "STRICT_TRADABLE":
                blockers.append(f"STRICT_TRADABILITY_NOT_CLEAR:{state}")
            if strict.get("receipt_kind") == "UNVERIFIED_RESEARCH_RECEIPT":
                blockers.append("STRICT_TRADABILITY_RECEIPT_KIND_UNTRUSTED")
            elif strict.get("receipt_sha256") not in verified:
                blockers.append("STRICT_TRADABILITY_RECEIPT_UNVERIFIED")
        if not evidence_for:
            blockers.append("NO_FROZEN_EVIDENCE_FOR")
        if not evidence_against:
            blockers.append("NO_FROZEN_EVIDENCE_AGAINST")

        results.append({
            "asset_id": asset_id,
            "snapshot_record_sha256": digest(asset),
            "status": "MECHANISM_REVIEW_READY" if not blockers else "INSUFFICIENT_EVIDENCE",
            "blockers": sorted(set(blockers)),
            "formation_authority": False,
            "prospective_chronology_authority": False,
        })

    return {
        "schema": RESULT_SCHEMA,
        "contract_sha256": digest(contract),
        "snapshot_sha256": digest(snapshot),
        "asset_count": len(results),
        "assets": results,
        "verified_receipt_count": len(verified),
        "snapshot_time_authority": "SELF_REPORTED_NOT_NON_BACKDATEABLE",
        "prospective_chronology_authority": False,
        "formation_authority": False,
        "prediction_authority": False,
        "ranking_authority": False,
        "next_gate": "TRUSTED_APPEND_ONLY_SERVER_TIME_SNAPSHOT_RECEIPT_THEN_AUTHENTIC_HISTORICAL_MATCHED_CONTROL_VALIDATION",
    }
