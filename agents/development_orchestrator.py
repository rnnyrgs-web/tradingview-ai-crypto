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
REVIEW_EVIDENCE_WAIT = timedelta(hours=2)
DISPATCH_VISIBILITY_WAIT = timedelta(minutes=5)
MAX_DISPATCH_ATTEMPTS = 2
WORKFLOW = "autonomous_cloud_specialist.yml"


class Lifecycle(str, Enum):
    READY = "READY"
    CLAIMED = "CLAIMED"
    RUNNING = "RUNNING"
    AWAITING_REVIEW = "AWAITING_REVIEW"
    REVIEWING = "REVIEWING"
    REVISION_REQUIRED = "REVISION_REQUIRED"
    READY_FOR_INTEGRATION = "READY_FOR_INTEGRATION"
    MANUAL_REVIEW_REQUIRED = "MANUAL_REVIEW_REQUIRED"
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


def parse_lead_execution_issue(issue: dict[str, Any], *, head_sha: str,
                               branch: str) -> dict[str, Any] | None:
    """Validate the existing Lead workflow's exact-head execution receipt."""
    if not isinstance(issue, dict) or not SHA_RE.fullmatch(head_sha):
        return None
    title = re.fullmatch(r"autonomous-review-attempt: " + re.escape(head_sha)
                         + r" run=([1-9][0-9]*)", str(issue.get("title")))
    body = issue.get("body")
    if (not title or issue.get("state") != "open"
            or (issue.get("user") or {}).get("login") != "github-actions[bot]"
            or not isinstance(body, str)
            or f"Candidate branch: `{branch}`" not in body
            or f"Exact reviewed SHA: `{head_sha}`" not in body
            or f"Workflow run: `{title.group(1)}`" not in body):
        return None
    main_match = re.search(r"^Workflow main SHA: `([0-9a-f]{40})`$", body, re.MULTILINE)
    if not main_match:
        return None
    marker = re.search(r"^Outcome: `(STARTED|APPROVED|REJECTED|FAILED)`$", body, re.MULTILINE)
    if not marker:
        return None
    result: dict[str, Any] = {"status": marker.group(1), "run_id": int(title.group(1)),
                              "main_sha": main_match.group(1)}
    if result["status"] == "REJECTED":
        labels = ("Autonomous Security review:", "Autonomous Lead review:",
                  "Independent Claude adversarial review:")
        outcomes: dict[str, str] = {}
        for lane, label in zip(REVIEW_LANES, labels):
            match = re.search(re.escape(label) + r"\s*```json\s*(.*?)\s*```", body, re.DOTALL)
            if not match:
                return None
            try:
                verdict = json.loads(match.group(1))
            except json.JSONDecodeError:
                return None
            if (not isinstance(verdict, dict) or not isinstance(verdict.get("approve"), bool)
                    or verdict.get("risk") not in {"low", "medium", "high"}):
                return None
            outcomes[lane] = "APPROVE" if verdict["approve"] else "REJECT"
        if all(value == "APPROVE" for value in outcomes.values()):
            return None
        result["outcomes"] = outcomes
    return result


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


def _dispatch_request_id(task_id: str, main_sha: str, attempt_number: int) -> str:
    raw = json.dumps([task_id, main_sha, attempt_number], separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:24]


def _dispatch_attempt(task_id: str, main_sha: str, number: int, now: datetime) -> dict[str, str]:
    return {"request_id": _dispatch_request_id(task_id, main_sha, number),
            "requested_at": _iso(now)}


def _send_dispatch(api: Any, store: Any, state: dict[str, Any], task_id: str,
                   workflow: str, branch: str, main_sha: str, now: datetime,
                   *, retry: bool) -> CycleResult:
    updated = copy.deepcopy(state)
    prior = updated["dispatches"].get(task_id)
    attempts = list(prior["attempts"]) if retry else []
    attempt = _dispatch_attempt(task_id, main_sha, len(attempts) + 1, now)
    attempts.append(attempt)
    inputs = {"task_id": task_id, "orchestrator_request_id": attempt["request_id"]}
    updated["dispatches"][task_id] = {
        "status": "REQUESTED", "branch": branch, "workflow": workflow,
        "main_sha": main_sha, "attempts": attempts,
    }
    store.save(updated)
    try:
        api.dispatch_workflow(workflow, inputs)
    except Exception:
        # GitHub can accept a dispatch and still lose the acknowledgment.
        # The next cycle checks exact run evidence before any retry.
        return CycleResult(Lifecycle.RUNNING, "DISPATCH_OUTCOME_UNKNOWN", task_id)
    acknowledged = copy.deepcopy(updated)
    acknowledged["dispatches"][task_id]["status"] = "DISPATCHED"
    store.save(acknowledged)
    return CycleResult(Lifecycle.CLAIMED,
                       "DISPATCH_RETRIED" if retry else "DISPATCHED", task_id)


def _worker_result(outcome: Any, task_id: str) -> CycleResult:
    if not isinstance(outcome, dict) or outcome.get("status") not in {
        "PR_CREATED", "NO_CHANGE", "BLOCKED", "WAIT", "TASK_MISMATCH", "NOT_CLAIMED", "FAILED"
    } or not isinstance(outcome.get("reason"), str) or not outcome["reason"].strip():
        return CycleResult(Lifecycle.BLOCKED, "MALFORMED_WORKER_OUTCOME", task_id)
    status = outcome["status"]
    if status == "PR_CREATED":
        if (not isinstance(outcome.get("pr_number"), int) or outcome["pr_number"] <= 0
                or not isinstance(outcome.get("head_sha"), str)
                or not SHA_RE.fullmatch(outcome["head_sha"])):
            return CycleResult(Lifecycle.BLOCKED, "MALFORMED_WORKER_OUTCOME", task_id)
        return CycleResult(Lifecycle.AWAITING_REVIEW, "PR_CREATED_AWAIT_CANONICAL_STATE",
                           task_id, outcome["head_sha"])
    if status == "WAIT":
        retry_at = outcome.get("retry_at")
        try:
            stamp = datetime.fromisoformat(str(retry_at).replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                raise ValueError("naive retry timestamp")
        except (TypeError, ValueError):
            return CycleResult(Lifecycle.BLOCKED, "MALFORMED_WORKER_OUTCOME", task_id)
        return CycleResult(Lifecycle.READY, "WORKER_WAIT", task_id)
    if status == "NO_CHANGE":
        return CycleResult(Lifecycle.DONE, "WORKER_NO_CHANGE_AWAIT_CANONICAL_UPDATE", task_id)
    return CycleResult(Lifecycle.BLOCKED, f"WORKER_{status}", task_id)


def _reconcile_dispatch(api: Any, store: Any, budget: Any, runner_config: dict[str, Any],
                        state: dict[str, Any], task_id: str, main_sha: str,
                        now: datetime) -> CycleResult:
    intent = state["dispatches"].get(task_id)
    if (not isinstance(intent, dict) or intent.get("workflow") != WORKFLOW
            or not isinstance(intent.get("main_sha"), str)
            or not SHA_RE.fullmatch(intent["main_sha"])
            or intent.get("branch") != safe_branch("data-market", task_id)
            or intent.get("status") not in {"REQUESTED", "DISPATCHED", "OBSERVED", "BLOCKED", "COMPLETED"}
            or not isinstance(intent.get("attempts"), list)
            or not intent["attempts"]
            or len(intent["attempts"]) > MAX_DISPATCH_ATTEMPTS):
        return CycleResult(Lifecycle.BLOCKED, "MALFORMED_DISPATCH_INTENT", task_id)
    attempts = intent["attempts"]
    try:
        stamps = [datetime.fromisoformat(a["requested_at"].replace("Z", "+00:00"))
                  for a in attempts]
        ids = [a["request_id"] for a in attempts]
        if (any(stamp.tzinfo is None or stamp > now for stamp in stamps)
                 or any(not re.fullmatch(r"[0-9a-f]{24}", rid) for rid in ids)
                 or len(set(ids)) != len(ids)
                 or ids != [_dispatch_request_id(task_id, intent["main_sha"], number)
                            for number in range(1, len(ids) + 1)]):
            raise ValueError("malformed attempts")
    except (KeyError, TypeError, AttributeError, ValueError):
        return CycleResult(Lifecycle.BLOCKED, "MALFORMED_DISPATCH_INTENT", task_id)
    if intent.get("worker_outcome") is not None:
        if (intent["status"] != "COMPLETED"
                or not isinstance(intent.get("run_id"), int)
                or intent["run_id"] <= 0
                or intent.get("run_conclusion") != "success"):
            return CycleResult(Lifecycle.BLOCKED, "MALFORMED_DISPATCH_INTENT", task_id)
        return _worker_result(intent["worker_outcome"], task_id)
    if intent["status"] == "COMPLETED":
        return CycleResult(Lifecycle.BLOCKED, "MALFORMED_DISPATCH_INTENT", task_id)
    run = api.find_dispatch_run(task_id, ids, intent["main_sha"], stamps[0])
    if run is not None:
        if (not isinstance(run, dict) or run.get("request_id") not in ids
                or run.get("task_id") != task_id or run.get("head_sha") != intent["main_sha"]
                or not isinstance(run.get("id"), int) or run["id"] <= 0
                or run.get("status") not in {"queued", "in_progress", "completed"}):
            return CycleResult(Lifecycle.BLOCKED, "MALFORMED_DISPATCH_RUN", task_id)
        if run["status"] == "completed" and run.get("conclusion") not in {
            "success", "failure", "cancelled", "timed_out", "action_required"
        }:
            return CycleResult(Lifecycle.BLOCKED, "MALFORMED_DISPATCH_RUN", task_id)
        failed = run["status"] == "completed" and run.get("conclusion") != "success"
        outcome = None
        if run["status"] == "completed" and not failed:
            outcome = api.get_dispatch_outcome(run["id"], run["request_id"], task_id,
                                               intent["main_sha"], intent["branch"])
            decision = _worker_result(outcome, task_id)
            if decision.reason == "MALFORMED_WORKER_OUTCOME":
                return decision
            if outcome["status"] == "PR_CREATED":
                pr = api.get_pr(outcome["pr_number"])
                if (not isinstance(pr, dict) or _head(pr) != outcome["head_sha"]
                        or (pr.get("head") or {}).get("ref") != intent["branch"]
                        or ((pr.get("head") or {}).get("repo") or {}).get("full_name") != api.repo
                        or pr.get("state") != "open"):
                    return CycleResult(Lifecycle.BLOCKED, "WORKER_PR_MISMATCH", task_id)
        observed = copy.deepcopy(state)
        observed["dispatches"][task_id]["status"] = (
            "BLOCKED" if failed else "COMPLETED" if outcome is not None else "OBSERVED")
        observed["dispatches"][task_id]["run_id"] = run["id"]
        observed["dispatches"][task_id]["run_status"] = run["status"]
        observed["dispatches"][task_id]["run_conclusion"] = run.get("conclusion")
        if outcome is not None:
            observed["dispatches"][task_id]["worker_outcome"] = outcome
        if observed != state:
            store.save(observed)
        if failed:
            return CycleResult(Lifecycle.BLOCKED, "WORKFLOW_FAILED", task_id)
        if run["status"] == "completed":
            return decision
        return CycleResult(Lifecycle.CLAIMED, "DISPATCH_RUN_ADOPTED", task_id)
    if api.branch_exists(intent["branch"]):
        return CycleResult(Lifecycle.CLAIMED, "TASK_BRANCH_EXISTS", task_id)
    if intent["status"] == "OBSERVED":
        return CycleResult(Lifecycle.CLAIMED, "DISPATCH_RUN_PREVIOUSLY_OBSERVED", task_id)
    if intent["status"] == "BLOCKED":
        reason = "WORKFLOW_FAILED" if intent.get("run_conclusion") else "DISPATCH_RETRY_EXHAUSTED"
        return CycleResult(Lifecycle.BLOCKED, reason, task_id)
    if now - stamps[-1] <= DISPATCH_VISIBILITY_WAIT:
        return CycleResult(Lifecycle.RUNNING, "DISPATCH_VISIBILITY_WAIT", task_id)
    if len(attempts) >= MAX_DISPATCH_ATTEMPTS:
        blocked = copy.deepcopy(state)
        blocked["dispatches"][task_id]["status"] = "BLOCKED"
        store.save(blocked)
        return CycleResult(Lifecycle.BLOCKED, "DISPATCH_RETRY_EXHAUSTED", task_id)
    if not budget.can_dispatch(runner_config, "data-market", now):
        return CycleResult(Lifecycle.READY, "SHARED_BUDGET_DENIED", task_id)
    if api.current_main_sha() != main_sha or intent["main_sha"] != main_sha:
        return CycleResult(None, "MAIN_CHANGED", task_id)
    return _send_dispatch(api, store, state, task_id, WORKFLOW,
                          intent["branch"], intent["main_sha"], now, retry=True)


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
        if pr.get("state") == "open" and not api.pr_base_is_current(head_ref, head, expected_main_sha):
            return CycleResult(Lifecycle.REVISION_REQUIRED, "STALE_PR_BASE", task_id, head)
        decision = reconcile_candidate(task, pr, api.security_runs(head_ref),
                                       _review_for_task(state, task_id, number, head), now)
        if not decision.needs_review:
            reason = ("WAIT_FOR_LEAD_INTEGRATION" if decision.lifecycle is Lifecycle.READY_FOR_INTEGRATION
                      else decision.reason)
            return CycleResult(decision.lifecycle, reason, task_id, head)

        key = review_identity(task_id, number, head)
        execution = api.get_lead_review_execution(head, head_ref)
        if not isinstance(execution, dict) or execution.get("status") not in {
            "MISSING", "RUNNING", "REJECTED", "FAILED", "APPROVED"
        }:
            return CycleResult(Lifecycle.BLOCKED, "MALFORMED_REVIEW_EXECUTION", task_id, head)
        outcomes = parse_existing_lead_review(api.get_review_issue(head),
                                              head_sha=head, branch=head_ref)
        if execution["status"] == "REJECTED":
            if outcomes is not None:
                return CycleResult(Lifecycle.BLOCKED, "CONTRADICTORY_REVIEW_EVIDENCE", task_id, head)
            try:
                rejected = add_review_record(state, task_id=task_id, pr_number=number,
                                             head_sha=head, ci_state="success",
                                             outcomes=execution.get("outcomes"), now=now)
            except (TypeError, ValueError):
                return CycleResult(Lifecycle.BLOCKED, "MALFORMED_REVIEW_EXECUTION", task_id, head)
            rejected["review_attempts"][key] = {
                "status": "REJECTED", "task_id": task_id, "pr_number": number,
                "head_sha": head, "run_id": execution.get("run_id"), "completed_at": _iso(now),
            }
            if api.current_main_sha() != expected_main_sha:
                return CycleResult(None, "MAIN_CHANGED", task_id, head)
            store.save(rejected)
            return CycleResult(Lifecycle.REVISION_REQUIRED, "REVIEW_REJECTED", task_id, head)
        if outcomes is not None:
            if execution["status"] == "FAILED":
                return CycleResult(Lifecycle.BLOCKED, "CONTRADICTORY_REVIEW_EVIDENCE", task_id, head)
            if execution["status"] == "RUNNING":
                return CycleResult(Lifecycle.REVIEWING, "REVIEW_WORKFLOW_RUNNING", task_id, head)
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
        if execution["status"] in {"FAILED", "APPROVED"}:
            if execution["status"] == "APPROVED":
                if not (isinstance(state["review_attempts"].get(key), dict)
                        and state["review_attempts"][key].get("status") == "BLOCKED"):
                    missing = copy.deepcopy(state)
                    missing["review_attempts"][key] = {
                        "status": "BLOCKED", "task_id": task_id,
                        "pr_number": number, "head_sha": head,
                        "reason": "APPROVAL_RECEIPT_MISSING", "checked_at": _iso(now),
                    }
                    store.save(missing)
                return CycleResult(Lifecycle.BLOCKED, "APPROVAL_RECEIPT_MISSING", task_id, head)
            if (isinstance(state["review_attempts"].get(key), dict)
                    and state["review_attempts"][key].get("status") == "BLOCKED"):
                return CycleResult(Lifecycle.BLOCKED, "REVIEW_WORKFLOW_FAILED", task_id, head)
            blocked = copy.deepcopy(state)
            blocked["review_attempts"][key] = {
                "status": "BLOCKED", "task_id": task_id, "pr_number": number,
                "head_sha": head, "run_id": execution.get("run_id"),
                "failed_at": _iso(now),
            }
            if state["review_attempts"].get(key) != blocked["review_attempts"][key]:
                store.save(blocked)
            return CycleResult(Lifecycle.BLOCKED, "REVIEW_WORKFLOW_FAILED", task_id, head)
        if execution["status"] == "RUNNING":
            return CycleResult(Lifecycle.REVIEWING, "REVIEW_WORKFLOW_RUNNING", task_id, head)
        if not api.lead_can_review(head_ref, head, expected_main_sha):
            manual = copy.deepcopy(state)
            manual["review_attempts"][key] = {
                "status": "MANUAL_REVIEW_REQUIRED", "task_id": task_id,
                "pr_number": number, "head_sha": head,
            }
            if state["review_attempts"].get(key) != manual["review_attempts"][key]:
                store.save(manual)
            return CycleResult(Lifecycle.MANUAL_REVIEW_REQUIRED,
                               "MANUAL_REVIEW_REQUIRED", task_id, head)
        if key in state["review_attempts"]:
            attempt = state["review_attempts"][key]
            if not isinstance(attempt, dict) or attempt.get("head_sha") != head:
                return CycleResult(Lifecycle.BLOCKED, "MALFORMED_REVIEW_ATTEMPT", task_id, head)
            if attempt.get("status") == "BLOCKED":
                return CycleResult(Lifecycle.BLOCKED, "REVIEW_WORKFLOW_FAILED", task_id, head)
            if attempt.get("status") == "MANUAL_REVIEW_REQUIRED":
                return CycleResult(Lifecycle.MANUAL_REVIEW_REQUIRED,
                                   "MANUAL_REVIEW_REQUIRED", task_id, head)
            try:
                requested_at = datetime.fromisoformat(attempt["requested_at"].replace("Z", "+00:00"))
                if requested_at.tzinfo is None or requested_at > now:
                    raise ValueError("invalid review request timestamp")
            except (KeyError, AttributeError, ValueError):
                return CycleResult(Lifecycle.BLOCKED, "MALFORMED_REVIEW_ATTEMPT", task_id, head)
            if now - requested_at <= REVIEW_EVIDENCE_WAIT:
                return CycleResult(Lifecycle.AWAITING_REVIEW,
                                   "REVIEW_EVIDENCE_MISSING", task_id, head)
            timed_out = copy.deepcopy(state)
            timed_out["review_attempts"][key]["status"] = "MANUAL_REVIEW_REQUIRED"
            timed_out["review_attempts"][key]["timed_out_at"] = _iso(now)
            store.save(timed_out)
            return CycleResult(Lifecycle.MANUAL_REVIEW_REQUIRED,
                               "REVIEW_EVIDENCE_TIMEOUT", task_id, head)
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

    ready = sorted((task for task in coordination["tasks"] if task["status"] == "READY"),
                   key=lambda task: (int(task.get("priority", 999999)), task["id"]))
    if ready[0]["id"] in state["dispatches"]:
        return _reconcile_dispatch(api, store, budget, runner_config, state,
                                   ready[0]["id"], expected_main_sha, now)

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
    if api.current_main_sha() != expected_main_sha:
        return CycleResult(None, "MAIN_CHANGED", dispatch.task_id)
    return _send_dispatch(api, store, state, dispatch.task_id, dispatch.workflow,
                          dispatch.branch, expected_main_sha, now, retry=False)
