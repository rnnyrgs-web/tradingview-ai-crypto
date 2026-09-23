from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

import pit_trusted_acquisition_issue_bridge as bridge

SCHEMA = "PIT_TRUSTED_ACQUISITION_DISPATCH_AUTHORITY_V1"
TARGET_WORKFLOW_PATH = Path(".github/workflows/pit-trusted-remote-acquisition.yml")
TARGET_WORKFLOW_GIT_BLOB_SHA = "439c16fd901eef705c905863e3c00512f0c82471"
ALLOWED_SOURCE_KINDS = frozenset({"COMMONCRAWL_INDEX", "COMMONCRAWL_WARC_RANGE"})
DISPATCH_AUTHORITY = "DISPATCH_PROVIDER_ACQUISITION_ONLY"
DOWNSTREAM_TRUST_REQUIREMENTS = (
    "CANONICAL_MAIN_WORKFLOW_DISPATCH",
    "EXACT_PROVIDER_RESPONSE_BYTES",
    "CANONICAL_ACQUISITION_RECEIPT",
    "GITHUB_ARTIFACT_ATTESTATION",
    "CONSUMER_SPECIFIC_PIT_PROVENANCE_VALIDATION",
)
PROHIBITED_AUTHORITIES = (
    "HISTORICAL_UNIVERSE_MEMBERSHIP",
    "HISTORICAL_LABEL",
    "MATCHED_CONTROL_STATUS",
    "PRECURSOR_OR_GRAPH_SUPPORT",
    "MODEL_FIT_OR_METRIC",
    "OOS_OR_FORWARD_OPENING",
    "PROSPECTIVE_CANDIDATE",
    "RANKING_OR_PROMOTION",
    "BROKER_CONNECTION",
    "TRADE_EXECUTION",
)


class DispatchAuthorityError(ValueError):
    pass


def _git_blob_sha(data: bytes) -> str:
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data, usedforsecurity=False).hexdigest()


def verify_target_workflow(path: Path = TARGET_WORKFLOW_PATH) -> str:
    try:
        data = path.read_bytes()
    except OSError as exc:
        raise DispatchAuthorityError("target acquisition workflow is unavailable") from exc
    actual = _git_blob_sha(data)
    if actual != TARGET_WORKFLOW_GIT_BLOB_SHA:
        raise DispatchAuthorityError(
            "target acquisition workflow identity drifted; bridge dispatch is blocked until a materially new reviewed authority contract binds the new workflow"
        )
    text = data.decode("utf-8")
    required = (
        "name: PIT Trusted Remote Acquisition",
        "  workflow_dispatch:",
        "permissions:\n  contents: read\n  id-token: write\n  attestations: write",
        'test "$GITHUB_EVENT_NAME" = "workflow_dispatch"',
        'test "$GITHUB_REF" = "refs/heads/main"',
        "Attest exact acquisition bundle",
        "subject-path: trusted-acquisition-output/trusted-acquisition.tar",
    )
    missing = [fragment for fragment in required if fragment not in text]
    if missing:
        raise DispatchAuthorityError("target acquisition workflow lost a frozen trust-boundary invariant")
    return actual


def build_dispatch_authority_receipt(
    event: dict[str, Any], *, target_workflow_path: Path = TARGET_WORKFLOW_PATH
) -> dict[str, Any]:
    target_blob = verify_target_workflow(target_workflow_path)
    issue_number, source_kind, fields = bridge.validate_event(event)
    if source_kind not in ALLOWED_SOURCE_KINDS:
        raise DispatchAuthorityError("source kind is outside dispatch-only authority")
    payload = bridge.build_dispatch_payload(fields)
    digest = bridge.request_digest(issue_number, fields)
    return {
        "schema": SCHEMA,
        "issue_number": issue_number,
        "request_sha256": digest,
        "source_kind": source_kind,
        "dispatch_authority": DISPATCH_AUTHORITY,
        "target_workflow": bridge.TARGET_WORKFLOW,
        "target_ref": bridge.TARGET_REF,
        "target_workflow_git_blob_sha": target_blob,
        "dispatch_payload": payload,
        "downstream_trust_requirements": list(DOWNSTREAM_TRUST_REQUIREMENTS),
        "prohibited_authorities": list(PROHIBITED_AUTHORITIES),
        "scientific_evidence_authority": False,
        "historical_membership_authority": False,
        "historical_label_authority": False,
        "matched_control_authority": False,
        "model_or_metric_authority": False,
        "prospective_candidate_authority": False,
        "oos_or_forward_opening_authority": False,
        "broker_authority": False,
        "trade_authority": False,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    try:
        event = json.loads(args.event.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise DispatchAuthorityError("event must be readable strict JSON") from exc
    if not isinstance(event, dict):
        raise DispatchAuthorityError("event must be a JSON object")
    receipt = build_dispatch_authority_receipt(event)
    args.output.write_text(
        json.dumps(receipt, sort_keys=True, separators=(",", ":")) + "\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    main()
