"""Bind Claude Code authentication evidence to Orchestrator V2 lifecycle state.

The existing V2 reducer already owns task/attempt identity, completion, exact-head
CI, independent review, bounded repair, integration, replay and successor rules.
This module adds the missing provider/auth boundary without reimplementing them.

Subscription authorization requires four reconciled facts:
1. the secret-free capability receipt emitted by the pinned probe workflow;
2. authenticated GitHub workflow-run metadata;
3. authenticated GitHub artifact metadata;
4. the exact downloaded artifact ZIP bytes whose SHA-256 equals GitHub metadata.

A caller therefore cannot upgrade itself to subscription execution by fabricating
a self-consistent JSON receipt while merely citing a real workflow run.
"""

from __future__ import annotations

import copy
import hashlib
import io
import json
import zipfile
from typing import Any, Mapping

from agents.claude_code_auth import (
    API_METERED,
    CAPABILITY_WORKFLOW,
    MANUAL_ADAPTER_REQUIRED,
    REPO,
    SUBSCRIPTION,
    AuthPolicyError,
    make_auth_receipt,
    resolve_auth,
    validate_auth_receipt,
    validate_capability_receipt,
)
from agents.development_orchestrator_v2 import apply_event, validate_v2

AUTH_MAP = "claude_code_auth_receipts"
ARTIFACT_PREFIX = "claude-subscription-capability"
ARTIFACT_FILE = "claude-subscription-capability.json"
MAX_ARTIFACT_BYTES = 64 * 1024
TRUSTED_CAPABILITY_EVENT = "workflow_dispatch"
TRUSTED_CAPABILITY_BRANCH = "main"
TRUSTED_CAPABILITY_WORKFLOW_REF = (
    f"{REPO}/{CAPABILITY_WORKFLOW}@refs/heads/{TRUSTED_CAPABILITY_BRANCH}"
)
_ATTEMPT_CREATING_EVENTS = {"CLAIM", "RETRY", "REBASE"}


class ClaudeCodeLifecycleError(RuntimeError):
    pass


def _digest(value: Mapping[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(dict(value), sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()


def _receipt_from_archive(artifact_archive: bytes, artifact: Mapping[str, Any]) -> dict[str, Any]:
    if not isinstance(artifact_archive, bytes) or not artifact_archive:
        raise ClaudeCodeLifecycleError("capability artifact bytes are required")
    if len(artifact_archive) > MAX_ARTIFACT_BYTES:
        raise ClaudeCodeLifecycleError("capability artifact exceeds bounded size")
    expected_digest = artifact.get("digest")
    actual_digest = "sha256:" + hashlib.sha256(artifact_archive).hexdigest()
    if expected_digest != actual_digest:
        raise ClaudeCodeLifecycleError("capability artifact byte digest mismatch")
    try:
        with zipfile.ZipFile(io.BytesIO(artifact_archive)) as archive:
            names = archive.namelist()
            if names != [ARTIFACT_FILE]:
                raise ClaudeCodeLifecycleError("capability artifact file set mismatch")
            info = archive.getinfo(ARTIFACT_FILE)
            if info.file_size > 32 * 1024 or info.is_dir():
                raise ClaudeCodeLifecycleError("capability receipt file is malformed")
            raw = archive.read(ARTIFACT_FILE)
    except (zipfile.BadZipFile, KeyError) as exc:
        raise ClaudeCodeLifecycleError("capability artifact is not the expected ZIP") from exc
    try:
        parsed = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ClaudeCodeLifecycleError("capability receipt JSON is malformed") from exc
    if not isinstance(parsed, dict):
        raise ClaudeCodeLifecycleError("capability receipt JSON must be an object")
    return parsed


def verify_github_capability_provenance(
    capability_receipt: Mapping[str, Any],
    *,
    workflow_run: Mapping[str, Any],
    artifact: Mapping[str, Any],
    artifact_archive: bytes,
    trusted_workflow_sha: str,
) -> str:
    """Reconcile receipt bytes against authenticated GitHub run/artifact facts.

    Subscription execution authority is accepted only from a workflow-dispatch
    run on the repository's main branch. Pull-request runs remain useful for
    CI/fail-closed diagnostics, but a branch that can modify the probe workflow
    may never self-attest subscription capability.
    """
    archived_receipt = _receipt_from_archive(artifact_archive, artifact)
    if archived_receipt != dict(capability_receipt):
        raise ClaudeCodeLifecycleError("capability receipt does not match GitHub artifact bytes")
    try:
        proof_ref = validate_capability_receipt(
            archived_receipt, trusted_workflow_sha=trusted_workflow_sha
        )
    except AuthPolicyError as exc:
        raise ClaudeCodeLifecycleError(str(exc)) from exc

    if (
        archived_receipt.get("event_name") != TRUSTED_CAPABILITY_EVENT
        or archived_receipt.get("workflow_ref") != TRUSTED_CAPABILITY_WORKFLOW_REF
        or archived_receipt.get("execution_sha") != trusted_workflow_sha
    ):
        raise ClaudeCodeLifecycleError(
            "capability proof must originate from workflow_dispatch on trusted main"
        )

    run_id = str(archived_receipt["run_id"])
    run_attempt = str(archived_receipt["run_attempt"])
    repository = workflow_run.get("repository") or {}
    if (
        str(workflow_run.get("id")) != run_id
        or str(workflow_run.get("run_attempt")) != run_attempt
        or workflow_run.get("status") != "completed"
        or workflow_run.get("conclusion") != "success"
        or workflow_run.get("path") != CAPABILITY_WORKFLOW
        or workflow_run.get("head_sha") != trusted_workflow_sha
        or workflow_run.get("head_branch") != TRUSTED_CAPABILITY_BRANCH
        or workflow_run.get("event") != TRUSTED_CAPABILITY_EVENT
        or repository.get("full_name") != REPO
    ):
        raise ClaudeCodeLifecycleError("capability workflow-run provenance mismatch")

    artifact_run = artifact.get("workflow_run") or {}
    expected_name = f"{ARTIFACT_PREFIX}-{run_id}-{run_attempt}"
    if (
        artifact.get("name") != expected_name
        or artifact.get("expired") is not False
        or str(artifact_run.get("id")) != run_id
        or artifact_run.get("head_sha") != trusted_workflow_sha
        or artifact_run.get("head_branch") != TRUSTED_CAPABILITY_BRANCH
    ):
        raise ClaudeCodeLifecycleError("capability artifact provenance mismatch")
    return proof_ref


def _put_receipt(state: dict[str, Any], receipt: Mapping[str, Any]) -> dict[str, Any]:
    try:
        validate_auth_receipt(receipt)
    except AuthPolicyError as exc:
        raise ClaudeCodeLifecycleError(str(exc)) from exc
    updated = copy.deepcopy(state)
    auth_map = updated.setdefault(AUTH_MAP, {})
    if not isinstance(auth_map, dict):
        raise ClaudeCodeLifecycleError("malformed Claude Code auth receipt map")
    attempt_id = receipt["attempt_id"]
    existing = auth_map.get(attempt_id)
    if existing is not None and existing != dict(receipt):
        raise ClaudeCodeLifecycleError("conflicting immutable Claude Code auth receipt")
    auth_map[attempt_id] = copy.deepcopy(dict(receipt))
    return updated


def _resolve_attempt_auth(
    *,
    task_id: str,
    request_id: str,
    branch: str,
    current_main_sha: str,
    at: str,
    oauth_present: bool,
    api_key_present: bool,
    capability_receipt: Mapping[str, Any] | None,
    trusted_workflow_sha: str | None,
    workflow_run: Mapping[str, Any] | None,
    capability_artifact: Mapping[str, Any] | None,
    capability_artifact_archive: bytes | None,
    allow_api_fallback: bool,
    api_budget_reservation_id: str | None,
) -> tuple[Any, dict[str, Any], str | None]:
    if capability_receipt is not None:
        if (
            trusted_workflow_sha is None
            or workflow_run is None
            or capability_artifact is None
            or capability_artifact_archive is None
        ):
            raise ClaudeCodeLifecycleError(
                "subscription capability requires trusted GitHub run, artifact metadata, and bytes"
            )
        verify_github_capability_provenance(
            capability_receipt,
            workflow_run=workflow_run,
            artifact=capability_artifact,
            artifact_archive=capability_artifact_archive,
            trusted_workflow_sha=trusted_workflow_sha,
        )
    elif any(
        value is not None
        for value in (
            trusted_workflow_sha,
            workflow_run,
            capability_artifact,
            capability_artifact_archive,
        )
    ):
        raise ClaudeCodeLifecycleError(
            "partial capability provenance cannot authorize subscription execution"
        )

    try:
        decision = resolve_auth(
            oauth_present=oauth_present,
            api_key_present=api_key_present,
            capability_receipt=capability_receipt,
            trusted_workflow_sha=trusted_workflow_sha,
            allow_api_fallback=allow_api_fallback,
        )
        auth_receipt = make_auth_receipt(
            task_id=task_id,
            request_id=request_id,
            branch=branch,
            base_main_sha=current_main_sha,
            decision=decision,
            observed_at=at,
        )
    except AuthPolicyError as exc:
        raise ClaudeCodeLifecycleError(str(exc)) from exc

    if not decision.execute:
        if decision.auth_mode != MANUAL_ADAPTER_REQUIRED:
            raise ClaudeCodeLifecycleError("non-executable auth must fail closed as manual")
        return decision, auth_receipt, None

    if decision.auth_mode == SUBSCRIPTION:
        budget_reservation_id = f"subscription-no-spend:{auth_receipt['content_digest'][:32]}"
    elif decision.auth_mode == API_METERED:
        if not allow_api_fallback or not api_budget_reservation_id:
            raise ClaudeCodeLifecycleError("metered API fallback requires approved budget reservation")
        budget_reservation_id = api_budget_reservation_id
    else:
        raise ClaudeCodeLifecycleError("unsupported executable Claude Code auth mode")
    return decision, auth_receipt, budget_reservation_id


def prepare_authenticated_claim(
    state: dict[str, Any],
    coordination: dict[str, Any],
    *,
    task_id: str,
    request_id: str,
    branch: str,
    current_main_sha: str,
    at: str,
    selection_evidence: dict[str, Any],
    oauth_present: bool,
    api_key_present: bool,
    capability_receipt: Mapping[str, Any] | None = None,
    trusted_workflow_sha: str | None = None,
    workflow_run: Mapping[str, Any] | None = None,
    capability_artifact: Mapping[str, Any] | None = None,
    capability_artifact_archive: bytes | None = None,
    allow_api_fallback: bool = False,
    api_budget_reservation_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Persist auth classification; create a V2 claim only when executable.

    MANUAL_ADAPTER_REQUIRED deliberately leaves the canonical task unclaimed so
    a credential/user-action blocker cannot occupy a coding worker indefinitely.
    """
    validate_authenticated_state(state)
    decision, auth_receipt, budget_reservation_id = _resolve_attempt_auth(
        task_id=task_id,
        request_id=request_id,
        branch=branch,
        current_main_sha=current_main_sha,
        at=at,
        oauth_present=oauth_present,
        api_key_present=api_key_present,
        capability_receipt=capability_receipt,
        trusted_workflow_sha=trusted_workflow_sha,
        workflow_run=workflow_run,
        capability_artifact=capability_artifact,
        capability_artifact_archive=capability_artifact_archive,
        allow_api_fallback=allow_api_fallback,
        api_budget_reservation_id=api_budget_reservation_id,
    )

    if not decision.execute:
        updated = _put_receipt(state, auth_receipt)
        validate_authenticated_state(updated)
        return updated, auth_receipt

    claim = {
        "event_id": f"claude-code-claim:{auth_receipt['attempt_id']}",
        "type": "CLAIM",
        "task_id": task_id,
        "at": at,
        "attempt_id": auth_receipt["attempt_id"],
        "request_id": request_id,
        "adapter": "claude_code_runner",
        "engine": "claude-code",
        "branch": branch,
        "base_main_sha": current_main_sha,
        "budget_reservation_id": budget_reservation_id,
    }
    claimed = apply_event(
        state,
        claim,
        coordination,
        current_main_sha=current_main_sha,
        selection_evidence=selection_evidence,
    )
    claimed = _put_receipt(claimed, auth_receipt)
    validate_authenticated_state(claimed)
    return claimed, auth_receipt


def prepare_authenticated_reexecution(
    state: dict[str, Any],
    coordination: dict[str, Any],
    *,
    kind: str,
    task_id: str,
    request_id: str,
    current_main_sha: str,
    at: str,
    oauth_present: bool,
    api_key_present: bool,
    capability_receipt: Mapping[str, Any] | None = None,
    trusted_workflow_sha: str | None = None,
    workflow_run: Mapping[str, Any] | None = None,
    capability_artifact: Mapping[str, Any] | None = None,
    capability_artifact_archive: bytes | None = None,
    allow_api_fallback: bool = False,
    api_budget_reservation_id: str | None = None,
    head_sha: str | None = None,
    repair_id: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Create a fresh authenticated V2 RETRY/REBASE attempt.

    Attempt-creating lifecycle transitions must never inherit an earlier auth or
    budget receipt implicitly. Every retry/rebase receives a fresh immutable auth
    receipt and therefore a fresh subscription proof binding or API budget gate.
    """
    validate_authenticated_state(state)
    if kind not in {"RETRY", "REBASE"}:
        raise ClaudeCodeLifecycleError("authenticated reexecution supports RETRY or REBASE only")
    record = state.get("tasks", {}).get(task_id)
    if not isinstance(record, Mapping):
        raise ClaudeCodeLifecycleError("authenticated reexecution requires an existing V2 task")
    active = record.get("attempts", {}).get(record.get("active_attempt"))
    if not isinstance(active, Mapping) or active.get("engine") != "claude-code":
        raise ClaudeCodeLifecycleError("authenticated reexecution requires a Claude Code attempt")
    branch = active.get("branch")
    if not isinstance(branch, str) or not branch:
        raise ClaudeCodeLifecycleError("active Claude Code branch is malformed")

    decision, auth_receipt, budget_reservation_id = _resolve_attempt_auth(
        task_id=task_id,
        request_id=request_id,
        branch=branch,
        current_main_sha=current_main_sha,
        at=at,
        oauth_present=oauth_present,
        api_key_present=api_key_present,
        capability_receipt=capability_receipt,
        trusted_workflow_sha=trusted_workflow_sha,
        workflow_run=workflow_run,
        capability_artifact=capability_artifact,
        capability_artifact_archive=capability_artifact_archive,
        allow_api_fallback=allow_api_fallback,
        api_budget_reservation_id=api_budget_reservation_id,
    )
    if not decision.execute:
        updated = _put_receipt(state, auth_receipt)
        validate_authenticated_state(updated)
        return updated, auth_receipt

    event: dict[str, Any] = {
        "event_id": f"claude-code-{kind.lower()}:{auth_receipt['attempt_id']}",
        "type": kind,
        "task_id": task_id,
        "at": at,
        "attempt_id": auth_receipt["attempt_id"],
        "request_id": request_id,
        "base_main_sha": current_main_sha,
        "budget_reservation_id": budget_reservation_id,
    }
    if head_sha is not None:
        event["head_sha"] = head_sha
    if repair_id is not None:
        event["repair_id"] = repair_id

    updated = apply_event(
        state,
        event,
        coordination,
        current_main_sha=current_main_sha,
    )
    updated = _put_receipt(updated, auth_receipt)
    validate_authenticated_state(updated)
    return updated, auth_receipt


def apply_authenticated_event(
    state: dict[str, Any],
    event: dict[str, Any],
    coordination: dict[str, Any],
    *,
    current_main_sha: str,
    selection_evidence: dict[str, Any] | None = None,
    v1_document: dict[str, Any] | None = None,
) -> dict[str, Any]:
    validate_authenticated_state(state)
    if event.get("type") in _ATTEMPT_CREATING_EVENTS:
        raise ClaudeCodeLifecycleError(
            "attempt-creating Claude Code events require authenticated preparation"
        )
    updated = apply_event(
        state,
        event,
        coordination,
        current_main_sha=current_main_sha,
        selection_evidence=selection_evidence,
        v1_document=v1_document,
    )
    validate_authenticated_state(updated)
    return updated


def validate_authenticated_state(state: Mapping[str, Any]) -> None:
    validate_v2(state)
    auth_map = state.get(AUTH_MAP, {})
    if not isinstance(auth_map, Mapping):
        raise ClaudeCodeLifecycleError("malformed Claude Code auth receipt map")

    seen_requests: set[tuple[str, str]] = set()
    for attempt_id, raw in auth_map.items():
        if not isinstance(raw, Mapping) or raw.get("attempt_id") != attempt_id:
            raise ClaudeCodeLifecycleError("malformed Claude Code auth receipt identity")
        try:
            validate_auth_receipt(raw)
        except AuthPolicyError as exc:
            raise ClaudeCodeLifecycleError(str(exc)) from exc

        request_key = (str(raw["task_id"]), str(raw["request_id"]))
        if request_key in seen_requests:
            raise ClaudeCodeLifecycleError("duplicate Claude Code task/request auth identity")
        seen_requests.add(request_key)
        if not raw["execute"]:
            continue

        record = state.get("tasks", {}).get(raw["task_id"])
        attempt = (record or {}).get("attempts", {}).get(attempt_id)
        if not isinstance(attempt, Mapping):
            raise ClaudeCodeLifecycleError("executable auth receipt is not bound to V2 attempt")
        if (
            attempt.get("engine") != "claude-code"
            or attempt.get("adapter") != "claude_code_runner"
            or attempt.get("request_id") != raw["request_id"]
            or attempt.get("branch") != raw["branch"]
            or attempt.get("base_main_sha") != raw["base_main_sha"]
        ):
            raise ClaudeCodeLifecycleError("Claude Code auth/V2 attempt provenance mismatch")

        reservation = attempt.get("budget_reservation_id")
        if raw["auth_mode"] == SUBSCRIPTION:
            expected = f"subscription-no-spend:{raw['content_digest'][:32]}"
            if reservation != expected or raw["budget_gate_required"]:
                raise ClaudeCodeLifecycleError("subscription attempt gained metered budget authority")
        elif raw["auth_mode"] == API_METERED:
            if not isinstance(reservation, str) or not reservation or reservation.startswith(
                "subscription-no-spend:"
            ):
                raise ClaudeCodeLifecycleError("metered API attempt lacks independent budget reservation")
        else:
            raise ClaudeCodeLifecycleError("non-executable auth mode bound to executable attempt")

    # Reciprocal coverage is mandatory: the V2 reducer can create RETRY/REBASE
    # attempts, so validating only receipts -> attempts would leave new attempts
    # able to bypass auth/budget proof. Every Claude Code attempt must have one
    # executable immutable receipt in the auth map.
    for task_id, record in state.get("tasks", {}).items():
        attempts = record.get("attempts", {}) if isinstance(record, Mapping) else {}
        for attempt_id, attempt in attempts.items():
            if not isinstance(attempt, Mapping) or attempt.get("engine") != "claude-code":
                continue
            raw = auth_map.get(attempt_id)
            if (
                not isinstance(raw, Mapping)
                or raw.get("execute") is not True
                or raw.get("task_id") != task_id
            ):
                raise ClaudeCodeLifecycleError(
                    "Claude Code V2 attempt lacks reciprocal executable auth receipt"
                )


def auth_state_digest(state: Mapping[str, Any]) -> str:
    validate_authenticated_state(state)
    return _digest(state.get(AUTH_MAP, {}))
