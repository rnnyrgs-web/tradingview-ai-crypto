"""V2-001 durable control-plane contract, deliberately without live dispatch.

The canonical task queue remains specialist_coordination (+ overrides). This
reducer is a versioned value stored under ``v2`` in V1's existing non-main
GitHubStateStore document. The store's Contents-API SHA is the CAS token;
callers must reload after a conflict, never replay against a stale snapshot.
Only externally verified facts may be submitted as events in production.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime
from typing import Any

from agents.autonomous_cloud_runner import safe_branch
from orchestration.rejected_fingerprints import is_rejected_fingerprint
from orchestration.specialist_coordination import validate_state

SHA = re.compile(r"^[0-9a-f]{40}$")
MAX_REPAIRS = 2
REVIEW_LANES = {"security", "independent"}
OUTCOMES = {"PR_CREATED", "NO_CHANGE", "BLOCKED", "WAIT", "TASK_MISMATCH", "FAILED"}
ESCALATIONS = {"credential_required", "plugin_required", "spending_approval_required",
               "paid_resource_recommendation", "repeated_failure", "manual_external_action",
               "ambiguous_high_impact_decision", "critical_security_incident"}

# Status describes an accepted adapter, not a theoretical provider feature.
# V2-001 does not wire any of these to a new live dispatch call.
ADAPTERS: dict[str, dict[str, Any]] = {
    "deterministic": dict(status="MANUAL", programmatic_dispatch=False, can_write_code=True,
                          can_write_research=True, can_review=False, can_create_pr=True,
                          can_merge=False, metered=False, budget_gate=False,
                          roles=["data-market", "quant-research"]),
    "api_luna": dict(status="AUTOMATIC", programmatic_dispatch=True, can_write_code=True,
                     can_write_research=True, can_review=False, can_create_pr=True,
                     can_merge=False, metered=True, budget_gate=True, roles=["data-market"]),
    "api_terra": dict(status="MANUAL", programmatic_dispatch=False, can_write_code=True,
                      can_write_research=True, can_review=False, can_create_pr=True,
                      can_merge=False, metered=True, budget_gate=True, roles=[]),
    "api_sol": dict(status="MANUAL", programmatic_dispatch=False, can_write_code=False,
                    can_write_research=True, can_review=True, can_create_pr=False,
                    can_merge=False, metered=True, budget_gate=True, roles=[]),
    "claude": dict(status="AUTOMATIC", programmatic_dispatch=True, can_write_code=False,
                   can_write_research=True, can_review=True, can_create_pr=True,
                   can_merge=False, metered=True, budget_gate=True, roles=["signal-accuracy"]),
    "claude-code": dict(status="AUTOMATIC", programmatic_dispatch=True, can_write_code=True,
                        can_write_research=False, can_review=True, can_create_pr=True,
                        can_merge=False, metered=True, budget_gate=True, roles=["testing-security"]),
    "work_astra": dict(status="MANUAL", programmatic_dispatch=False, can_write_code=True,
                       can_write_research=True, can_review=False, can_create_pr=True,
                       can_merge=False, metered=False, budget_gate=True, roles=[]),
    "codex": dict(status="MANUAL", programmatic_dispatch=False, can_write_code=True,
                  can_write_research=True, can_review=False, can_create_pr=True,
                  can_merge=False, metered=False, budget_gate=True, roles=[]),
    "independent_reviewer": dict(status="MANUAL", programmatic_dispatch=False,
                                  can_write_code=False, can_write_research=False,
                                  can_review=True, can_create_pr=False, can_merge=False,
                                  metered=True, budget_gate=True, roles=[]),
    "lead": dict(status="MANUAL", programmatic_dispatch=False, can_write_code=False,
                 can_write_research=False, can_review=True, can_create_pr=False,
                 can_merge=True, metered=False, budget_gate=False, roles=[]),
}

ENGINE_KIND = {"deterministic": "human", "api_luna": "chatgpt", "api_terra": "chatgpt",
               "api_sol": "chatgpt", "work_astra": "chatgpt", "codex": "chatgpt",
               "claude": "claude", "claude-code": "claude-code"}
ACCEPTED_RUNNERS = {"api_luna": "github_cloud_worker", "claude": "claude_runner",
                    "claude-code": "claude_code_runner"}


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValueError(message)


def _sha(value: Any) -> bool:
    return isinstance(value, str) and bool(SHA.fullmatch(value))


def _time(value: Any) -> bool:
    try:
        return isinstance(value, str) and datetime.fromisoformat(value.replace("Z", "+00:00")).tzinfo is not None
    except ValueError:
        return False


def _nonempty(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _digest(value: dict) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def empty_v2() -> dict:
    return {"version": 2, "tasks": {}, "events": {}, "escalations": {}, "successors": {}}


def persist_event(store: Any, event: dict, coordination: dict, main_sha: str,
                  read_main_sha: Any) -> dict:
    """Write V2 under V1's existing CAS document, never a second state file.

    GitHubStateStore.save requires the Contents API SHA captured by load. A
    conflict raises; the caller must reload and re-evaluate external facts.
    """
    _require(_sha(main_sha) and read_main_sha() == main_sha, "main advanced")
    document = store.load()
    _require(isinstance(document, dict) and document.get("version") == 1
             and all(isinstance(document.get(k), dict) for k in
                     ("reviews", "dispatches", "review_attempts"))
             and isinstance(document.get("runs"), list), "malformed V1 state")
    before = document.get("v2", empty_v2())
    after = apply_event(before, event, coordination, current_main_sha=main_sha)
    if after == before:
        return document
    _require(read_main_sha() == main_sha, "main advanced")
    changed = copy.deepcopy(document)
    changed["v2"] = after
    store.save(changed)
    return changed


def validate_v2(state: Any) -> None:
    _require(isinstance(state, dict) and state.get("version") == 2, "malformed v2 state")
    _require(all(isinstance(state.get(k), dict) for k in
                 ("tasks", "events", "escalations", "successors")), "malformed v2 maps")
    for task_id, record in state["tasks"].items():
        _require(_nonempty(task_id) and isinstance(record, dict)
                 and record.get("task_id") == task_id and _nonempty(record.get("status"))
                 and isinstance(record.get("attempts"), dict)
                 and isinstance(record.get("reviews"), dict)
                 and isinstance(record.get("repairs"), dict)
                 and isinstance(record.get("ci"), dict), "malformed v2 task")
        _require(record.get("active_attempt") in record["attempts"], "malformed active attempt")
        for attempt_id, attempt in record["attempts"].items():
            _require(isinstance(attempt, dict) and attempt.get("attempt_id") == attempt_id
                     and _sha(attempt.get("base_main_sha"))
                     and all(_nonempty(attempt.get(k)) for k in
                             ("request_id", "engine", "adapter", "branch"))
                     and _time(attempt.get("started_at")), "malformed attempt identity")
        for head, ci in record["ci"].items():
            _require(_sha(head) and isinstance(ci, dict) and ci.get("head_sha") == head
                     and ci.get("conclusion") in {"success", "failure"}
                     and _nonempty(ci.get("ci_id")), "malformed CI identity")
        for review_id, review in record["reviews"].items():
            _require(isinstance(review, dict) and review.get("review_id") == review_id
                     and _sha(review.get("head_sha"))
                     and review.get("head_sha") in record["ci"]
                     and record["ci"][review["head_sha"]]["conclusion"] == "success"
                     and set(review.get("reviewer_lanes") or []) == REVIEW_LANES
                     and review.get("outcome") in {"APPROVED", "REVISION_REQUIRED", "BLOCKED", "WAIT"},
                     "malformed review identity")
        for repair_id, repair in record["repairs"].items():
            _require(isinstance(repair, dict) and repair.get("repair_id") == repair_id
                     and repair.get("review_id") in record["reviews"]
                     and repair.get("owner") == record.get("owner"), "malformed repair identity")
    _require(all(_nonempty(k) and isinstance(v, str)
                 and bool(re.fullmatch(r"[0-9a-f]{64}", v))
                 for k, v in state["events"].items()),
             "malformed event receipts")


def route_task(task: dict, engine: str) -> dict[str, str]:
    adapter = ADAPTERS.get(engine)
    if not adapter or engine not in ENGINE_KIND:
        return {"status": "UNSUPPORTED", "reason": "MANUAL_ADAPTER_REQUIRED"}
    if adapter["status"] != "AUTOMATIC" or not adapter["programmatic_dispatch"]:
        return {"status": "MANUAL", "reason": "MANUAL_ADAPTER_REQUIRED"}
    kind = ENGINE_KIND[engine]
    if (task.get("eligible_engines") is not None and kind not in task["eligible_engines"]
            or task.get("engine_claim") not in {None, kind}
            or task.get("owner") not in adapter["roles"]):
        return {"status": "INELIGIBLE", "reason": "ENGINE_INELIGIBLE"}
    return {"status": "AUTOMATIC", "reason": "READY"}


def select_task(coordination: dict, *, engine: str, claimed_branches: set[str],
                active_prs: set[int], rejected: list[dict], strategy_queue: dict,
                now: datetime | None = None) -> dict | None:
    """Select from the canonical queue only; unknown evidence fails closed."""
    validate_state(coordination)
    _require(isinstance(claimed_branches, set) and isinstance(active_prs, set)
             and isinstance(rejected, list) and isinstance(strategy_queue, dict),
             "malformed selection evidence")
    _require(strategy_queue.get("active_deep_candidate", "MISSING") != "MISSING"
             and strategy_queue.get("max_active_deep_candidates", 1) == 1,
             "malformed strategy capacity")
    by_id = {task["id"]: task for task in coordination["tasks"]}
    for task in sorted((t for t in coordination["tasks"] if t["status"] == "READY"),
                       key=lambda t: (int(t.get("priority", 999999)), t["id"])):
        if task["blockers"] or route_task(task, engine)["status"] != "AUTOMATIC":
            continue
        if task.get("work_mode") == "DEEP" and strategy_queue["active_deep_candidate"] is not None:
            continue
        fingerprint = task.get("fingerprint_id")
        if fingerprint and is_rejected_fingerprint(str(fingerprint), rejected):
            continue
        if any(by_id.get(str(dep).split(maxsplit=1)[0], {}).get("status") != "DONE"
               for dep in task["dependencies"] if str(dep).startswith("COORD-")):
            continue
        if (task.get("pr") is not None or safe_branch(task["owner"], task["id"]) in claimed_branches
                or safe_branch(task["owner"], task["id"]) in active_prs
                or any(t["owner"] == task["owner"] and t["id"] != task["id"]
                       and t["status"] in {"IN_PROGRESS", "PR_OPEN"} for t in coordination["tasks"])):
            continue
        if now is not None and task.get("retry_at"):
            _require(_time(task["retry_at"]), "malformed retry_at")
            if datetime.fromisoformat(task["retry_at"].replace("Z", "+00:00")) > now:
                continue
        return copy.deepcopy(task)
    return None


def apply_event(state: dict, event: dict, coordination: dict, *, current_main_sha: str) -> dict:
    """Pure event reducer. Persist its result through V1 GitHubStateStore.save.

    Every receipt is immutable and a duplicate event ID with identical bytes is
    a no-op. The external caller checks current main/PR/CI facts before adding
    an event; this reducer also binds every derived identity it can verify.
    """
    validate_v2(state)
    validate_state(coordination)
    _require(isinstance(event, dict) and _nonempty(event.get("event_id"))
             and _nonempty(event.get("type")) and _nonempty(event.get("task_id"))
             and _time(event.get("at")), "malformed event")
    receipt = _digest(event)
    prior = state["events"].get(event["event_id"])
    if prior is not None:
        _require(prior == receipt, "duplicate event identity has conflicting immutable content")
        return state
    _require(_sha(current_main_sha), "malformed main SHA")
    canonical = {task["id"]: task for task in coordination["tasks"]}
    task_id = event["task_id"]
    _require(task_id in canonical, "task absent from canonical queue")
    task = canonical[task_id]
    updated = copy.deepcopy(state)
    record = updated["tasks"].get(task_id)
    kind = event["type"]

    if kind == "CLAIM":
        _require(record is None and task["status"] == "READY", "duplicate claim or task not READY")
        _require(event.get("base_main_sha") == current_main_sha, "main advanced before claim")
        _require(all(_nonempty(event.get(k)) for k in
                     ("attempt_id", "request_id", "adapter", "engine", "branch")),
                 "incomplete attempt identity")
        _require(event["branch"] == safe_branch(task["owner"], task_id), "branch identity mismatch")
        _require(route_task(task, event["engine"])["status"] == "AUTOMATIC", "unsupported adapter")
        _require(event["adapter"] == ACCEPTED_RUNNERS.get(event["engine"]),
                 "engine-adapter identity mismatch")
        if ADAPTERS[event["engine"]]["budget_gate"]:
            _require(_nonempty(event.get("budget_reservation_id")), "budget reservation required")
        attempt = {k: event.get(k) for k in ("attempt_id", "request_id", "adapter", "engine",
                                              "branch", "base_main_sha", "budget_reservation_id")}
        attempt["started_at"] = event["at"]
        record = {"task_id": task_id, "owner": task["owner"], "objective": task["title"],
                  "lane": task.get("work_mode"), "fingerprint_id": task.get("fingerprint_id"),
                  "dependencies": copy.deepcopy(task["dependencies"]), "status": "CLAIMED",
                  "attempts": {event["attempt_id"]: attempt}, "active_attempt": event["attempt_id"],
                  "reviews": {}, "repairs": {}, "ci": {}, "worker_free": False}
        updated["tasks"][task_id] = record
    else:
        _require(record is not None, "task not claimed")
        _require(record["status"] != "DONE" or kind == "SUCCESSOR", "task already DONE")
        if kind != "SUCCESSOR":
            _require(current_main_sha == record["attempts"][record["active_attempt"]]["base_main_sha"],
                     "main advanced; rebase and re-review required")
        _advance_record(updated, record, task, event, kind, coordination)
    updated["events"][event["event_id"]] = receipt
    validate_v2(updated)
    return updated


def _advance_record(state: dict, r: dict, task: dict, e: dict, kind: str, coordination: dict) -> None:
    status = r["status"]
    if kind == "DISPATCH":
        _require(status == "CLAIMED" and e.get("attempt_id") == r["active_attempt"]
                 and _nonempty(e.get("dispatch_id")), "invalid dispatch")
        _require("dispatch_id" not in r, "duplicate dispatch")
        r["dispatch_id"], r["status"] = e["dispatch_id"], "DISPATCHED"
    elif kind == "RUNNING":
        _require(status == "DISPATCHED" and e.get("attempt_id") == r["active_attempt"],
                 "invalid running event")
        r["status"] = "RUNNING"
    elif kind == "WORKER_OUTCOME":
        _require(status in {"DISPATCHED", "RUNNING"} and e.get("attempt_id") == r["active_attempt"]
                 and _nonempty(e.get("result_id")) and e.get("outcome") in OUTCOMES,
                 "invalid worker outcome")
        r["worker_result"] = {k: e.get(k) for k in
                              ("result_id", "outcome", "pr_number", "head_sha", "retry_at")}
        if e["outcome"] == "PR_CREATED":
            _require(type(e.get("pr_number")) is int and e["pr_number"] > 0
                     and _sha(e.get("head_sha")), "invalid PR identity")
            r["pr_number"], r["head_sha"], r["status"] = e["pr_number"], e["head_sha"], "REVIEW_REQUIRED"
        elif e["outcome"] == "WAIT":
            _require(_time(e.get("retry_at")), "WAIT requires retry_at")
            r["status"] = "WAIT"
        else:
            r["status"] = "BLOCKED"
    elif kind == "PROVIDER_TIMEOUT":
        _require(status in {"CLAIMED", "DISPATCHED", "RUNNING"}
                 and e.get("attempt_id") == r["active_attempt"]
                 and _time(e.get("retry_at")), "invalid provider timeout")
        r["retry_at"], r["status"] = e["retry_at"], "WAIT"
    elif kind == "HEAD_CHANGED":
        _require(status in {"REVIEW_REQUIRED", "REVIEWING", "READY_FOR_INTEGRATION"}
                 and e.get("pr_number") == r.get("pr_number")
                 and _sha(e.get("head_sha")) and e["head_sha"] != r.get("head_sha"),
                 "invalid changed head")
        r["head_sha"], r["status"] = e["head_sha"], "REVIEW_REQUIRED"
    elif kind == "CI":
        _require(status in {"REVIEW_REQUIRED", "REVISION_REQUIRED"}
                 and e.get("pr_number") == r.get("pr_number")
                 and e.get("head_sha") == r.get("head_sha")
                 and e.get("conclusion") in {"success", "failure"}
                 and _nonempty(e.get("ci_id")), "CI identity or head mismatch")
        _require(e["head_sha"] not in r["ci"], "CI for head already immutable")
        r["ci"][e["head_sha"]] = {"ci_id": e["ci_id"], "conclusion": e["conclusion"],
                                   "head_sha": e["head_sha"], "at": e["at"]}
    elif kind == "REVIEW_REQUESTED":
        _require(status == "REVIEW_REQUIRED" and e.get("pr_number") == r.get("pr_number")
                 and e.get("head_sha") == r.get("head_sha")
                 and r["ci"].get(r["head_sha"], {}).get("conclusion") == "success"
                 and _nonempty(e.get("request_id")), "invalid review request")
        r["review_request_id"], r["status"] = e["request_id"], "REVIEWING"
    elif kind == "REVIEW":
        _require(status in {"REVIEW_REQUIRED", "REVIEWING", "REVISION_REQUIRED"}
                 and e.get("pr_number") == r.get("pr_number")
                 and e.get("head_sha") == r.get("head_sha")
                 and r["ci"].get(r["head_sha"], {}).get("conclusion") == "success",
                 "exact-head CI required")
        _require(_nonempty(e.get("review_id")) and set(e.get("reviewer_lanes") or []) == REVIEW_LANES
                 and e.get("outcome") in {"APPROVED", "REVISION_REQUIRED", "BLOCKED", "WAIT"}
                 and isinstance(e.get("findings"), list), "malformed independent review")
        _require(r["head_sha"] not in [v["head_sha"] for v in r["reviews"].values()],
                 "head already reviewed")
        if e["outcome"] == "REVISION_REQUIRED":
            _require(bool(e["findings"]), "repair findings missing")
        review = {k: copy.deepcopy(e[k]) for k in
                  ("review_id", "pr_number", "head_sha", "reviewer_lanes", "outcome", "findings", "at")}
        review["fingerprint"] = _digest(review)
        r["reviews"][e["review_id"]] = review
        r["status"] = ("READY_FOR_INTEGRATION" if e["outcome"] == "APPROVED"
                       else "BLOCKED" if e["outcome"] == "REVISION_REQUIRED"
                       and len(r["repairs"]) >= MAX_REPAIRS else e["outcome"])
    elif kind == "REPAIR":
        review = r["reviews"].get(e.get("review_id"))
        _require(status == "REVISION_REQUIRED" and review is not None
                 and review["outcome"] == "REVISION_REQUIRED"
                 and e.get("owner") == r["owner"] and e.get("attempt_id") == r["active_attempt"]
                 and _nonempty(e.get("repair_id")) and len(r["repairs"]) < MAX_REPAIRS,
                 "invalid or exhausted repair")
        _require(all(v["review_id"] != e["review_id"] for v in r["repairs"].values()),
                 "duplicate repair claim")
        r["repairs"][e["repair_id"]] = {"repair_id": e["repair_id"], "review_id": e["review_id"],
                                       "findings": copy.deepcopy(review["findings"]),
                                       "attempt_id": e["attempt_id"], "owner": e["owner"],
                                       "number": len(r["repairs"]) + 1, "at": e["at"]}
        r["status"] = "REPAIR"
    elif kind == "REPAIRED_HEAD":
        _require(status == "REPAIR" and e.get("repair_id") in r["repairs"]
                 and _sha(e.get("head_sha")) and e["head_sha"] != r["head_sha"]
                 and e["head_sha"] not in r["ci"], "invalid repaired head")
        r["repairs"][e["repair_id"]]["updated_head_sha"] = e["head_sha"]
        r["head_sha"], r["status"] = e["head_sha"], "REVIEW_REQUIRED"
    elif kind == "INTEGRATION":
        review = r["reviews"].get(e.get("review_id"))
        _require(status == "READY_FOR_INTEGRATION" and review is not None
                 and review["outcome"] == "APPROVED"
                 and review["head_sha"] == r["head_sha"] == e.get("head_sha")
                 and e.get("pr_number") == r["pr_number"]
                 and _nonempty(e.get("integration_id")) and _nonempty(e.get("lead"))
                 and e.get("decision") in {"INTEGRATED", "REJECTED", "DEFERRED"},
                 "invalid Lead integration decision")
        if e["decision"] == "INTEGRATED":
            _require(_sha(e.get("resulting_main_sha")), "integrated main SHA required")
        r["integration"] = {k: e.get(k) for k in ("integration_id", "review_id", "pr_number",
                                                    "head_sha", "decision", "lead",
                                                    "resulting_main_sha", "at")}
        r["status"] = "DONE" if e["decision"] == "INTEGRATED" else "BLOCKED" if e["decision"] == "REJECTED" else "WAIT"
        r["worker_free"] = e["decision"] == "INTEGRATED"
    elif kind == "SUCCESSOR":
        _require(status == "DONE" and e.get("previous_task_id") == r["task_id"]
                 and e.get("successor_task_id") == task.get("next_task")
                 and e.get("routing_decision") == "AUTOMATIC"
                 and _nonempty(e.get("deduplication_proof")), "invalid successor identity")
        by_id = {t["id"]: t for t in coordination["tasks"]}
        successor = by_id.get(e["successor_task_id"])
        _require(task["status"] == "DONE" and successor is not None and successor["status"] == "READY"
                 and route_task(successor, e.get("engine"))["status"] == "AUTOMATIC",
                 "successor not canonically ready or engine ineligible")
        _require(r["task_id"] not in state["successors"], "successor already selected")
        state["successors"][r["task_id"]] = {k: e[k] for k in
                                             ("previous_task_id", "successor_task_id", "engine",
                                              "routing_decision", "deduplication_proof", "at")}
    elif kind == "USER_ACTION_REQUIRED":
        _require(_nonempty(e.get("escalation_id")) and e.get("reason") in ESCALATIONS
                 and e.get("severity") in {"LOW", "MEDIUM", "HIGH", "CRITICAL"}
                 and e.get("scope") in {"lane", "fleet"}
                 and all(_nonempty(e.get(k)) for k in ("action", "blocked", "continuation")),
                 "malformed user action")
        _require(e["escalation_id"] not in state["escalations"], "duplicate user action")
        state["escalations"][e["escalation_id"]] = {k: e[k] for k in
                                                   ("escalation_id", "reason", "severity", "action",
                                                    "blocked", "continuation", "scope", "at")}
        r["status"] = "USER_ACTION_REQUIRED"
    else:
        raise ValueError("unsupported lifecycle event")
