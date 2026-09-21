"""Authoritative, fail-closed Cohort 001 entrypoint.

`big_move_cohort_preflight.evaluate_coverage` is intentionally useful as a generic
structural/scientific evaluator, including in tests. A generic caller-provided
contract must not, however, become authority to open historical 2x labels.

This wrapper loads and Git-blob-pins the exact Cohort 001 contract itself. It
recomputes accepted return/volatility/regime values from retained checksum-bound
Binance spot 1d archives, independently binds each direct Binance decision price to
the exact retained archive close, mechanically binds any primary-document claim to
literal retained text, and recomputes the frozen coarse functional sector from the
whole PIT primary document.

Primary-document chronology is also fail-closed: caller-authored `published_at` or
`effective_at` metadata is not accepted as anti-backdating proof. Every primary
document that contributes to an accepted snapshot must additionally bind the exact
document bytes to a Common Crawl WARC response whose independent capture timestamp is
no later than the historical decision timestamp. Missing/ambiguous/unsupported archive
evidence excludes the snapshot rather than being silently normalized.

The wrapper itself never opens outcomes: even after source/value transforms and
historical-availability proofs pass, actual label opening remains a separate handoff
after real frozen coverage passes and exact-head review clears the integration.

No outcome data are read here. No forecast/trading authority is granted.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from big_move_binance_price_binding import validate_binance_decision_price
from big_move_cohort_preflight import digest, evaluate_coverage
from big_move_derived_output_binding import (
    COMPLETED_DERIVED_FIELDS,
    validate_snapshot_derived_output_bindings,
)
from big_move_primary_document_binding import (
    ELIGIBLE_SOURCE_IDS as PRIMARY_SOURCE_IDS,
    load_retained_record,
    validate_primary_document_literal_claim,
)
from big_move_primary_functional_classifier import validate_sector_output_binding
from big_move_primary_historical_availability import (
    validate_primary_document_historical_availability,
)

CANONICAL_CONTRACT_PATH = "money_intelligence/2x_cohort_001_preflight_contract.json"
CANONICAL_CONTRACT_ARTIFACT_ID = "2X-COHORT-001-PREFLIGHT-v1"
CANONICAL_CONTRACT_GIT_BLOB_SHA = "07eb6d26d760444b711cb277be424063ab39802a"
AUTHORITATIVE_SCHEMA = "two_x_cohort_authoritative_gate.v1"

# All previously explicit derived outputs now have deterministic pre-outcome binders:
# return/volatility/regime from retained Binance archives, and sector from the frozen
# primary-document functional classifier. Bad/missing evidence becomes a per-snapshot
# binding failure; no generic semantic fallback exists.
DERIVED_OUTPUT_BINDING_BLOCKERS: tuple[str, ...] = ()
DERIVED_OUTPUT_BOUND_FIELDS = tuple(COMPLETED_DERIVED_FIELDS) + ("sector",)

# Direct Binance decision price and literal primary-document values are reproducible
# from retained bytes. Primary-document historical availability is additionally bound
# to an independent pre-decision Common Crawl WARC capture. There is therefore no
# remaining unconditional source-value blocker in this authoritative wrapper; bad or
# missing archive evidence is recorded per snapshot and keeps coverage blocked.
SOURCE_VALUE_BOUND_FIELDS = (
    "price",
    "primary_document_literal_claims",
    "primary_document_historical_availability",
)
SOURCE_VALUE_BINDING_BLOCKERS: tuple[str, ...] = ()


def _git_blob_sha(raw: bytes) -> str:
    header = f"blob {len(raw)}\0".encode("ascii")
    return hashlib.sha1(header + raw, usedforsecurity=False).hexdigest()


def load_canonical_contract(repo_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parent
    path = (root / CANONICAL_CONTRACT_PATH).resolve()
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError("canonical Cohort 001 contract is unavailable") from exc
    if _git_blob_sha(raw) != CANONICAL_CONTRACT_GIT_BLOB_SHA:
        raise ValueError("canonical Cohort 001 contract drifted from frozen Git blob")
    try:
        contract = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("canonical Cohort 001 contract is malformed") from exc
    if not isinstance(contract, dict) or contract.get("artifact_id") != CANONICAL_CONTRACT_ARTIFACT_ID:
        raise ValueError("unexpected canonical Cohort 001 contract identity")
    thresholds = contract.get("coverage_thresholds")
    if thresholds != {
        "minimum_assets": 12,
        "minimum_snapshots": 624,
        "minimum_decisions_per_asset": 52,
    }:
        raise ValueError("canonical Cohort 001 coverage thresholds drifted")
    return contract


def _validate_primary_record_if_used(
    record: Any,
    *,
    decision_at: str,
    artifact_root: str | Path,
    repo_root: str | Path | None,
    field: str,
) -> None:
    if not isinstance(record, dict):
        return
    if record.get("source_id") not in PRIMARY_SOURCE_IDS:
        return
    try:
        validate_primary_document_literal_claim(
            record,
            decision_at=decision_at,
            artifact_root=artifact_root,
            repo_root=repo_root,
        )
        validate_primary_document_historical_availability(
            record,
            decision_at=decision_at,
            artifact_root=artifact_root,
            repo_root=repo_root,
        )
    except (TypeError, ValueError, OSError) as exc:
        raise ValueError(f"{field}: {exc}") from exc


def _validate_snapshot_primary_claims(
    snapshot: dict[str, Any],
    *,
    artifact_root: str | Path,
    repo_root: str | Path | None,
) -> None:
    decision_at = snapshot.get("decision_at")
    if not isinstance(decision_at, str):
        raise ValueError("snapshot decision_at missing")

    identity = snapshot.get("identity")
    if isinstance(identity, dict):
        _validate_primary_record_if_used(
            identity.get("evidence"),
            decision_at=decision_at,
            artifact_root=artifact_root,
            repo_root=repo_root,
            field="identity.evidence",
        )

    features = snapshot.get("features")
    if not isinstance(features, dict):
        raise ValueError("snapshot features missing")
    for feature_name, record in features.items():
        _validate_primary_record_if_used(
            record,
            decision_at=decision_at,
            artifact_root=artifact_root,
            repo_root=repo_root,
            field=f"features.{feature_name}",
        )
        if not isinstance(record, dict):
            continue
        derivation = record.get("derivation")
        if not isinstance(derivation, dict):
            continue
        inputs = derivation.get("inputs")
        if not isinstance(inputs, list):
            continue
        for input_index, ref in enumerate(inputs):
            if not isinstance(ref, dict):
                continue
            retained = load_retained_record(
                ref,
                artifact_root=artifact_root,
                field=f"features.{feature_name}.derivation.inputs[{input_index}]",
            )
            _validate_primary_record_if_used(
                retained,
                decision_at=decision_at,
                artifact_root=artifact_root,
                repo_root=repo_root,
                field=f"features.{feature_name}.derivation.inputs[{input_index}]",
            )


def evaluate_authoritative_coverage(
    snapshots: list[dict[str, Any]],
    artifact_root: str | Path | None = None,
    *,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Evaluate only the exact frozen contract and fail closed on open science gaps."""
    contract = load_canonical_contract(repo_root)
    structural = evaluate_coverage(contract, snapshots, artifact_root)

    blockers: list[str] = []
    if structural.get("status") != "READY_FOR_LABEL_OPEN":
        blockers.append("PIT_COVERAGE_NOT_READY")

    excluded_indices = {
        item.get("index")
        for item in structural.get("exclusions", [])
        if isinstance(item, dict) and isinstance(item.get("index"), int)
    }

    derived_binding_failures: list[dict[str, Any]] = []
    source_value_binding_failures: list[dict[str, Any]] = []
    if artifact_root is not None:
        for index, snapshot in enumerate(snapshots):
            if index in excluded_indices:
                continue
            stable_asset_id = snapshot.get("stable_asset_id") if isinstance(snapshot, dict) else None
            decision_at = snapshot.get("decision_at") if isinstance(snapshot, dict) else None
            try:
                validate_snapshot_derived_output_bindings(snapshot, artifact_root)
                features = snapshot.get("features") if isinstance(snapshot, dict) else None
                if not isinstance(features, dict):
                    raise ValueError("snapshot features missing")
                validate_sector_output_binding(
                    features.get("sector"),
                    decision_at=decision_at,
                    artifact_root=artifact_root,
                    repo_root=repo_root,
                )
            except (TypeError, ValueError, OSError) as exc:
                derived_binding_failures.append({
                    "index": index,
                    "stable_asset_id": stable_asset_id,
                    "decision_at": decision_at,
                    "reason": str(exc),
                })
            try:
                features = snapshot.get("features") if isinstance(snapshot, dict) else None
                if not isinstance(features, dict):
                    raise ValueError("snapshot features missing")
                validate_binance_decision_price(
                    features.get("price"),
                    venue_symbol=snapshot.get("venue_symbol"),
                    decision_at=decision_at,
                    artifact_root=artifact_root,
                    repo_root=repo_root,
                )
                _validate_snapshot_primary_claims(
                    snapshot,
                    artifact_root=artifact_root,
                    repo_root=repo_root,
                )
            except (TypeError, ValueError, OSError) as exc:
                source_value_binding_failures.append({
                    "index": index,
                    "stable_asset_id": stable_asset_id,
                    "decision_at": decision_at,
                    "reason": str(exc),
                })

    if derived_binding_failures:
        blockers.append("DERIVED_OUTPUT_ARCHIVE_BINDING_FAILED")
    if source_value_binding_failures:
        blockers.append("DIRECT_SOURCE_VALUE_BINDING_FAILED")

    blockers.extend(
        f"DERIVED_OUTPUT_NOT_DETERMINISTICALLY_BOUND:{field}"
        for field in DERIVED_OUTPUT_BINDING_BLOCKERS
    )
    blockers.extend(SOURCE_VALUE_BINDING_BLOCKERS)

    result: dict[str, Any] = {
        "schema": AUTHORITATIVE_SCHEMA,
        "canonical_contract_artifact_id": CANONICAL_CONTRACT_ARTIFACT_ID,
        "canonical_contract_git_blob_sha": CANONICAL_CONTRACT_GIT_BLOB_SHA,
        "canonical_contract_digest": digest(contract),
        "structural_coverage_result_digest": structural.get("result_digest"),
        "structural_coverage_status": structural.get("status"),
        "status": "COVERAGE_BLOCKED",
        "blockers": blockers,
        "derived_output_bound_fields": list(DERIVED_OUTPUT_BOUND_FIELDS),
        "derived_output_binding_status": "FAILED" if derived_binding_failures else "PASSED_FOR_STRUCTURALLY_ACCEPTED_SNAPSHOTS",
        "derived_output_binding_failures": derived_binding_failures,
        "derived_output_binding_blockers": list(DERIVED_OUTPUT_BINDING_BLOCKERS),
        "source_value_bound_fields": list(SOURCE_VALUE_BOUND_FIELDS),
        "source_value_binding_status": "FAILED" if source_value_binding_failures else "PASSED_FOR_STRUCTURALLY_ACCEPTED_SNAPSHOTS",
        "source_value_binding_failures": source_value_binding_failures,
        "source_value_binding_blockers": list(SOURCE_VALUE_BINDING_BLOCKERS),
        "outcome_access": "SEALED",
        "labels_opened": False,
        "prediction_authority": False,
        "trade_authority": False,
        "broker_connected": False,
        "live_trading": False,
    }
    result["result_digest"] = digest(result)
    return result
