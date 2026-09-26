import copy
import hashlib
import io
import json
import zipfile

import pytest

from agents.autonomous_cloud_runner import safe_branch
from agents.claude_code_auth import SUBSCRIPTION_AUTOMATED
from agents.claude_code_lifecycle_adapter import (
    AUTH_MAP,
    ARTIFACT_FILE,
    ClaudeCodeLifecycleError,
    apply_authenticated_event,
    auth_state_digest,
    prepare_authenticated_claim,
    validate_authenticated_state,
    verify_github_capability_provenance,
)
from agents.development_orchestrator_v2 import empty_v2
from orchestration.specialist_coordination import load_state


MAIN = "a" * 40
TASK_ID = "V2-CLAUDE-AUTH"
BRANCH = safe_branch("testing-security", TASK_ID)
AT = "2026-09-21T09:30:00Z"
RUN_ID = "321"
RUN_ATTEMPT = "1"


def _digest(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def capability_receipt(**overrides):
    receipt = {
        "version": 3,
        "provider": "anthropic",
        "engine": "claude-code",
        "auth_mode": SUBSCRIPTION_AUTOMATED,
        "reason": "OFFICIAL_OAUTH_ACTION_STRUCTURED_PROBE_SUCCEEDED",
        "repository": "rnnyrgs-web/tradingview-ai-crypto",
        "run_id": RUN_ID,
        "run_attempt": RUN_ATTEMPT,
        "event_name": "workflow_dispatch",
        "head_sha": MAIN,
        "execution_sha": MAIN,
        "workflow_ref": (
            "rnnyrgs-web/tradingview-ai-crypto/"
            ".github/workflows/claude_code_subscription_probe.yml@refs/heads/main"
        ),
        "probe_step_outcome": "success",
        "probe_conclusion": "success",
        "structured_probe_verified": True,
        "proof_ref": (
            "github-actions://rnnyrgs-web/tradingview-ai-crypto/"
            f"runs/{RUN_ID}/attempts/{RUN_ATTEMPT}"
        ),
    }
    receipt.update(overrides)
    receipt["content_digest"] = _digest(receipt)
    return receipt


def archive_bytes(receipt):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(ARTIFACT_FILE, json.dumps(receipt, sort_keys=True))
    return buffer.getvalue()


def workflow_run(**overrides):
    run = {
        "id": int(RUN_ID),
        "run_attempt": int(RUN_ATTEMPT),
        "status": "completed",
        "conclusion": "success",
        "path": ".github/workflows/claude_code_subscription_probe.yml",
        "head_sha": MAIN,
        "head_branch": "main",
        "event": "workflow_dispatch",
        "repository": {"full_name": "rnnyrgs-web/tradingview-ai-crypto"},
    }
    run.update(overrides)
    return run


def artifact(archive, **overrides):
    item = {
        "name": f"claude-subscription-capability-{RUN_ID}-{RUN_ATTEMPT}",
        "expired": False,
        "digest": "sha256:" + hashlib.sha256(archive).hexdigest(),
        "workflow_run": {"id": int(RUN_ID), "head_sha": MAIN, "head_branch": "main"},
    }
    item.update(overrides)
    return item


def proof_bundle():
    receipt = capability_receipt()
    archive = archive_bytes(receipt)
    return receipt, archive, artifact(archive)


def queue():
    state = load_state()
    for task in state["tasks"]:
        if task["status"] == "READY":
            task["status"] = "BLOCKED"
            task["blockers"] = ["synthetic fixture"]
    seed = copy.deepcopy(next(t for t in state["tasks"] if t["owner"] == "testing-security"))
    seed.update(
        id=TASK_ID,
        title="Synthetic Claude subscription lifecycle",
        owner="testing-security",
        status="READY",
        priority=0,
        blockers=[],
        dependencies=[],
        fingerprint_id=None,
        pr=None,
        eligible_engines=["claude-code"],
        engine_claim=None,
        next_task=None,
        work_mode="AUDIT",
        branch=state["roles"]["testing-security"]["branch"],
    )
    state["tasks"].append(seed)
    return state


def selection():
    return {
        "claimed_branches": set(),
        "active_prs": set(),
        "rejected": [],
        "strategy_queue": {"active_deep_candidate": None},
    }


def subscription_claim_kwargs():
    receipt, archive, item = proof_bundle()
    return dict(
        capability_receipt=receipt,
        trusted_workflow_sha=MAIN,
        workflow_run=workflow_run(),
        capability_artifact=item,
        capability_artifact_archive=archive,
    )


def test_subscription_claim_requires_independent_github_run_artifact_and_bytes():
    receipt, _, _ = proof_bundle()
    with pytest.raises(ClaudeCodeLifecycleError, match="trusted GitHub"):
        prepare_authenticated_claim(
            empty_v2(), queue(), task_id=TASK_ID, request_id="request-1", branch=BRANCH,
            current_main_sha=MAIN, at=AT, selection_evidence=selection(), oauth_present=True,
            api_key_present=False, capability_receipt=receipt, trusted_workflow_sha=MAIN,
        )


def test_workflow_artifact_metadata_and_exact_bytes_are_all_required():
    receipt, archive, item = proof_bundle()
    proof = verify_github_capability_provenance(
        receipt, workflow_run=workflow_run(), artifact=item,
        artifact_archive=archive, trusted_workflow_sha=MAIN,
    )
    assert proof.endswith(f"runs/{RUN_ID}/attempts/{RUN_ATTEMPT}")

    with pytest.raises(ClaudeCodeLifecycleError, match="workflow-run provenance"):
        verify_github_capability_provenance(
            receipt, workflow_run=workflow_run(head_sha="b" * 40), artifact=item,
            artifact_archive=archive, trusted_workflow_sha=MAIN,
        )
    with pytest.raises(ClaudeCodeLifecycleError, match="artifact provenance"):
        verify_github_capability_provenance(
            receipt, workflow_run=workflow_run(), artifact=artifact(archive, expired=True),
            artifact_archive=archive, trusted_workflow_sha=MAIN,
        )
    forged = capability_receipt(execution_sha="b" * 40)
    with pytest.raises(ClaudeCodeLifecycleError, match="does not match GitHub artifact bytes"):
        verify_github_capability_provenance(
            forged, workflow_run=workflow_run(), artifact=item,
            artifact_archive=archive, trusted_workflow_sha=MAIN,
        )
    with pytest.raises(ClaudeCodeLifecycleError, match="byte digest mismatch"):
        verify_github_capability_provenance(
            receipt, workflow_run=workflow_run(), artifact=item,
            artifact_archive=archive + b"tamper", trusted_workflow_sha=MAIN,
        )


def test_pull_request_or_non_main_probe_cannot_self_attest_subscription_authority():
    receipt = capability_receipt(
        event_name="pull_request",
        workflow_ref=(
            "rnnyrgs-web/tradingview-ai-crypto/"
            ".github/workflows/claude_code_subscription_probe.yml@refs/heads/feature/probe"
        ),
    )
    archive = archive_bytes(receipt)
    item = artifact(
        archive,
        workflow_run={
            "id": int(RUN_ID),
            "head_sha": MAIN,
            "head_branch": "feature/probe",
        },
    )
    with pytest.raises(ClaudeCodeLifecycleError, match="trusted-main workflow_dispatch"):
        verify_github_capability_provenance(
            receipt,
            workflow_run=workflow_run(event="pull_request", head_branch="feature/probe"),
            artifact=item,
            artifact_archive=archive,
            trusted_workflow_sha=MAIN,
        )


def test_execution_sha_must_equal_trusted_main_probe_sha():
    receipt = capability_receipt(execution_sha="b" * 40)
    archive = archive_bytes(receipt)
    with pytest.raises(ClaudeCodeLifecycleError, match="execution SHA is not bound to trusted workflow SHA"):
        verify_github_capability_provenance(
            receipt,
            workflow_run=workflow_run(),
            artifact=artifact(archive),
            artifact_archive=archive,
            trusted_workflow_sha=MAIN,
        )


def test_verified_subscription_claim_is_durable_non_metered_and_survives_lifecycle():
    state, receipt = prepare_authenticated_claim(
        empty_v2(), queue(), task_id=TASK_ID, request_id="request-1", branch=BRANCH,
        current_main_sha=MAIN, at=AT, selection_evidence=selection(), oauth_present=True,
        api_key_present=True, allow_api_fallback=True,
        api_budget_reservation_id="must-not-be-consumed", **subscription_claim_kwargs(),
    )
    assert receipt["auth_mode"] == "SUBSCRIPTION"
    assert receipt["budget_gate_required"] is False
    attempt = state["tasks"][TASK_ID]["attempts"][receipt["attempt_id"]]
    assert attempt["budget_reservation_id"].startswith("subscription-no-spend:")
    assert "must-not-be-consumed" not in json.dumps(state)
    assert receipt["attempt_id"] in state[AUTH_MAP]

    dispatch = {
        "event_id": "dispatch-1",
        "type": "DISPATCH",
        "task_id": TASK_ID,
        "at": "2026-09-21T09:31:00Z",
        "attempt_id": receipt["attempt_id"],
        "dispatch_id": "dispatch-1",
    }
    progressed = apply_authenticated_event(state, dispatch, queue(), current_main_sha=MAIN)
    assert progressed["tasks"][TASK_ID]["status"] == "DISPATCHED"
    assert auth_state_digest(progressed) == auth_state_digest(state)


def test_missing_subscription_proof_is_durable_manual_and_does_not_occupy_worker():
    state, receipt = prepare_authenticated_claim(
        empty_v2(), queue(), task_id=TASK_ID, request_id="request-manual", branch=BRANCH,
        current_main_sha=MAIN, at=AT, selection_evidence=selection(), oauth_present=False,
        api_key_present=False,
    )
    assert receipt["auth_mode"] == "MANUAL_ADAPTER_REQUIRED"
    assert receipt["execute"] is False
    assert TASK_ID not in state["tasks"]
    assert receipt["attempt_id"] in state[AUTH_MAP]
    validate_authenticated_state(state)


def test_oauth_without_provenance_never_silently_uses_paid_api():
    state, receipt = prepare_authenticated_claim(
        empty_v2(), queue(), task_id=TASK_ID, request_id="request-oauth", branch=BRANCH,
        current_main_sha=MAIN, at=AT, selection_evidence=selection(), oauth_present=True,
        api_key_present=True, allow_api_fallback=True, api_budget_reservation_id="approved-budget",
    )
    assert receipt["auth_mode"] == "MANUAL_ADAPTER_REQUIRED"
    assert receipt["execute"] is False
    assert "approved-budget" not in json.dumps(state)
    assert TASK_ID not in state["tasks"]


def test_api_fallback_requires_explicit_approval_and_budget_identity():
    with pytest.raises(ClaudeCodeLifecycleError, match="budget reservation"):
        prepare_authenticated_claim(
            empty_v2(), queue(), task_id=TASK_ID, request_id="request-api", branch=BRANCH,
            current_main_sha=MAIN, at=AT, selection_evidence=selection(), oauth_present=False,
            api_key_present=True, allow_api_fallback=True,
        )

    state, receipt = prepare_authenticated_claim(
        empty_v2(), queue(), task_id=TASK_ID, request_id="request-api", branch=BRANCH,
        current_main_sha=MAIN, at=AT, selection_evidence=selection(), oauth_present=False,
        api_key_present=True, allow_api_fallback=True,
        api_budget_reservation_id="approved-api-budget-1",
    )
    assert receipt["auth_mode"] == "API_METERED"
    attempt = state["tasks"][TASK_ID]["attempts"][receipt["attempt_id"]]
    assert attempt["budget_reservation_id"] == "approved-api-budget-1"


def test_tampering_auth_mode_or_budget_binding_is_detected():
    state, receipt = prepare_authenticated_claim(
        empty_v2(), queue(), task_id=TASK_ID, request_id="request-1", branch=BRANCH,
        current_main_sha=MAIN, at=AT, selection_evidence=selection(), oauth_present=True,
        api_key_present=False, **subscription_claim_kwargs(),
    )
    tampered = copy.deepcopy(state)
    tampered["tasks"][TASK_ID]["attempts"][receipt["attempt_id"]][
        "budget_reservation_id"
    ] = "approved-api-budget-evil"
    attempt = tampered["tasks"][TASK_ID]["attempts"][receipt["attempt_id"]]
    unsigned = {k: v for k, v in attempt.items() if k not in {"content_digest", "dispatch_id"}}
    attempt["content_digest"] = _digest(unsigned)
    with pytest.raises(ClaudeCodeLifecycleError, match="gained metered budget"):
        validate_authenticated_state(tampered)


def test_conflicting_receipt_tamper_is_detected():
    state, receipt = prepare_authenticated_claim(
        empty_v2(), queue(), task_id=TASK_ID, request_id="request-manual", branch=BRANCH,
        current_main_sha=MAIN, at=AT, selection_evidence=selection(), oauth_present=False,
        api_key_present=False,
    )
    bad = copy.deepcopy(state)
    bad[AUTH_MAP][receipt["attempt_id"]]["reason"] = "tampered"
    with pytest.raises(ClaudeCodeLifecycleError):
        validate_authenticated_state(bad)
