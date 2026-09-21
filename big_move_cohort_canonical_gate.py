"""Authoritative, fail-closed Cohort 001 entrypoint.

`big_move_cohort_preflight.evaluate_coverage` is intentionally useful as a generic
structural/scientific evaluator, including in tests. A generic caller-provided
contract must not, however, become authority to open historical 2x labels.

This wrapper loads and Git-blob-pins the exact Cohort 001 contract itself. It also
recomputes the accepted return/volatility/regime values from retained checksum-bound
Binance spot 1d archives. Remaining source/value and sector-classifier gaps stay
explicit hard blockers, so this module still cannot open outcome labels.

No outcome data are read here. No forecast/trading authority is granted.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from big_move_cohort_preflight import digest, evaluate_coverage
from big_move_derived_output_binding import (
    COMPLETED_DERIVED_FIELDS,
    validate_snapshot_derived_output_bindings,
)

CANONICAL_CONTRACT_PATH = "money_intelligence/2x_cohort_001_preflight_contract.json"
CANONICAL_CONTRACT_ARTIFACT_ID = "2X-COHORT-001-PREFLIGHT-v1"
CANONICAL_CONTRACT_GIT_BLOB_SHA = "07eb6d26d760444b711cb277be424063ab39802a"
AUTHORITATIVE_SCHEMA = "two_x_cohort_authoritative_gate.v1"

# Market-derived return/volatility/regime are now recomputed from retained
# checksum-bound Binance archives in `big_move_derived_output_binding`. Sector remains
# blocked until the mechanical primary-document classifier itself is value-bound.
DERIVED_OUTPUT_BINDING_BLOCKERS = ("sector",)
DERIVED_OUTPUT_BOUND_FIELDS = COMPLETED_DERIVED_FIELDS

# Source proofs currently authenticate retained support artifacts but do not yet
# deterministically bind these normalized/claimed values back to the retained source
# bytes. Until a parser/attestation closes that gap, canonical label opening remains
# blocked even if structural coverage thresholds are met.
SOURCE_VALUE_BINDING_BLOCKERS = (
    "BINANCE_NORMALIZED_VALUE_NOT_PARSED_FROM_RETAINED_ARCHIVE",
    "PRIMARY_DOCUMENT_CLAIM_VALUE_NOT_PARSED_OR_ATTESTED",
)


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

    binding_failures: list[dict[str, Any]] = []
    excluded_indices = {
        item.get("index")
        for item in structural.get("exclusions", [])
        if isinstance(item, dict) and isinstance(item.get("index"), int)
    }
    if artifact_root is not None:
        for index, snapshot in enumerate(snapshots):
            if index in excluded_indices:
                continue
            try:
                validate_snapshot_derived_output_bindings(snapshot, artifact_root)
            except (TypeError, ValueError, OSError) as exc:
                binding_failures.append({
                    "index": index,
                    "stable_asset_id": snapshot.get("stable_asset_id") if isinstance(snapshot, dict) else None,
                    "decision_at": snapshot.get("decision_at") if isinstance(snapshot, dict) else None,
                    "reason": str(exc),
                })
    if binding_failures:
        blockers.append("DERIVED_OUTPUT_ARCHIVE_BINDING_FAILED")

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
        "derived_output_binding_status": "FAILED" if binding_failures else "PASSED_FOR_STRUCTURALLY_ACCEPTED_SNAPSHOTS",
        "derived_output_binding_failures": binding_failures,
        "derived_output_binding_blockers": list(DERIVED_OUTPUT_BINDING_BLOCKERS),
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
