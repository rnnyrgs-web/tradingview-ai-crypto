"""Fail-closed pre-outcome coverage gate for <=90 day 2x+ cohort research.

A retained digest proves byte integrity, not historical source authenticity. Cohort 001
therefore requires both retained-byte verification and source-native/archive proof
before any snapshot can contribute to label opening. Derived fields inherit the
source-authenticity requirements of every bound input.

This module creates no forecast, opens no outcome, and grants no trading authority.
"""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timedelta, timezone
import hashlib
import json
import math
from pathlib import Path
import re
from statistics import median
from typing import Any

from big_move_source_authenticity import (
    is_derived_source,
    validate_record_authenticity,
    verify_source_policy_pin,
)
from big_move_survivorship_resolution_queue import (
    reject_survivorship_enumeration_as_membership_lineage,
    validate_provider_native_membership_provenance,
)

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
MAX_ARTIFACT_BYTES = 16_000_000

EXACT_DERIVED_SOURCE = {
    "liquidity_usd": "TRAILING_30D_MEDIAN_QUOTE_VOLUME_USD_V1",
    "listing_age_days": "DERIVED_BINANCE_LISTING_AGE_DAYS_V1",
    "tradable": "DERIVED_BINANCE_HISTORICAL_MEMBERSHIP_V1",
    "member": "DERIVED_BINANCE_HISTORICAL_MEMBERSHIP_V1",
}
LIQUIDITY_PARAMS = {
    "window_days": 30,
    "statistic": "median",
    "measure": "quote_volume_usd",
    "completed_daily_bars_only": True,
}
LISTING_AGE_PARAMS = {
    "basis": "first_verified_venue_trade",
    "rounding": "floor_elapsed_days",
}
MEMBERSHIP_PARAMS = {"rule": "verified_market_presence_at_decision"}


def _canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


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
            if str(key).strip().lower() in FORBIDDEN_OUTCOME_KEYS:
                raise ValueError(f"outcome-derived key forbidden before label-open: {path}.{key}")
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


def _values_equal(left: Any, right: Any) -> bool:
    if type(left) is bool or type(right) is bool:
        return left is right
    if isinstance(left, (int, float)) and not isinstance(left, bool):
        try:
            return math.isclose(float(left), float(right), rel_tol=1e-12, abs_tol=1e-12)
        except (TypeError, ValueError):
            return False
    return left == right


def _historical_rule(contract: dict[str, Any]) -> dict[str, Any]:
    rule = contract.get("historical_universe_rule")
    if not isinstance(rule, dict):
        raise ValueError("historical_universe_rule missing")
    return rule


def validate_contract(contract: dict[str, Any]) -> None:
    _walk_forbidden(contract)
    verify_source_policy_pin()
    if contract.get("schema") != SCHEMA:
        raise ValueError("unexpected cohort preflight schema")
    if contract.get("outcome_access") != "SEALED_UNTIL_COVERAGE_READY":
        raise ValueError("outcome access must remain sealed during coverage preflight")
    if contract.get("forward_formation_status") != "BLOCKED_UNTIL_TRUSTED_RECEIPT":
        raise ValueError("forward formation must remain blocked until trusted receipt integration")
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
    if not isinstance(required, list) or not required or len(set(required)) != len(required):
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
            "bool", "nonempty_string", "positive_number", "nonnegative_number", "finite_number"
        }:
            raise ValueError(f"unsupported feature kind: {field}")
        allowed = source_eligibility[field]
        if not isinstance(allowed, list) or not allowed or any(
            not isinstance(source, str) or not source.strip() for source in allowed
        ):
            raise ValueError(f"source_eligibility.{field} must be a non-empty string list")
        exact = EXACT_DERIVED_SOURCE.get(field)
        if exact is not None and allowed != [exact]:
            raise ValueError(
                f"source_eligibility.{field} must be exactly {exact}; raw caller values are forbidden"
            )

    thresholds = contract.get("coverage_thresholds")
    if not isinstance(thresholds, dict):
        raise ValueError("coverage_thresholds missing")
    for key in ("minimum_assets", "minimum_snapshots", "minimum_decisions_per_asset"):
        value = thresholds.get(key)
        if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
            raise ValueError(f"{key} must be a positive integer")


def _artifact_path(root: Path | None, relpath: Any, *, field: str) -> Path:
    if root is None:
        raise ValueError(f"{field} cannot be scientifically verified without retained artifact root")
    if not isinstance(relpath, str) or not relpath.strip():
        raise ValueError(f"{field}.artifact_relpath missing")
    candidate = Path(relpath)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"{field}.artifact_relpath must stay inside retained artifact root")
    base = root.resolve()
    path = (base / candidate).resolve()
    if not path.is_relative_to(base):
        raise ValueError(f"{field}.artifact_relpath escapes retained artifact root")
    return path


def _read_verified_json(root: Path | None, relpath: Any, expected_sha256: Any, *, field: str) -> Any:
    if not isinstance(expected_sha256, str) or not SHA256_RE.fullmatch(expected_sha256):
        raise ValueError(f"{field}.sha256 must be lowercase SHA-256")
    path = _artifact_path(root, relpath, field=field)
    try:
        if path.stat().st_size > MAX_ARTIFACT_BYTES:
            raise ValueError(f"{field} retained artifact is too large")
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError(f"{field} retained artifact is unavailable") from exc
    if hashlib.sha256(raw).hexdigest() != expected_sha256:
        raise ValueError(f"{field} retained artifact SHA-256 mismatch")
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{field} retained artifact must be canonical JSON") from exc


def _mirror_record_matches_artifact(record: dict[str, Any], artifact: Any, *, field: str) -> None:
    if not isinstance(artifact, dict):
        raise ValueError(f"{field} retained evidence artifact must be an object")
    for key in ("source_id", "source_version", "observed_at", "available_at", "value", "source_proof"):
        if key not in artifact or not _values_equal(record.get(key), artifact.get(key)):
            raise ValueError(f"{field} caller metadata/value does not match retained artifact")
    if record.get("derivation") != artifact.get("derivation"):
        raise ValueError(f"{field} derivation does not match retained artifact")


def _verified_inputs(derivation: dict[str, Any], root: Path | None, *, field: str) -> list[Any]:
    inputs = derivation.get("inputs")
    if not isinstance(inputs, list) or not inputs:
        raise ValueError(f"{field}.derivation.inputs must be non-empty")
    verified = []
    for index, item in enumerate(inputs):
        if not isinstance(item, dict):
            raise ValueError(f"{field}.derivation.inputs[{index}] must be an object")
        verified.append(_read_verified_json(
            root, item.get("artifact_relpath"), item.get("sha256"),
            field=f"{field}.derivation.inputs[{index}]"
        ))
    return verified


def _expect_derivation(
    record: dict[str, Any], root: Path | None, *, field: str,
    transform_id: str, parameters: dict[str, Any] | None = None,
) -> tuple[dict[str, Any], list[Any]]:
    derivation = record.get("derivation")
    if not isinstance(derivation, dict):
        raise ValueError(f"{field}.derivation missing")
    if derivation.get("transform_id") != transform_id:
        raise ValueError(f"{field}.derivation.transform_id mismatch")
    version = derivation.get("transform_version")
    if not isinstance(version, str) or not version.strip():
        raise ValueError(f"{field}.derivation.transform_version missing")
    params = derivation.get("parameters")
    if not isinstance(params, dict):
        raise ValueError(f"{field}.derivation.parameters missing")
    if parameters is not None and params != parameters:
        raise ValueError(f"{field}.derivation.parameters violate frozen semantics")
    return derivation, _verified_inputs(derivation, root, field=field)


def _validate_liquidity_derivation(record: dict[str, Any], root: Path | None, decision_at: datetime) -> None:
    _, inputs = _expect_derivation(
        record, root, field="liquidity_usd",
        transform_id="TRAILING_30D_MEDIAN_QUOTE_VOLUME_USD_V1", parameters=LIQUIDITY_PARAMS,
    )
    expected_dates = {(decision_at.date() - timedelta(days=days)).isoformat() for days in range(1, 31)}
    by_date: dict[str, float] = {}
    for artifact in inputs:
        if not isinstance(artifact, dict) or artifact.get("schema") != "binance_daily_quote_volume.v1":
            raise ValueError("liquidity_usd input must use binance_daily_quote_volume.v1")
        rows = artifact.get("rows")
        if not isinstance(rows, list):
            raise ValueError("liquidity_usd input rows missing")
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError("liquidity_usd input row malformed")
            date = row.get("date")
            if date in by_date:
                raise ValueError("liquidity_usd input has duplicate UTC date")
            if not isinstance(date, str):
                raise ValueError("liquidity_usd input date missing")
            try:
                volume = float(row.get("quote_volume_usd"))
            except (TypeError, ValueError) as exc:
                raise ValueError("liquidity_usd input quote volume invalid") from exc
            if not math.isfinite(volume) or volume < 0:
                raise ValueError("liquidity_usd input quote volume invalid")
            by_date[date] = volume
    if expected_dates - set(by_date):
        raise ValueError("liquidity_usd requires all 30 completed UTC daily quote-volume observations")
    computed = float(median([by_date[date] for date in sorted(expected_dates)]))
    if not math.isclose(computed, float(record["value"]), rel_tol=1e-12, abs_tol=1e-9):
        raise ValueError("liquidity_usd value does not equal deterministic trailing-30d median")


def _validate_listing_age_derivation(record: dict[str, Any], root: Path | None, decision_at: datetime) -> None:
    _, inputs = _expect_derivation(
        record, root, field="listing_age_days",
        transform_id="DERIVED_BINANCE_LISTING_AGE_DAYS_V1", parameters=LISTING_AGE_PARAMS,
    )
    if len(inputs) != 1 or not isinstance(inputs[0], dict) or inputs[0].get("schema") != "binance_first_trade.v1":
        raise ValueError("listing_age_days requires one binance_first_trade.v1 input")
    first_trade = _utc(inputs[0].get("first_trade_at"), field="listing_age_days.first_trade_at")
    if first_trade > decision_at:
        raise ValueError("listing_age_days first trade cannot be after decision")
    computed = int((decision_at - first_trade).total_seconds() // 86400)
    if computed != int(float(record["value"])):
        raise ValueError("listing_age_days value does not equal deterministic first-trade age")


def _validate_membership_derivation(
    record: dict[str, Any], root: Path | None, decision_at: datetime, *, field: str,
    venue_symbol: str | None = None,
) -> None:
    _, inputs = _expect_derivation(
        record, root, field=field,
        transform_id="DERIVED_BINANCE_HISTORICAL_MEMBERSHIP_V1", parameters=MEMBERSHIP_PARAMS,
    )
    if len(inputs) != 1 or not isinstance(inputs[0], dict) or inputs[0].get("schema") != "binance_market_presence.v1":
        raise ValueError(f"{field} requires one binance_market_presence.v1 input")
    presence = inputs[0]
    reject_survivorship_enumeration_as_membership_lineage(presence)
    decision_text = decision_at.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
    if _utc(presence.get("decision_at"), field=f"{field}.presence.decision_at") != decision_at:
        raise ValueError(f"{field} presence input decision timestamp mismatch")
    if presence.get(field) is not record.get("value"):
        raise ValueError(f"{field} value does not equal retained historical presence input")

    source_proof = presence.get("source_proof")
    if not isinstance(source_proof, dict):
        raise ValueError(f"{field} presence source_proof missing")
    source_proof_sha256 = source_proof.get("sha256")
    if not isinstance(source_proof_sha256, str) or SHA256_RE.fullmatch(source_proof_sha256) is None:
        raise ValueError(f"{field} presence source_proof.sha256 must be lowercase SHA-256")

    provenance = presence.get("membership_provenance")
    if not isinstance(provenance, dict):
        raise ValueError("membership provenance is required")
    if provenance.get("source_proof_sha256") != source_proof_sha256:
        raise ValueError("membership provenance source-proof binding mismatch")
    if venue_symbol is None or not isinstance(venue_symbol, str) or not venue_symbol.strip():
        raise ValueError(f"{field} enclosing venue_symbol is required")
    validate_provider_native_membership_provenance(
        provenance,
        venue_symbol=venue_symbol,
        decision_at=decision_text,
        source_proof_sha256=source_proof_sha256,
    )


def _validate_source(
    record: dict[str, Any], *, decision_at: datetime, field: str, kind: str,
    allowed_sources: list[str], artifact_root: Path | None, venue_symbol: str | None = None,
) -> None:
    if not isinstance(record, dict):
        raise ValueError(f"{field} evidence must be an object")
    for key in (
        "source_id", "source_version", "raw_digest_sha256", "artifact_relpath", "observed_at", "available_at"
    ):
        if not isinstance(record.get(key), str) or not record[key].strip():
            raise ValueError(f"{field}.{key} missing")
    if not SHA256_RE.fullmatch(record["raw_digest_sha256"]):
        raise ValueError(f"{field}.raw_digest_sha256 must be lowercase SHA-256")
    if record["source_id"] not in allowed_sources:
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

    artifact = _read_verified_json(
        artifact_root, record["artifact_relpath"], record["raw_digest_sha256"], field=field
    )
    _mirror_record_matches_artifact(record, artifact, field=field)
    validate_record_authenticity(
        record, artifact_root=artifact_root, decision_at=decision_at, field=field
    )

    exact = EXACT_DERIVED_SOURCE.get(field)
    if exact is not None:
        if record["source_id"] != exact:
            raise ValueError(f"{field} must use frozen deterministic source {exact}")
        if field == "liquidity_usd":
            _validate_liquidity_derivation(record, artifact_root, decision_at)
        elif field == "listing_age_days":
            _validate_listing_age_derivation(record, artifact_root, decision_at)
        else:
            _validate_membership_derivation(
                record, artifact_root, decision_at, field=field, venue_symbol=venue_symbol
            )
    elif is_derived_source(record["source_id"]):
        _expect_derivation(record, artifact_root, field=field, transform_id=record["source_id"])


def _validate_frozen_universe_gates(
    snapshot: dict[str, Any], contract: dict[str, Any], *, decision_at: datetime
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
        decision_at.weekday() == 0 and decision_at.hour == 0 and decision_at.minute == 0
        and decision_at.second == 0 and decision_at.microsecond == 0
    ):
        reasons.append("decision_at is not on MONDAY_00_UTC_WEEKLY grid")
    features = snapshot.get("features")
    if not isinstance(features, dict):
        return reasons
    listing = features.get("listing_age_days")
    if isinstance(listing, dict):
        try:
            if float(listing.get("value")) < float(rule["listing_age_min_days"]):
                reasons.append("listing_age_days below frozen minimum")
        except (TypeError, ValueError):
            pass
    liquidity = features.get("liquidity_usd")
    if isinstance(liquidity, dict):
        try:
            if float(liquidity.get("value")) < float(rule["trailing_30d_median_quote_volume_usd_min"]):
                reasons.append("liquidity_usd below frozen minimum")
        except (TypeError, ValueError):
            pass
    for field in ("tradable", "member"):
        evidence = features.get(field)
        if isinstance(evidence, dict) and evidence.get("value") is not True:
            reasons.append(f"{field} must be true at decision_at")
    return reasons


def validate_snapshot(
    snapshot: dict[str, Any], contract: dict[str, Any], artifact_root: Path | None = None
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
    reasons.extend(_validate_frozen_universe_gates(snapshot, contract, decision_at=decision_at))

    identity = snapshot.get("identity")
    if not isinstance(identity, dict):
        reasons.append("identity evidence missing")
    else:
        try:
            valid_from = _utc(identity.get("valid_from"), field="identity.valid_from")
            valid_to_raw = identity.get("valid_to")
            valid_to = _utc(valid_to_raw, field="identity.valid_to") if valid_to_raw is not None else None
            if decision_at < valid_from or (valid_to is not None and decision_at >= valid_to):
                raise ValueError("decision_at lies outside stable identity interval")
            _validate_source(
                identity.get("evidence"), decision_at=decision_at, field="identity.evidence",
                kind="nonempty_string", allowed_sources=contract["identity_source_eligibility"],
                artifact_root=artifact_root,
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
                    features.get(field), decision_at=decision_at, field=field,
                    kind=contract["feature_kinds"][field],
                    allowed_sources=contract["source_eligibility"][field], artifact_root=artifact_root,
                    venue_symbol=snapshot.get("venue_symbol"),
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
    contract: dict[str, Any], snapshots: list[dict[str, Any]], artifact_root: str | Path | None = None
) -> dict[str, Any]:
    validate_contract(contract)
    if not isinstance(snapshots, list):
        raise ValueError("snapshots must be a list")
    _walk_forbidden(snapshots)
    root = Path(artifact_root) if artifact_root is not None else None
    key_counts = Counter(
        key for snapshot in snapshots if isinstance(snapshot, dict)
        for key in [_snapshot_identity_key(snapshot)] if key is not None
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
            excluded.append({
                "index": index, "stable_asset_id": snapshot.get("stable_asset_id"),
                "decision_at": snapshot.get("decision_at"),
                "reasons": ["duplicate stable_asset_id/venue/decision_at snapshot is ambiguous and cannot count toward coverage"],
            })
            continue
        ok, reasons = validate_snapshot(snapshot, contract, root)
        if ok:
            accepted.append(snapshot)
            per_asset[snapshot["stable_asset_id"]] += 1
        else:
            excluded.append({
                "index": index, "stable_asset_id": snapshot.get("stable_asset_id"),
                "decision_at": snapshot.get("decision_at"), "reasons": list(reasons),
            })

    thresholds = contract["coverage_thresholds"]
    eligible_assets = sorted(
        asset for asset, count in per_asset.items()
        if count >= thresholds["minimum_decisions_per_asset"]
    )
    eligible_snapshot_count = sum(count for asset, count in per_asset.items() if asset in eligible_assets)
    ready = (
        root is not None and len(eligible_assets) >= thresholds["minimum_assets"]
        and eligible_snapshot_count >= thresholds["minimum_snapshots"]
    )
    status = "READY_FOR_LABEL_OPEN" if ready else "COVERAGE_BLOCKED"
    result = {
        "schema": RESULT_SCHEMA,
        "contract_digest": digest(contract),
        "snapshot_manifest_digest": digest(snapshots),
        "status": status,
        "source_verification": "SOURCE_NATIVE_AND_RETAINED_BYTES_VERIFIED" if root is not None else "UNAVAILABLE",
        "source_policy_git_blob_sha": "f0c9048228dac566def31f5872406d3437d114c7",
        "accepted_snapshot_count": len(accepted),
        "eligible_snapshot_count": eligible_snapshot_count,
        "excluded_snapshot_count": len(excluded),
        "eligible_asset_count": len(eligible_assets),
        "eligible_assets": eligible_assets,
        "per_asset_snapshot_counts": dict(sorted(per_asset.items())),
        "duplicate_snapshot_key_count": len(duplicate_keys),
        "exclusions": excluded,
        "outcome_access": "MAY_OPEN_ONLY_IN_SEPARATE_LABEL_STAGE" if ready else "SEALED",
        "forward_formation_status": "BLOCKED_UNTIL_TRUSTED_RECEIPT",
        "prediction_authority": False,
        "trade_authority": False,
        "broker_connected": False,
    }
    result["result_digest"] = digest(result)
    return result
