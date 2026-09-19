"""Bounded, review-only development task reconciliation and dispatch decisions.

The canonical task queue remains specialist_coordination plus its overrides.
This module stores only exact-head review evidence and dispatch receipts on the
existing non-main automation state branch. It never merges or promotes code.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from enum import Enum
from typing import Any

from agents.autonomous_cloud_runner import safe_branch
from orchestration.specialist_coordination import validate_state


REVIEW_LANES = ("security", "lead", "claude-adversarial")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
STALE_AFTER = timedelta(days=7)
WORKFLOW = "autonomous_cloud_specialist.yml"


class Lifecycle(str, Enum):
    READY = "READY"
    CLAIMED = "CLAIMED"
    RUNNING = "RUNNING"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    REVIEWING = "REVIEWING"
    REVISION_REQUIRED = "REVISION_REQUIRED"
    READY_FOR_INTEGRATION = "READY_FOR_INTEGRATION"
    BLOCKED = "BLOCKED"
    DONE = "DONE"


@dataclass(frozen=True)
class CandidateDecision:
    lifecycle: Lifecycle
    reason: str
    needs_review: bool = False
    head_sha: str | None = None


@dataclass(frozen=True)
class DispatchDecision:
    run: bool
    reason: str
    task_id: str | None = None
    branch: str | None = None
    workflow: str | None = None
    inputs: dict[str, str] | None = None


@dataclass(frozen=True)
class CycleResult:
    lifecycle: Lifecycle | None
    reason: str
    task_id: str | None = None
    head_sha: str | None = None


def _iso(now: datetime) -> str:
    if now.tzinfo is None:
        raise ValueError("timestamp must include timezone")
    return now.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def review_identity(task_id: str, pr_number: int, head_sha: str) -> str:
    if not task_id or not isinstance(pr_number, int) or pr_number <= 0 or not SHA_RE.fullmatch(head_sha):
        raise ValueError("malformed exact-head review identity")
    raw = json.dumps([task_id, pr_number, head_sha, REVIEW_LANES], separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def add_review_record(
    state: dict[str, Any], *, task_id: str, pr_number: int, head_sha: str,
    ci_state: str, outcomes: dict[str, str], now: datetime,
) -> dict[str, Any]:
    """Persist one immutable aggregate verdict for one exact PR head."""
    if state.get("version") != 1 or not isinstance(state.get("reviews"), dict):
        raise ValueError("malformed development orchestrator state")
    if ci_state != "success" or set(outcomes) != set(REVIEW_LANES):
        raise ValueError("incomplete exact-head review")
    if any(value not in {"APPROVE", "REJECT"} for value in outcomes.values()):
        raise ValueError("invalid reviewer outcome")
    key = review_identity(task_id, pr_number, head_sha)
    record = {
        "fingerprint": key, "task_id": task_id, "pr_number": pr_number,
        "head_sha": head_sha, "reviewer_lanes": list(REVIEW_LANES),
        "outcomes": dict(outcomes),
        "outcome": "APPROVE" if all(v == "APPROVE" for v in outcomes.values()) else "REJECT",
        "ci_state": ci_state, "reviewed_at": _iso(now),
    }
    prior = state["reviews"].get(key)
    if prior is not None:
        if prior != record:
            raise ValueError("review identity already has a different verdict")
        return state
    updated = copy.deepcopy(state)
    updated["reviews"][key] = record
    return updated


def parse_existing_lead_review(issue: dict[str, Any], *, head_sha: str, branch: str) -> dict[str, str] | None:
    """Import the existing Lead workflow's already-performed three-lane review.

    This is a read-only receipt parser. It never requests model work or sends
    private candidate content to an additional destination.
    """
    if (not isinstance(issue, dict) or not SHA_RE.fullmatch(head_sha)
            or issue.get("title") != f"autonomous-review: {head_sha}"
            or issue.get("state") != "open"
            or (issue.get("user") or {}).get("login") != "github-actions[bot]"):
        return None
    body = issue.get("body")
    if not isinstance(body, str) or f"Candidate branch: `{branch}`" not in body:
        return None
    if f"Exact reviewed SHA: `{head_sha}`" not in body:
        return None
    if "Security and Reliability: PASS on exact candidate SHA." not in body:
        return None
    labels = ("Autonomous Security review:", "Autonomous Lead review:",
              "Independent Claude adversarial review:")
    results: dict[str, str] = {}
    for lane, label in zip(REVIEW_LANES, labels):
        match = re.search(re.escape(label) + r"\s*```json\s*(.*?)\s*```", body, re.DOTALL)
        if not match:
            return None
        try:
            verdict = json.loads(match.group(1))
        except json.JSONDecodeError:
            return None
        if not isinstance(verdict, dict) or verdict.get("approve") is not True:
            return None
        if verdict.get("risk") not in {"low", "medium", "high"}:
            return None
        results[lane] = "APPROVE"
    return results


def _head(pr: dict[str, Any]) -> str | None:
    head = pr.get("head")
    sha = head.get("sha") if isinstance(head, dict) else None
    return sha if isinstance(sha, str) and SHA_RE.fullmatch(sha) else None


def _exact_ci(ci_runs: list[dict[str, Any]], head_sha: str) -> str:
    matches = [run for run in ci_runs if isinstance(run, dict)
               and run.get("head_sha") == head_sha
               and run.get("name") == "Security and Reliability"]
    if not matches:
        return "missing"
    statuses = {(run.get("status"), run.get("conclusion")) for run in matches}
    if any(status == "completed" and conclusion in
           {"failure", "cancelled", "timed_out", "action_required"}
           for status, conclusion in statuses):
        return "failure"
    if ("completed", "success") in statuses:
        return "success"
    return "pending"


def reconcile_candidate(
    task: dict[str, Any], pr: dict[str, Any], ci_runs: list[dict[str, Any]],
    review_record: dict[str, Any] | None, now: datetime,
) -> CandidateDecision:
    """Read durable PR/CI/review facts without mutating GitHub."""
    if task.get("status") == "DONE":
        return CandidateDecision(Lifecycle.DONE, "CANONICAL_DONE")
    if task.get("status") != "PR_OPEN" or not isinstance(pr, dict) or not isinstance(ci_runs, list):
        return CandidateDecision(Lifecycle.BLOCKED, "MALFORMED_CANDIDATE")
    head = _head(pr)
    if not head or not isinstance(pr.get("number"), int) or pr["number"] <= 0:
        return CandidateDecision(Lifecycle.BLOCKED, "MALFORMED_PR")
    if not isinstance(pr.get("base"), dict) or pr["base"].get("ref") != "main":
        return CandidateDecision(Lifecycle.BLOCKED, "UNEXPECTED_PR_BASE", head_sha=head)
    if pr.get("merged") is True:
        return CandidateDecision(Lifecycle.BLOCKED, "AWAIT_CANONICAL_DONE", head_sha=head)
    if pr.get("state") != "open":
        return CandidateDecision(Lifecycle.BLOCKED, "PR_NOT_OPEN", head_sha=head)
    try:
        updated_at = datetime.fromisoformat(str(pr["updated_at"]).replace("Z", "+00:00"))
        if updated_at.tzinfo is None:
            raise ValueError("naive timestamp")
    except (KeyError, TypeError, ValueError):
        return CandidateDecision(Lifecycle.BLOCKED, "MALFORMED_PR_TIMESTAMP", head_sha=head)
    ci = _exact_ci(ci_runs, head)
    if ci == "failure":
        return CandidateDecision(Lifecycle.REVISION_REQUIRED, "FAILED_EXACT_HEAD_CI", head_sha=head)
    if ci != "success":
        if now - updated_at > STALE_AFTER:
            return CandidateDecision(Lifecycle.BLOCKED, "STALE_PR_WITHOUT_CI", head_sha=head)
        return CandidateDecision(Lifecycle.RUNNING, "WAIT_EXACT_HEAD_CI", head_sha=head)
    if review_record is None:
        return CandidateDecision(Lifecycle.AWAITING_REVIEW, "EXACT_HEAD_REVIEW_REQUIRED", True, head)
    if not isinstance(review_record, dict):
        return CandidateDecision(Lifecycle.BLOCKED, "MALFORMED_REVIEW", head_sha=head)
    if review_record.get("head_sha") != head:
        return CandidateDecision(Lifecycle.AWAITING_REVIEW, "HEAD_CHANGED", True, head)
    try:
        key = review_identity(str(task.get("id") or ""), pr["number"], head)
    except ValueError:
        return CandidateDecision(Lifecycle.BLOCKED, "MALFORMED_TASK_ID", head_sha=head)
    if (review_record.get("fingerprint") != key
            or review_record.get("task_id") != task.get("id")
            or review_record.get("pr_number") != pr["number"]
            or review_record.get("ci_state") != "success"
            or review_record.get("reviewer_lanes") != list(REVIEW_LANES)
            or set(review_record.get("outcomes") or {}) != set(REVIEW_LANES)):
        return CandidateDecision(Lifecycle.BLOCKED, "MALFORMED_REVIEW", head_sha=head)
    outcomes = review_record["outcomes"]
    if any(value not in {"APPROVE", "REJECT"} for value in outcomes.values()):
        return CandidateDecision(Lifecycle.BLOCKED, "MALFORMED_REVIEW", head_sha=head)
    expected = "APPROVE" if all(v == "APPROVE" for v in outcomes.values()) else "REJECT"
    if review_record.get("outcome") != expected:
        return CandidateDecision(Lifecycle.BLOCKED, "MALFORMED_REVIEW", head_sha=head)
    if expected == "REJECT":
        return CandidateDecision(Lifecycle.REVISION_REQUIRED, "REVIEW_REJECTED", head_sha=head)
    return CandidateDecision(Lifecycle.READY_FOR_INTEGRATION, "EXACT_HEAD_REVIEW_PASSED", head_sha=head)


def verify_dispatch_task(requested_id: str, selected_task: dict[str, Any] | None) -> None:
    """The receiving runner calls this before any reservation or model work."""
    if not requested_id or not isinstance(selected_task, dict) or selected_task.get("id") != requested_id:
        raise ValueError("task ID mismatch")


def select_successor(
    coordination: dict[str, Any], routing_policy: dict[str, Any],
    runner_config: dict[str, Any], claimed_branches: set[str],
    dispatches: dict[str, Any], budget_allowed: bool,
) -> DispatchDecision:
    """Select one canonical READY task, then fail closed if V1 cannot run it."""
    try:
        validate_state(coordination)
    except (KeyError, TypeError, ValueError, RuntimeError):
        return DispatchDecision(False, "MALFORMED_CANONICAL_STATE")
    if (not isinstance(claimed_branches, set) or not isinstance(dispatches, dict)
            or not isinstance(routing_policy, dict) or not isinstance(runner_config, dict)):
        return DispatchDecision(False, "MALFORMED_ORCHESTRATOR_INPUT")
    ready = sorted((t for t in coordination["tasks"] if t["status"] == "READY"),
                   key=lambda t: (int(t.get("priority", 999999)), t["id"]))
    if not ready:
        return DispatchDecision(False, "NO_READY_TASK")
    task = ready[0]
    task_id = task["id"]
    if task.get("blockers"):
        return DispatchDecision(False, "TASK_BLOCKED", task_id)
    by_id = {t["id"]: t for t in coordination["tasks"]}
    if any(by_id.get(str(dep).split(maxsplit=1)[0], {}).get("status") != "DONE"
           for dep in task.get("dependencies", []) if str(dep).startswith("COORD-")):
        return DispatchDecision(False, "DEPENDENCY_NOT_DONE", task_id)
    if task.get("eligible_engines") is not None and "chatgpt" not in task["eligible_engines"]:
        return DispatchDecision(False, "ENGINE_INELIGIBLE", task_id)
    if task.get("engine_claim") not in {None, "chatgpt"}:
        return DispatchDecision(False, "OTHER_ENGINE_CLAIM", task_id)
    routes = routing_policy.get("routes") or {}
    luna = routes.get("api_luna") or {}
    settings = (runner_config.get("roles") or {}).get(task.get("owner")) or {}
    if (task.get("owner") != "data-market" or luna.get("executor") != "openai_api"
            or luna.get("model") != "gpt-5.6-luna"
            or settings.get("model") != luna.get("model")
            or task.get("owner") not in runner_config.get("autonomous_roles", [])
            or not (runner_config.get("models") or {}).get(luna["model"], {}).get("enabled")
            or not runner_config.get("enabled")):
        return DispatchDecision(False, "MANUAL_ADAPTER_REQUIRED", task_id)
    branch = safe_branch(task["owner"], task_id)
    if branch in claimed_branches or task_id in dispatches:
        return DispatchDecision(False, "TASK_ALREADY_CLAIMED", task_id, branch)
    if not budget_allowed:
        return DispatchDecision(False, "SHARED_BUDGET_DENIED", task_id, branch)
    return DispatchDecision(True, "READY", task_id, branch, WORKFLOW, {"task_id": task_id})


def _valid_state(state: Any) -> bool:
    return (isinstance(state, dict) and state.get("version") == 1
            and all(isinstance(state.get(key), dict) for key in
                    ("reviews", "dispatches", "review_attempts"))
            and isinstance(state.get("runs"), list))


def _pr_number(raw: Any) -> int | None:
    if isinstance(raw, int) and raw > 0:
        return raw
    if isinstance(raw, str):
        match = re.search(r"(?:/pull/|#)([1-9][0-9]*)$", raw)
        if match:
            return int(match.group(1))
    return None


def _review_for_task(state: dict[str, Any], task_id: str, pr_number: int, head_sha: str) -> dict | None:
    key = review_identity(task_id, pr_number, head_sha)
    exact = state["reviews"].get(key)
    if exact is not None:
        return exact
    # Supply a prior record only to distinguish a changed head from the
    # first review. The prior approval can never authorize the new head.
    prior = [r for r in state["reviews"].values()
             if isinstance(r, dict) and r.get("task_id") == task_id
             and r.get("pr_number") == pr_number]
    return prior[-1] if prior else None


def run_existing_review_cycle(
    coordination: dict[str, Any], routing_policy: dict[str, Any], runner_config: dict[str, Any],
    api: Any, store: Any, budget: Any, now: datetime, expected_main_sha: str,
) -> CycleResult:
    """Reconcile existing three-lane evidence, then dispatch at most one task.

    The review request contains only task/PR/head metadata. Existing Lead
    review evidence is imported only after all three lanes and exact-head CI
    are verified. No model call or PR diff transfer occurs in this cycle.
    """
    try:
        validate_state(coordination)
    except (KeyError, TypeError, ValueError, RuntimeError):
        return CycleResult(None, "MALFORMED_CANONICAL_STATE")
    if not SHA_RE.fullmatch(expected_main_sha) or api.current_main_sha() != expected_main_sha:
        return CycleResult(None, "MAIN_CHANGED")
    state = store.load()
    if not _valid_state(state):
        return CycleResult(None, "MALFORMED_ORCHESTRATOR_STATE")

    candidates = sorted((task for task in coordination["tasks"] if task["status"] == "PR_OPEN"),
                        key=lambda task: (int(task.get("priority", 999999)), task["id"]))
    if candidates:
        task = candidates[0]
        task_id = task["id"]
        number = _pr_number(task.get("pr"))
        if number is None:
            return CycleResult(Lifecycle.BLOCKED, "MALFORMED_PR_REFERENCE", task_id)
        pr = api.get_pr(number)
        head = _head(pr) if isinstance(pr, dict) else None
        if head is None:
            return CycleResult(Lifecycle.BLOCKED, "MALFORMED_PR", task_id)
        head_ref = pr.get("head", {}).get("ref")
        if (pr.get("head", {}).get("repo") or {}).get("full_name") != api.repo:
            return CycleResult(Lifecycle.BLOCKED, "PR_REPOSITORY_MISMATCH", task_id, head)
        if head_ref not in {task.get("branch"), safe_branch(task["owner"], task_id)}:
            return CycleResult(Lifecycle.BLOCKED, "PR_BRANCH_MISMATCH", task_id, head)
        decision = reconcile_candidate(task, pr, api.security_runs(head_ref),
                                       _review_for_task(state, task_id, number, head), now)
        if not decision.needs_review:
            reason = ("WAIT_FOR_LEAD_INTEGRATION" if decision.lifecycle is Lifecycle.READY_FOR_INTEGRATION
                      else decision.reason)
            return CycleResult(decision.lifecycle, reason, task_id, head)

        key = review_identity(task_id, number, head)
        outcomes = parse_existing_lead_review(api.get_review_issue(head),
                                              head_sha=head, branch=head_ref)
        if outcomes is not None:
            if api.get_pr(number).get("head", {}).get("sha") != head:
                return CycleResult(Lifecycle.AWAITING_REVIEW, "HEAD_CHANGED", task_id, head)
            if api.current_main_sha() != expected_main_sha:
                return CycleResult(None, "MAIN_CHANGED", task_id, head)
            completed = add_review_record(state, task_id=task_id, pr_number=number,
                                          head_sha=head, ci_state="success", outcomes=outcomes,
                                          now=now)
            if key in completed["review_attempts"]:
                completed["review_attempts"][key]["status"] = "COMPLETED"
                completed["review_attempts"][key]["completed_at"] = _iso(now)
            store.save(completed)
            return CycleResult(Lifecycle.READY_FOR_INTEGRATION,
                               "EXACT_HEAD_REVIEW_IMPORTED", task_id, head)
        if key in state["review_attempts"]:
            return CycleResult(Lifecycle.REVIEWING, "WAIT_FOR_INDEPENDENT_REVIEW", task_id, head)
        requested = copy.deepcopy(state)
        requested["review_attempts"][key] = {
            "status": "REQUESTED", "task_id": task_id, "pr_number": number,
            "head_sha": head, "requested_at": _iso(now),
        }
        if api.current_main_sha() != expected_main_sha:
            return CycleResult(None, "MAIN_CHANGED", task_id, head)
        store.save(requested)
        api.request_review(task_id, number, head)
        return CycleResult(Lifecycle.AWAITING_REVIEW, "REVIEW_REQUESTED", task_id, head)

    running = sorted((task for task in coordination["tasks"] if task["status"] == "IN_PROGRESS"),
                     key=lambda task: (int(task.get("priority", 999999)), task["id"]))
    if running:
        return CycleResult(Lifecycle.RUNNING, "WAIT_FOR_CANONICAL_COMPLETION", running[0]["id"])

    if not any(task["status"] == "READY" for task in coordination["tasks"]):
        return CycleResult(None, "NO_READY_TASK")

    claimed = set()
    for task in coordination["tasks"]:
        if task["status"] == "READY":
            branch = safe_branch(task["owner"], task["id"])
            if api.branch_exists(branch):
                claimed.add(branch)
    budget_allowed = bool(budget.can_dispatch(runner_config, "data-market", now))
    dispatch = select_successor(coordination, routing_policy, runner_config,
                                claimed, state["dispatches"], budget_allowed)
    if not dispatch.run:
        return CycleResult(Lifecycle.READY if dispatch.task_id else None,
                           dispatch.reason, dispatch.task_id)
    intent = copy.deepcopy(state)
    intent["dispatches"][dispatch.task_id] = {
        "status": "REQUESTED", "branch": dispatch.branch,
        "workflow": dispatch.workflow, "inputs": dispatch.inputs,
        "requested_at": _iso(now),
    }
    if api.current_main_sha() != expected_main_sha:
        return CycleResult(None, "MAIN_CHANGED", dispatch.task_id)
    store.save(intent)
    api.dispatch_workflow(dispatch.workflow, dispatch.inputs)
    sent = copy.deepcopy(intent)
    sent["dispatches"][dispatch.task_id]["status"] = "DISPATCHED"
    store.save(sent)
    return CycleResult(Lifecycle.CLAIMED, "DISPATCHED", dispatch.task_id)
