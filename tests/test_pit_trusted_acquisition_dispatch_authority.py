from __future__ import annotations

import json
from pathlib import Path

import pytest

import pit_trusted_acquisition_dispatch_authority as authority


def _event() -> dict:
    return {
        "action": "opened",
        "repository": {
            "full_name": "rnnyrgs-web/tradingview-ai-crypto",
            "default_branch": "main",
            "owner": {"login": "rnnyrgs-web"},
        },
        "sender": {"login": "rnnyrgs-web"},
        "issue": {
            "number": 123,
            "state": "open",
            "title": "pit-trusted-acquisition-request: COMMONCRAWL_INDEX",
            "body": json.dumps(
                {
                    "collection": "CC-MAIN-2026-34",
                    "target_url": "https://example.org/project/docs?a=1",
                }
            ),
            "user": {"login": "rnnyrgs-web"},
        },
    }


def test_target_workflow_identity_and_trust_boundary_are_exact():
    assert authority.verify_target_workflow() == authority.TARGET_WORKFLOW_GIT_BLOB_SHA


def test_target_workflow_drift_blocks_dispatch_authority(tmp_path: Path):
    original = authority.TARGET_WORKFLOW_PATH.read_bytes()
    mutated = tmp_path / "target.yml"
    mutated.write_bytes(original + b"\n# unreviewed drift\n")
    with pytest.raises(authority.DispatchAuthorityError, match="identity drifted"):
        authority.verify_target_workflow(mutated)


def test_receipt_is_dispatch_only_and_cannot_be_scientific_evidence():
    receipt = authority.build_dispatch_authority_receipt(_event())
    assert receipt["schema"] == authority.SCHEMA
    assert receipt["dispatch_authority"] == "DISPATCH_PROVIDER_ACQUISITION_ONLY"
    assert receipt["target_workflow_git_blob_sha"] == authority.TARGET_WORKFLOW_GIT_BLOB_SHA
    assert receipt["source_kind"] == "COMMONCRAWL_INDEX"
    assert receipt["dispatch_payload"]["ref"] == "main"
    assert receipt["scientific_evidence_authority"] is False
    assert receipt["historical_membership_authority"] is False
    assert receipt["historical_label_authority"] is False
    assert receipt["matched_control_authority"] is False
    assert receipt["model_or_metric_authority"] is False
    assert receipt["prospective_candidate_authority"] is False
    assert receipt["oos_or_forward_opening_authority"] is False
    assert receipt["broker_authority"] is False
    assert receipt["trade_authority"] is False
    assert "CONSUMER_SPECIFIC_PIT_PROVENANCE_VALIDATION" in receipt["downstream_trust_requirements"]
    assert "OOS_OR_FORWARD_OPENING" in receipt["prohibited_authorities"]
    assert "TRADE_EXECUTION" in receipt["prohibited_authorities"]


def test_bridge_workflow_runs_authority_gate_before_dispatch_bridge():
    workflow = Path(
        ".github/workflows/pit-trusted-remote-acquisition-request-bridge.yml"
    ).read_text(encoding="utf-8")
    authority_call = (
        'python3 pit_trusted_acquisition_dispatch_authority.py '
        '--event "$GITHUB_EVENT_PATH" --output /tmp/pit-dispatch-authority.json'
    )
    dispatch_call = 'python3 pit_trusted_acquisition_issue_bridge.py --event "$GITHUB_EVENT_PATH"'
    assert authority_call in workflow
    assert dispatch_call in workflow
    assert workflow.index(authority_call) < workflow.index(dispatch_call)


def test_authority_receipt_is_bound_to_same_request_digest_as_dispatch_bridge():
    receipt = authority.build_dispatch_authority_receipt(_event())
    issue_number, _, fields = authority.bridge.validate_event(_event())
    assert receipt["request_sha256"] == authority.bridge.request_digest(issue_number, fields)


def test_non_commoncrawl_kind_cannot_gain_dispatch_authority(monkeypatch):
    monkeypatch.setattr(
        authority.bridge,
        "validate_event",
        lambda event: (123, "BINANCE_LISTOBJECTS_V2", {"source_kind": "BINANCE_LISTOBJECTS_V2"}),
    )
    with pytest.raises(authority.DispatchAuthorityError, match="outside dispatch-only authority"):
        authority.build_dispatch_authority_receipt(_event())
