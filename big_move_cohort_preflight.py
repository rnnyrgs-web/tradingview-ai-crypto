"""Fail-closed pre-outcome coverage gate for <=90 day 2x+ cohort research.

This module does not create forward forecasts, open outcome labels, or grant trading
authority. It only validates whether a historical point-in-time coverage manifest
is safe enough to pass to the separately-owned event/matched-control builder.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
import re
from typing import Any

SCHEMA = "two_x_cohort_preflight.v1"
RESULT_SCHEMA = "two_x_cohort_coverage_result.v1"
FORBIDDEN_OUTCOME_KEYS = {
    "outcome",
    "label",
    "reached_2x",
    "future_return",
    "forward_return",
    "max_forward_price",
    "first_target_hit_at",
    "target_hit_at",
    "resolved_at",
    "resolution",
}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def digest(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _utc(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field} must be an RFC3339 UTC timestamp ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid RFC3339 timestamp") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise ValueError(f"{field} must be UTC")
    return parsed


def _walk_forbidden(value: Any, path: str = "$") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            key_text = str(key).strip().lower()
            if key_text in FORBIDDEN_OUTCOME_KEYS:
                raise ValueError(
                    f"outcome-derived key forbidden before label-open: {path}.{key}"
                )
            _walk_forbidden(child, f"{path}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            _walk_forbidden(child, f"{path}[{index}]")


def _validate_value(value: Any, kind: str, *, field: str) -> None:
    if kind == "bool":
        if type(value) is not bool:
            raise ValueError(f"{field}.value must be boolean")
        return
    if kind == "nonempty_string":
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{field}.value must be a non-empty string")
        return
    if kind in {"positive_number", "nonnegative_number", "finite_number"}:
        if isinstance(value, bool):
            raise ValueError(f"{field}.value must be numeric")
        try:
            number = float(value)
        except (TypeError, ValueError) as exc:
            raise ValueError(f"{field}.value must be numeric") from exc
        if not math.isfinite(number):
            raise ValueError(f"{field}.value must be finite")
        if kind == "positive_number" and number <= 0:
            raise ValueError(f"{field}.value must be > 0")
        if kind == "nonnegative_number" and number < 0:
            raise ValueError(f"{field}.value must be >= 0")
        return
    raise ValueError(f"unsupported feature kind for {field}: {kind}")


def _historical_rule(contract: dict[str, Any]) -> dict[str, Any]:
    rule = contract.get("historical_universe_rule")
    if not isinstance(rule, dict):
        raise ValueError("historical_universe_rule missing")
    return rule


def validate_contract(contract: dict[str, Any]) -> None:
    _walk_forbidden(contract)
    if contract.get("schema") != SCHEMA:
        raise ValueError("unexpected cohort preflight schema")
    if contract.get("outcome_access") != "SEALED_UNTIL_COVERAGE_READY":
        raise ValueError("outcome access must remain sealed during coverage preflight")
    if contract.get("forward_formation_status") != "BLOCKED_UNTIL_TRUSTED_RECEIPT":
        raise ValueError(
            "forward formation must remain blocked until trusted receipt integration"
        )
    _utc(contract.get("frozen_at"), field="frozen_at")

    rule = _historical_rule(contract)
    for key in ("venue", "quote_asset"):
        value = rule.get(key)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"historical_universe_rule.{key} must be a non-empty string")
    if rule.get("decision_grid") != "MONDAY_00_UTC_WEEKLY":
        raise ValueError("unsupported decision_grid; expected MONDAY_00_UTC_WEEKLY")
    grid_start = _utc(rule.get("grid_start"), field="historical_universe_rule.grid_start")
    grid_end = _utc(rule.get("grid_end"), field="historical_universe_rule.grid_end")
    if grid_start > grid_end:
        raise ValueError("historical_universe_rule grid_start must be <= grid_end")
    for key in ("listing_age_min_days", "trailing_30d_median_quote_volume_usd_min"):
        value = rule.get(key)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise ValueError(f"historical_universe_rule.{key} must be nonnegative")

    required = contract.get("required_features")
    if (
        not isinstance(required, list)
        or not required
        or len(set(required)) != len(required)
    ):
        raise ValueError("required_features must be a non-empty unique list")
    if any(not isinstance(field, str) or not field.strip() for field in required):
        raise ValueError("required feature names must be non-empty strings")

    feature_kinds = contract.get("feature_kinds")
    source_eligibility = contract.get("source_eligibility")
    identity_sources = contract.get("identity_source_eligibility")
    if not isinstance(feature_kinds, dict) or set(feature_kinds) != set(required):
        raise ValueError("feature_kinds must exactly cover required_features")
    if not isinstance(source_eligibility, dict) or set(source_eligibility) != set(required):
        raise ValueError("source_eligibility must exactly cover required_features")
    if not isinstance(identity_sources, list) or not identity_sources or any(
        not isinstance(source, str) or not source.strip() for source in identity_sources
    ):
        raise ValueError("identity_source_eligibility must be a non-empty string list")
    for field in required:
        if feature_kinds[field] not in {
            "bool",
            "nonempty_string",
            "positive_number",
            "nonnegative_number",
            "finite_number",
        }:
            raise ValueError(f"unsupported feature kind: {field}")
        allowed = source_eligibility[field]
        if not isinstance(allowed, list) or any(
            not isinstance(source, str) or not source.strip() for source in allowed
        ):
            raise ValueError(f"source_eligibility.{field} must be a string list")

    thresholds = contract.get("coverage_thresholds")
    if not isinstance(thresholds, dict):
        raise ValueError("coverage_thresholds missing")
    for key in (
        "minimum_assets",
        "minimum_snapshots",
        "minimum_decisions_per_asset",
    ):
        value = thresholds.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"{key} must be a positive integer")


def _validate_source(
    record: dict[str, Any],
    *,
    decision_at: datetime,
    field: str,
    kind: str,
    allowed_sources: list[str],
) -> None:
    if not isinstance(record, dict):
        raise ValueError(f"{field} evidence must be an object")
    for key in (
        "source_id",
        "source_version",
        "raw_digest_sha256",
        "observed_at",
        "available_at",
    ):
        if not isinstance(record.get(key), str) or not record[key].strip():
            raise ValueError(f"{field}.{key} missing")
    if not SHA256_RE.fullmatch(record["raw_digest_sha256"]):
        raise ValueError(f"{field}.raw_digest_sha256 must be lowercase SHA-256")
    if record["source_id"] not in allowed_sources:
        if not allowed_sources:
            raise ValueError(f"{field} has no source currently approved by frozen contract")
        raise ValueError(f"{field}.source_id is not approved by frozen contract")
    observed = _utc(record["observed_at"], field=f"{field}.observed_at")
    available = _utc(record["available_at"], field=f"{field}.available_at")
    if observed > available:
        raise ValueError(f"{field} observed_at cannot be after available_at")
    if available > decision_at:
        raise ValueError(f"{field} was not available by decision_at")
    if "value" not in record:
        raise ValueError(f"{field}.value missing")
    _validate_value(record["value"], kind, field=field)


def _validate_frozen_universe_gates(
    snapshot: dict[str, Any],
    contract: dict[str, Any],
    *,
    decision_at: datetime,
) -> list[str]:
    reasons: list[str] = []
    rule = _historical_rule(contract)

    if snapshot.get("venue") != rule["venue"]:
        reasons.append("venue does not match frozen historical universe")

    grid_start = _utc(rule["grid_start"], field="historical_universe_rule.grid_start")
    grid_end = _utc(rule["grid_end"], field="historical_universe_rule.grid_end")
    if decision_at < grid_start or decision_at > grid_end:
        reasons.append("decision_at lies outside frozen grid range")
    if not (
        decision_at.weekday() == 0
        and decision_at.hour == 0
        and decision_at.minute == 0
        and decision_at.second == 0
        and decision_at.microsecond == 0
    ):
        reasons.append("decision_at is not on MONDAY_00_UTC_WEEKLY grid")

    features = snapshot.get("features")
    if not isinstance(features, dict):
        return reasons

    listing = features.get("listing_age_days")
    if isinstance(listing, dict):
        try:
            listing_value = float(listing.get("value"))
            if listing_value < float(rule["listing_age_min_days"]):
                reasons.append("listing_age_days below frozen minimum")
        except (TypeError, ValueError):
            pass

    liquidity = features.get("liquidity_usd")
    if isinstance(liquidity, dict):
        try:
            liquidity_value = float(liquidity.get("value"))
            if liquidity_value < float(rule["trailing_30d_median_quote_volume_usd_min"]):
                reasons.append("liquidity_usd below frozen minimum")
        except (TypeError, ValueError):
            pass

    for field in ("tradable", "member"):
        evidence = features.get(field)
        if isinstance(evidence, dict) and evidence.get("value") is not True:
            reasons.append(f"{field} must be true at decision_at")

    return reasons


def validate_snapshot(
    snapshot: dict[str, Any], contract: dict[str, Any]
) -> tuple[bool, tuple[str, ...]]:
    _walk_forbidden(snapshot)
    reasons: list[str] = []
    try:
        decision_at = _utc(snapshot.get("decision_at"), field="decision_at")
    except ValueError as exc:
        return False, (str(exc),)

    for key in ("stable_asset_id", "venue", "venue_symbol"):
        value = snapshot.get(key)
        if not isinstance(value, str) or not value.strip():
            reasons.append(f"{key} missing")

    reasons.extend(
        _validate_frozen_universe_gates(snapshot, contract, decision_at=decision_at)
    )

    identity = snapshot.get("identity")
    if not isinstance(identity, dict):
        reasons.append("identity evidence missing")
    else:
        try:
            valid_from = _utc(identity.get("valid_from"), field="identity.valid_from")
            valid_to_raw = identity.get("valid_to")
            valid_to = (
                _utc(valid_to_raw, field="identity.valid_to")
                if valid_to_raw is not None
                else None
            )
            if decision_at < valid_from or (
                valid_to is not None and decision_at >= valid_to
            ):
                raise ValueError("decision_at lies outside stable identity interval")
            _validate_source(
                identity.get("evidence"),
                decision_at=decision_at,
                field="identity.evidence",
                kind="nonempty_string",
                allowed_sources=contract["identity_source_eligibility"],
            )
        except ValueError as exc:
            reasons.append(str(exc))

    features = snapshot.get("features")
    if not isinstance(features, dict):
        reasons.append("features missing")
    else:
        for field in contract["required_features"]:
            try:
                _validate_source(
                    features.get(field),
                    decision_at=decision_at,
                    field=field,
                    kind=contract["feature_kinds"][field],
                    allowed_sources=contract["source_eligibility"][field],
                )
            except ValueError as exc:
                reasons.append(str(exc))

    return not reasons, tuple(sorted(set(reasons)))


def _snapshot_identity_key(snapshot: dict[str, Any]) -> tuple[str, str, str] | None:
    asset = snapshot.get("stable_asset_id")
    venue = snapshot.get("venue")
    decision_at = snapshot.get("decision_at")
    if not all(isinstance(value, str) and value.strip() for value in (asset, venue, decision_at)):
        return None
    return asset, venue, decision_at


def evaluate_coverage(
    contract: dict[str, Any], snapshots: list[dict[str, Any]]
) -> dict[str, Any]:
    validate_contract(contract)
    if not isinstance(snapshots, list):
        raise ValueError("snapshots must be a list")
    _walk_forbidden(snapshots)

    key_counts = Counter(
        key
        for snapshot in snapshots
        if isinstance(snapshot, dict)
        for key in [_snapshot_identity_key(snapshot)]
        if key is not None
    )
    duplicate_keys = {key for key, count in key_counts.items() if count > 1}

    accepted: list[dict[str, Any]] = []
    excluded: list[dict[str, Any]] = []
    per_asset = Counter()
    for index, snapshot in enumerate(snapshots):
        if not isinstance(snapshot, dict):
            excluded.append({"index": index, "reasons": ["snapshot must be an object"]})
            continue

        key = _snapshot_identity_key(snapshot)
        if key is not None and key in duplicate_keys:
            excluded.append(
                {
                    "index": index,
                    "stable_asset_id": snapshot.get("stable_asset_id"),
                    "decision_at": snapshot.get("decision_at"),
                    "reasons": [
                        "duplicate stable_asset_id/venue/decision_at snapshot is ambiguous and cannot count toward coverage"
                    ],
                }
            )
            continue

        ok, reasons = validate_snapshot(snapshot, contract)
        if ok:
            accepted.append(snapshot)
            per_asset[snapshot["stable_asset_id"]] += 1
        else:
            excluded.append(
                {
                    "index": index,
                    "stable_asset_id": snapshot.get("stable_asset_id"),
                    "decision_at": snapshot.get("decision_at"),
                    "reasons": list(reasons),
                }
            )

    thresholds = contract["coverage_thresholds"]
    eligible_assets = sorted(
        asset
        for asset, count in per_asset.items()
        if count >= thresholds["minimum_decisions_per_asset"]
    )
    eligible_snapshot_count = sum(
        count for asset, count in per_asset.items() if asset in eligible_assets
    )
    ready = (
        len(eligible_assets) >= thresholds["minimum_assets"]
        and eligible_snapshot_count >= thresholds["minimum_snapshots"]
    )
    status = "READY_FOR_LABEL_OPEN" if ready else "COVERAGE_BLOCKED"
    result = {
        "schema": RESULT_SCHEMA,
        "contract_digest": digest(contract),
        "snapshot_manifest_digest": digest(snapshots),
        "status": status,
        "accepted_snapshot_count": len(accepted),
        "eligible_snapshot_count": eligible_snapshot_count,
        "excluded_snapshot_count": len(excluded),
        "eligible_asset_count": len(eligible_assets),
        "eligible_assets": eligible_assets,
        "per_asset_snapshot_counts": dict(sorted(per_asset.items())),
        "duplicate_snapshot_key_count": len(duplicate_keys),
        "exclusions": excluded,
        "outcome_access": (
            "MAY_OPEN_ONLY_IN_SEPARATE_LABEL_STAGE" if ready else "SEALED"
        ),
        "forward_formation_status": "BLOCKED_UNTIL_TRUSTED_RECEIPT",
        "prediction_authority": False,
        "trade_authority": False,
        "broker_connected": False,
    }
    result["result_digest"] = digest(result)
    return result
