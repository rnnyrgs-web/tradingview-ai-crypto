import copy
import hashlib
import io
import json
import zipfile

import pytest

from agents.autonomous_cloud_runner import safe_branch
from agents.claude_code_auth import SUBSCRIPTION_AUTOMATED
from agents.claude_code_lifecycle_adapter import (
    ARTIFACT_FILE,
    AUTH_MAP,
    ClaudeCodeLifecycleError,
    apply_authenticated_event,
    prepare_authenticated_claim,
    prepare_authenticated_reexecution,
    validate_authenticated_state,
)
from agents.development_orchestrator_v2 import apply_event, empty_v2
from orchestration.specialist_coordination import load_state


MAIN = "a" * 40
NEXT_MAIN = "b" * 40
TASK_ID = "V2-CLAUDE-REEXEC"
BRANCH = safe_branch("testing-security", TASK_ID)
RUN_ID = "654"
RUN_ATTEMPT = "1"


def _digest(payload):
    return hashlib.sha256(
        json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def capability_receipt():
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
    receipt["content_digest"] = _digest(receipt)
    return receipt


def archive_bytes(receipt):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(ARTIFACT_FILE, json.dumps(receipt, sort_keys=True))
    return buffer.getvalue()


def proof_kwargs():
    receipt = capability_receipt()
    archive = archive_bytes(receipt)
    return dict(
        capability_receipt=receipt,
        trusted_workflow_sha=MAIN,
        workflow_run={
            "id": int(RUN_ID),
            "run_attempt": int(RUN_ATTEMPT),
            "status": "completed",
            "conclusion": "success",
            "path": ".github/workflows/claude_code_subscription_probe.yml",
            "head_sha": MAIN,
            "head_branch": "main",
            "event": "workflow_dispatch",
            "repository": {"full_name": "rnnyrgs-web/tradingview-ai-crypto"},
        },
        capability_artifact={
            "name": f"claude-subscription-capability-{RUN_ID}-{RUN_ATTEMPT}",
            "expired": False,
            "digest": "sha256:" + hashlib.sha256(archive).hexdigest(),
            "workflow_run": {
                "id": int(RUN_ID),
                "head_sha": MAIN,
                "head_branch": "main",
            },
        },
        capability_artifact_archive=archive,
    )


def queue():
    state = load_state()
    for task in state["tasks"]:
        if task["status"] == "READY":
            task["status"] = "BLOCKED"
            task["blockers"] = ["synthetic fixture"]
    seed = copy.deepcopy(next(t for t in state["tasks"] if t["owner"] == "testing-security"))
    seed.update(
        id=TASK_ID,
        title="Synthetic Claude authenticated retry/rebase",
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


def claimed_state():
    state, receipt = prepare_authenticated_claim(
        empty_v2(),
        queue(),
        task_id=TASK_ID,
        request_id="request-1",
        branch=BRANCH,
        current_main_sha=MAIN,
        at="2026-09-21T09:30:00Z",
        selection_evidence=selection(),
        oauth_present=True,
        api_key_present=False,
        **proof_kwargs(),
    )
    return state, receipt


def test_raw_attempt_creating_events_are_rejected_by_authenticated_boundary():
    state, receipt = claimed_state()
    raw_rebase = {
        "event_id": "raw-rebase",
        "type": "REBASE",
        "task_id": TASK_ID,
        "at": "2026-09-21T09:31:00Z",
        "attempt_id": "c" * 64,
        "request_id": "request-2",
        "base_main_sha": NEXT_MAIN,
        "budget_reservation_id": "forged-budget",
    }
    with pytest.raises(ClaudeCodeLifecycleError, match="authenticated preparation"):
        apply_authenticated_event(
            state, raw_rebase, queue(), current_main_sha=NEXT_MAIN
        )

    # Even bypassing the wrapper cannot produce a valid authenticated state:
    # reciprocal validation catches a new Claude Code attempt with no auth receipt.
    bypassed = apply_event(state, raw_rebase, queue(), current_main_sha=NEXT_MAIN)
    assert receipt["attempt_id"] in bypassed[AUTH_MAP]
    with pytest.raises(ClaudeCodeLifecycleError, match="reciprocal executable auth receipt"):
        validate_authenticated_state(bypassed)


def test_authenticated_rebase_creates_fresh_receipt_and_subscription_budget_binding():
    state, first = claimed_state()
    rebased, second = prepare_authenticated_reexecution(
        state,
        queue(),
        kind="REBASE",
        task_id=TASK_ID,
        request_id="request-2",
        current_main_sha=NEXT_MAIN,
        at="2026-09-21T09:31:00Z",
        oauth_present=True,
        api_key_present=True,
        allow_api_fallback=True,
        api_budget_reservation_id="must-not-be-used",
        **proof_kwargs(),
    )
    assert second["attempt_id"] != first["attempt_id"]
    assert second["auth_mode"] == "SUBSCRIPTION"
    assert second["budget_gate_required"] is False
    assert first["attempt_id"] in rebased[AUTH_MAP]
    assert second["attempt_id"] in rebased[AUTH_MAP]
    attempt = rebased["tasks"][TASK_ID]["attempts"][second["attempt_id"]]
    assert attempt["base_main_sha"] == NEXT_MAIN
    assert attempt["budget_reservation_id"].startswith("subscription-no-spend:")
    assert "must-not-be-used" not in json.dumps(rebased)
    validate_authenticated_state(rebased)


def test_authenticated_retry_requires_fresh_auth_receipt_after_provider_wait():
    state, first = claimed_state()
    dispatched = apply_authenticated_event(
        state,
        {
            "event_id": "dispatch-1",
            "type": "DISPATCH",
            "task_id": TASK_ID,
            "at": "2026-09-21T09:31:00Z",
            "attempt_id": first["attempt_id"],
            "dispatch_id": "dispatch-1",
        },
        queue(),
        current_main_sha=MAIN,
    )
    waiting = apply_authenticated_event(
        dispatched,
        {
            "event_id": "timeout-1",
            "type": "PROVIDER_TIMEOUT",
            "task_id": TASK_ID,
            "at": "2026-09-21T09:32:00Z",
            "attempt_id": first["attempt_id"],
            "retry_at": "2026-09-21T09:33:00Z",
        },
        queue(),
        current_main_sha=MAIN,
    )
    retried, second = prepare_authenticated_reexecution(
        waiting,
        queue(),
        kind="RETRY",
        task_id=TASK_ID,
        request_id="request-2",
        current_main_sha=MAIN,
        at="2026-09-21T09:33:00Z",
        oauth_present=True,
        api_key_present=False,
        **proof_kwargs(),
    )
    assert second["attempt_id"] != first["attempt_id"]
    assert retried["tasks"][TASK_ID]["active_attempt"] == second["attempt_id"]
    assert retried["tasks"][TASK_ID]["status"] == "CLAIMED"
    assert retried["tasks"][TASK_ID]["attempts"][second["attempt_id"]][
        "budget_reservation_id"
    ].startswith("subscription-no-spend:")
    validate_authenticated_state(retried)


def test_missing_auth_receipt_for_existing_claude_attempt_is_invalid():
    state, receipt = claimed_state()
    tampered = copy.deepcopy(state)
    del tampered[AUTH_MAP][receipt["attempt_id"]]
    with pytest.raises(ClaudeCodeLifecycleError, match="reciprocal executable auth receipt"):
        validate_authenticated_state(tampered)
