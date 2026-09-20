"""Deterministic contract acceptance; all tasks and GitHub facts here are synthetic."""

import copy
from datetime import datetime, timezone

import pytest

from agents.development_orchestrator import REVIEW_LANES as V1_REVIEW_LANES, add_review_record
from agents.development_orchestrator_v2 import (
    ADAPTERS, apply_event, empty_v2, persist_event, route_task, select_task,
)
from orchestration.specialist_coordination import load_state


NOW = datetime(2026, 9, 20, tzinfo=timezone.utc)
MAIN = "a" * 40
HEAD = "b" * 40
REPAIRED = "c" * 40
MERGED = "d" * 40


def queue():
    state = load_state()
    for task in state["tasks"]:
        if task["status"] == "READY":
            task["status"], task["blockers"] = "BLOCKED", ["synthetic fixture"]
    a = copy.deepcopy(next(t for t in state["tasks"] if t["owner"] == "data-market"))
    a.update(id="V2-A", owner="data-market", status="READY", priority=0,
             blockers=[], dependencies=[], fingerprint_id=None, pr=None,
             eligible_engines=["chatgpt"], engine_claim=None,
             next_task="V2-B", work_mode="AUDIT",
             branch=state["roles"]["data-market"]["branch"])
    b = copy.deepcopy(next(t for t in state["tasks"] if t["owner"] == "signal-accuracy"))
    b.update(id="V2-B", owner="signal-accuracy", status="QUEUED", priority=1,
             blockers=[], dependencies=["V2-A"], fingerprint_id=None, pr=None,
             eligible_engines=["claude"], engine_claim=None, next_task=None, work_mode="AUDIT",
             branch=state["roles"]["signal-accuracy"]["branch"])
    state["tasks"].extend([a, b])
    return state


def event(kind, n, **fields):
    if kind == "WORKER_OUTCOME" and fields.get("outcome") == "PR_CREATED":
        fields = {"pr_repo": "rnnyrgs-web/tradingview-ai-crypto",
                  "pr_head_branch": "auto/data-market/v2-a", "pr_base_branch": "main",
                  "pr_base_main_sha": MAIN, **fields}
    return {"event_id": f"event-{n}", "type": kind, "task_id": "V2-A",
            "at": "2026-09-20T00:00:00Z", **fields}


def verdicts(outcome):
    results = {lane: "APPROVE" for lane in V1_REVIEW_LANES}
    if outcome == "REVISION_REQUIRED":
        results["claude-adversarial"] = "REJECT"
    return results


def advance(state, kind, n, **fields):
    document = {"version": 1, "reviews": {}, "review_attempts": {}, "dispatches": {}, "runs": []}
    if kind == "REVIEW":
        document = add_review_record(document, task_id="V2-A", pr_number=fields["pr_number"],
                                     head_sha=fields["head_sha"], ci_state="success",
                                     outcomes=fields["outcomes"], now=NOW)
    return apply_event(state, event(kind, n, **fields), queue(), current_main_sha=MAIN,
                       v1_document=document,
                       selection_evidence={"claimed_branches": set(), "active_prs": set(),
                                           "rejected": [], "strategy_queue": {"active_deep_candidate": None}})


def claimed():
    selected = select_task(queue(), engine="api_luna", claimed_branches=set(),
                           active_prs=set(), rejected=[], strategy_queue={"active_deep_candidate": None})
    assert selected["id"] == "V2-A"
    state = advance(empty_v2(), "CLAIM", 1, attempt_id="attempt-A", engine="api_luna",
                    adapter="github_cloud_worker", request_id="request-A", branch="auto/data-market/v2-a",
                    base_main_sha=MAIN, budget_reservation_id="reservation-A")
    return state


def test_full_lifecycle_repair_integration_and_successor_replay():
    assert route_task(queue()["tasks"][-2], "api_luna")["status"] == "AUTOMATIC"
    state = claimed()
    assert state["tasks"]["V2-A"]["status"] == "CLAIMED"
    state = advance(state, "DISPATCH", 2, attempt_id="attempt-A", dispatch_id="dispatch-A")
    state = advance(state, "RUNNING", 3, attempt_id="attempt-A")
    state = advance(state, "WORKER_OUTCOME", 4, attempt_id="attempt-A", result_id="result-A",
                    outcome="PR_CREATED", pr_number=501, head_sha=HEAD)
    state = advance(state, "CI", 5, ci_id="ci-A", pr_number=501, head_sha=HEAD, conclusion="success")
    state = advance(state, "REVIEW", 6, review_id="review-A", pr_number=501, head_sha=HEAD,
                    reviewer_lanes=list(V1_REVIEW_LANES), outcomes=verdicts("REVISION_REQUIRED"),
                    outcome="REVISION_REQUIRED",
                    findings=["synthetic bounded defect"])
    assert state["tasks"]["V2-A"]["status"] == "REVISION_REQUIRED"
    state = advance(state, "REPAIR", 7, repair_id="repair-A", review_id="review-A",
                    attempt_id="attempt-A", owner="data-market")
    state = advance(state, "REPAIRED_HEAD", 8, repair_id="repair-A", head_sha=REPAIRED)
    state = advance(state, "CI", 9, ci_id="ci-B", pr_number=501, head_sha=REPAIRED,
                    conclusion="success")
    state = advance(state, "REVIEW", 10, review_id="review-B", pr_number=501,
                    head_sha=REPAIRED, reviewer_lanes=list(V1_REVIEW_LANES),
                    outcomes=verdicts("APPROVED"), outcome="APPROVED",
                    findings=[])
    assert state["tasks"]["V2-A"]["status"] == "READY_FOR_INTEGRATION"
    state = apply_event(state, event("INTEGRATION", 11, integration_id="integration-A",
                                     review_id="review-B", pr_number=501, head_sha=REPAIRED,
                                     decision="INTEGRATED", lead="human-lead",
                                     resulting_main_sha=MERGED), queue(), current_main_sha=MERGED)
    assert state["tasks"]["V2-A"]["status"] == "DONE"
    assert state["tasks"]["V2-A"]["worker_free"] is True
    updated_queue = queue()
    updated_queue["tasks"][-2]["status"] = "DONE"
    updated_queue["tasks"][-1]["status"] = "READY"
    successor = select_task(updated_queue, engine="claude", claimed_branches=set(),
                            active_prs=set(), rejected=[], strategy_queue={"active_deep_candidate": None})
    assert successor["id"] == "V2-B"
    assert route_task(successor, "claude")["status"] == "AUTOMATIC"
    next_event = event("SUCCESSOR", 12, successor_task_id="V2-B", engine="claude",
                       previous_task_id="V2-A", routing_decision="AUTOMATIC",
                       deduplication_proof="canonical-ready-no-active-claim")
    selection = {"claimed_branches": set(), "active_prs": set(), "rejected": [],
                 "strategy_queue": {"active_deep_candidate": None}}
    blocked_queue = copy.deepcopy(updated_queue)
    blocked_queue["tasks"][-1]["blockers"] = ["synthetic blocker"]
    with pytest.raises(ValueError, match="successor"):
        apply_event(state, next_event, blocked_queue, current_main_sha=MERGED,
                    selection_evidence=selection)
    occupied = {**selection, "active_prs": {"auto/signal-accuracy/v2-b"}}
    with pytest.raises(ValueError, match="successor"):
        apply_event(state, next_event, updated_queue, current_main_sha=MERGED,
                    selection_evidence=occupied)
    state = apply_event(state, next_event, updated_queue, current_main_sha=MERGED,
                        selection_evidence=selection)
    assert apply_event(state, next_event, updated_queue, current_main_sha=MERGED,
                       selection_evidence=selection) == state
    with pytest.raises(ValueError, match="duplicate|immutable"):
        apply_event(state, {**next_event, "engine": "codex"}, updated_queue,
                    current_main_sha=MERGED)


@pytest.mark.parametrize("outcome", ["NO_CHANGE", "BLOCKED", "WAIT", "TASK_MISMATCH", "FAILED"])
def test_worker_alternative_outcomes_fail_closed(outcome):
    state = claimed()
    state = advance(state, "DISPATCH", 2, attempt_id="attempt-A", dispatch_id="dispatch-A")
    state = advance(state, "WORKER_OUTCOME", 3, attempt_id="attempt-A", result_id="result-A",
                    outcome=outcome, retry_at="2026-09-21T00:00:00Z" if outcome == "WAIT" else None)
    assert state["tasks"]["V2-A"]["status"] in {"WAIT", "BLOCKED"}
    assert state["tasks"]["V2-A"]["status"] != "DONE"


def test_failed_ci_stale_head_and_main_advance_never_approve():
    state = claimed()
    state = advance(state, "DISPATCH", 2, attempt_id="attempt-A", dispatch_id="dispatch-A")
    state = advance(state, "WORKER_OUTCOME", 3, attempt_id="attempt-A", result_id="result-A",
                    outcome="PR_CREATED", pr_number=501, head_sha=HEAD)
    state = advance(state, "CI", 4, ci_id="ci-A", pr_number=501, head_sha=HEAD, conclusion="failure")
    with pytest.raises(ValueError):
        advance(state, "REVIEW", 5, review_id="review-A", pr_number=501, head_sha=HEAD,
                reviewer_lanes=list(V1_REVIEW_LANES), outcomes=verdicts("APPROVED"),
                outcome="APPROVED", findings=[])
    with pytest.raises(ValueError):
        advance(state, "CI", 6, ci_id="ci-B", pr_number=501, head_sha=REPAIRED, conclusion="success")
    with pytest.raises(ValueError, match="main|repair"):
        apply_event(state, event("REPAIR", 7, repair_id="repair-A", review_id="review-A",
                                 attempt_id="attempt-A", owner="data-market"), queue(),
                    current_main_sha=MERGED)


def test_duplicate_claim_unsupported_route_budget_and_malformed_state():
    state = claimed()
    with pytest.raises(ValueError):
        advance(state, "CLAIM", 2, attempt_id="other", engine="api_luna",
                adapter="github_cloud_worker", request_id="other", branch="auto/data-market/v2-a",
                base_main_sha=MAIN, budget_reservation_id="reservation-B")
    assert route_task(queue()["tasks"][-2], "codex")["reason"] == "MANUAL_ADAPTER_REQUIRED"
    assert route_task(queue()["tasks"][-2], "work_astra")["reason"] == "MANUAL_ADAPTER_REQUIRED"
    assert ADAPTERS["claude-code"]["can_merge"] is False
    with pytest.raises(ValueError, match="budget"):
        advance(empty_v2(), "CLAIM", 3, attempt_id="attempt-X", engine="api_luna",
                adapter="github_cloud_worker", request_id="request-X", branch="auto/data-market/v2-a",
                base_main_sha=MAIN, budget_reservation_id=None)
    with pytest.raises(ValueError):
        advance({"version": 2, "tasks": []}, "CLAIM", 4)


def test_user_action_required_is_durable_and_lane_scoped():
    state = claimed()
    state = advance(state, "USER_ACTION_REQUIRED", 2, escalation_id="user-A",
                    reason="credential_required", severity="HIGH", action="Connect approved credential",
                    blocked="V2-A dispatch", continuation="Independent research can continue",
                    scope="lane")
    assert state["tasks"]["V2-A"]["status"] == "USER_ACTION_REQUIRED"
    assert state["escalations"]["user-A"]["scope"] == "lane"


def test_provider_timeout_and_duplicate_delivery_do_not_dispatch_again():
    state = claimed()
    dispatched = advance(state, "DISPATCH", 2, attempt_id="attempt-A", dispatch_id="dispatch-A")
    assert advance(dispatched, "DISPATCH", 2, attempt_id="attempt-A", dispatch_id="dispatch-A") == dispatched
    timed_out = advance(dispatched, "PROVIDER_TIMEOUT", 3, attempt_id="attempt-A",
                        retry_at="2026-09-21T00:00:00Z")
    assert timed_out["tasks"]["V2-A"]["status"] == "WAIT"
    with pytest.raises(ValueError):
        advance(timed_out, "DISPATCH", 4, attempt_id="attempt-A", dispatch_id="dispatch-B")


def test_changed_head_invalidates_exact_head_approval():
    state = claimed()
    state = advance(state, "DISPATCH", 2, attempt_id="attempt-A", dispatch_id="dispatch-A")
    state = advance(state, "WORKER_OUTCOME", 3, attempt_id="attempt-A", result_id="result-A",
                    outcome="PR_CREATED", pr_number=501, head_sha=HEAD)
    state = advance(state, "CI", 4, ci_id="ci-A", pr_number=501, head_sha=HEAD, conclusion="success")
    state = advance(state, "REVIEW_REQUESTED", 5, request_id="review-request-A",
                    pr_number=501, head_sha=HEAD)
    assert state["tasks"]["V2-A"]["status"] == "REVIEWING"
    state = advance(state, "REVIEW", 6, review_id="review-A", pr_number=501, head_sha=HEAD,
                    reviewer_lanes=list(V1_REVIEW_LANES), outcomes=verdicts("APPROVED"),
                    outcome="APPROVED", findings=[])
    state = advance(state, "HEAD_CHANGED", 7, pr_number=501, head_sha=REPAIRED)
    assert state["tasks"]["V2-A"]["status"] == "REVIEW_REQUIRED"
    with pytest.raises(ValueError):
        advance(state, "INTEGRATION", 8, integration_id="integration-A", review_id="review-A",
                pr_number=501, head_sha=HEAD, decision="INTEGRATED", lead="human-lead",
                resulting_main_sha=MERGED)


def test_repair_limit_blocks_third_revision():
    state = claimed()
    state = advance(state, "DISPATCH", 2, attempt_id="attempt-A", dispatch_id="dispatch-A")
    state = advance(state, "WORKER_OUTCOME", 3, attempt_id="attempt-A", result_id="result-A",
                    outcome="PR_CREATED", pr_number=501, head_sha=HEAD)
    for number, head, next_head in [(4, HEAD, REPAIRED), (9, REPAIRED, "e" * 40)]:
        state = advance(state, "CI", number, ci_id=f"ci-{number}", pr_number=501,
                        head_sha=head, conclusion="success")
        state = advance(state, "REVIEW", number + 1, review_id=f"review-{number}",
                        pr_number=501, head_sha=head, reviewer_lanes=list(V1_REVIEW_LANES),
                        outcomes=verdicts("REVISION_REQUIRED"),
                        outcome="REVISION_REQUIRED", findings=["bounded synthetic finding"])
        state = advance(state, "REPAIR", number + 2, repair_id=f"repair-{number}",
                        review_id=f"review-{number}", attempt_id="attempt-A", owner="data-market")
        state = advance(state, "REPAIRED_HEAD", number + 3, repair_id=f"repair-{number}",
                        head_sha=next_head)
    state = advance(state, "CI", 14, ci_id="ci-final", pr_number=501,
                    head_sha="e" * 40, conclusion="success")
    state = advance(state, "REVIEW", 15, review_id="review-final", pr_number=501,
                    head_sha="e" * 40, reviewer_lanes=list(V1_REVIEW_LANES),
                    outcomes=verdicts("REVISION_REQUIRED"),
                    outcome="REVISION_REQUIRED", findings=["still broken"])
    assert state["tasks"]["V2-A"]["status"] == "BLOCKED"
    with pytest.raises(ValueError):
        advance(state, "REPAIR", 16, repair_id="repair-third", review_id="review-final",
                attempt_id="attempt-A", owner="data-market")


def test_cas_store_replay_restart_and_main_advance():
    class Store:
        def __init__(self):
            self.value = {"version": 1, "reviews": {}, "dispatches": {},
                          "review_attempts": {}, "runs": []}
            self.version = 0
            self.loaded = None

        def load(self):
            self.loaded = self.version
            return copy.deepcopy(self.value)

        def save(self, value):
            if self.loaded != self.version:
                raise RuntimeError("CAS conflict")
            self.value = copy.deepcopy(value)
            self.version += 1

    store = Store()
    claim = event("CLAIM", 1, attempt_id="attempt-A", engine="api_luna",
                  adapter="github_cloud_worker", request_id="request-A",
                  branch="auto/data-market/v2-a", base_main_sha=MAIN,
                  budget_reservation_id="reservation-A")
    selection = {"claimed_branches": set(), "active_prs": set(), "rejected": [],
                 "strategy_queue": {"active_deep_candidate": None}}
    first = persist_event(store, claim, queue(), MAIN, lambda: MAIN,
                          selection_evidence=selection)
    assert first["v2"]["tasks"]["V2-A"]["status"] == "CLAIMED"
    assert persist_event(store, claim, queue(), MAIN, lambda: MAIN,
                         selection_evidence=selection) == first
    assert store.version == 1
    with pytest.raises(ValueError, match="main advanced"):
        persist_event(store, event("DISPATCH", 2, attempt_id="attempt-A",
                                   dispatch_id="dispatch-A"), queue(), MAIN, lambda: MERGED)
    stale = store.load()
    store.version += 1
    with pytest.raises(RuntimeError, match="CAS conflict"):
        store.save(stale)


def test_corrupt_durable_identity_fails_closed_on_replay():
    state = claimed()
    state["tasks"]["V2-A"]["attempts"]["attempt-A"]["base_main_sha"] = "bad"
    with pytest.raises(ValueError, match="attempt"):
        advance(state, "DISPATCH", 2, attempt_id="attempt-A", dispatch_id="dispatch-A")


def test_no_valid_successor_waits_and_rejected_fingerprint_is_skipped():
    canonical = queue()
    canonical["tasks"][-2]["fingerprint_id"] = "SYNTHETIC-REJECTED"
    assert select_task(canonical, engine="api_luna", claimed_branches=set(),
                       active_prs=set(),
                       rejected=[{"fingerprint_id": "SYNTHETIC-REJECTED",
                                  "do_not_resubmit_same_fingerprint": True}],
                       strategy_queue={"active_deep_candidate": None}) is None
    canonical["tasks"][-2]["fingerprint_id"] = None
    assert select_task(canonical, engine="api_luna", claimed_branches={"auto/data-market/v2-a"},
                       active_prs=set(), rejected=[],
                       strategy_queue={"active_deep_candidate": None}) is None
    canonical["tasks"][-2]["retry_at"] = "2026-09-21T00:00:00Z"
    assert select_task(canonical, engine="api_luna", claimed_branches=set(), active_prs=set(),
                       rejected=[], strategy_queue={"active_deep_candidate": None}) is None


def test_contract_grants_no_autonomous_merge_or_trade_authority():
    assert all(not item["can_merge"] for key, item in ADAPTERS.items() if key != "lead")
    assert ADAPTERS["lead"]["programmatic_dispatch"] is False
    assert route_task(queue()["tasks"][-2], "api_terra")["reason"] == "MANUAL_ADAPTER_REQUIRED"
    assert route_task(queue()["tasks"][-2], "api_sol")["reason"] == "MANUAL_ADAPTER_REQUIRED"
    assert not any("trade" in key or "promotion" in key or "broker" in key
                   for key in empty_v2())


def test_engine_cannot_claim_another_engines_adapter():
    with pytest.raises(ValueError, match="adapter"):
        advance(empty_v2(), "CLAIM", 1, attempt_id="attempt-A", engine="api_luna",
                adapter="claude_runner", request_id="request-A",
                branch="auto/data-market/v2-a", base_main_sha=MAIN,
                budget_reservation_id="reservation-A")


def test_claim_rechecks_active_branch_and_canonical_selection():
    claim = event("CLAIM", 1, attempt_id="attempt-A", engine="api_luna",
                  adapter="github_cloud_worker", request_id="request-A",
                  branch="auto/data-market/v2-a", base_main_sha=MAIN,
                  budget_reservation_id="reservation-A")
    with pytest.raises(ValueError, match="selection|claimed"):
        apply_event(empty_v2(), claim, queue(), current_main_sha=MAIN,
                    selection_evidence={"claimed_branches": {"auto/data-market/v2-a"},
                                        "active_prs": set(), "rejected": [],
                                        "strategy_queue": {"active_deep_candidate": None}})


def test_wait_retries_once_with_new_immutable_attempt_after_retry_at():
    state = claimed()
    state = advance(state, "DISPATCH", 2, attempt_id="attempt-A", dispatch_id="dispatch-A")
    state = advance(state, "PROVIDER_TIMEOUT", 3, attempt_id="attempt-A",
                    retry_at="2026-09-21T00:00:00Z")
    with pytest.raises(ValueError, match="retry"):
        advance(state, "RETRY", 4, attempt_id="attempt-B", request_id="request-B",
                budget_reservation_id="reservation-B", base_main_sha=MAIN)
    state = advance(state, "RETRY", 4, at="2026-09-22T00:00:00Z",
                    attempt_id="attempt-B", request_id="request-B",
                    budget_reservation_id="reservation-B", base_main_sha=MAIN)
    assert state["tasks"]["V2-A"]["status"] == "CLAIMED"
    assert set(state["tasks"]["V2-A"]["attempts"]) == {"attempt-A", "attempt-B"}
    state = advance(state, "DISPATCH", 5, attempt_id="attempt-B", dispatch_id="dispatch-B")
    state = advance(state, "PROVIDER_TIMEOUT", 6, attempt_id="attempt-B",
                    retry_at="2026-09-23T00:00:00Z")
    assert state["tasks"]["V2-A"]["status"] == "BLOCKED"


def test_rebase_after_main_advances_creates_new_attempt():
    state = claimed()
    rebased = apply_event(state, event("REBASE", 2, attempt_id="attempt-B",
                                       request_id="request-B", base_main_sha=MERGED,
                                       budget_reservation_id="reservation-B"),
                          queue(), current_main_sha=MERGED)
    assert rebased["tasks"]["V2-A"]["attempts"]["attempt-A"]["base_main_sha"] == MAIN
    assert rebased["tasks"]["V2-A"]["attempts"]["attempt-B"]["base_main_sha"] == MERGED


def test_worker_pr_branch_and_review_lane_receipts_are_bound():
    state = claimed()
    state = advance(state, "DISPATCH", 2, attempt_id="attempt-A", dispatch_id="dispatch-A")
    with pytest.raises(ValueError, match="PR"):
        advance(state, "WORKER_OUTCOME", 3, attempt_id="attempt-A", result_id="result-A",
                outcome="PR_CREATED", pr_number=501, head_sha=HEAD,
                pr_head_branch="unrelated-branch")
    state = advance(state, "WORKER_OUTCOME", 3, attempt_id="attempt-A", result_id="result-A",
                    outcome="PR_CREATED", pr_number=501, head_sha=HEAD)
    state = advance(state, "CI", 4, ci_id="ci-A", pr_number=501, head_sha=HEAD,
                    conclusion="success")
    wrong = verdicts("APPROVED")
    del wrong["claude-adversarial"]
    with pytest.raises(ValueError, match="review"):
        advance(state, "REVIEW", 5, review_id="review-A", pr_number=501, head_sha=HEAD,
                reviewer_lanes=list(V1_REVIEW_LANES), outcomes=wrong,
                outcome="APPROVED", findings=[])


def test_corrupt_persisted_pr_or_review_receipt_fails_closed():
    state = claimed()
    state = advance(state, "DISPATCH", 2, attempt_id="attempt-A", dispatch_id="dispatch-A")
    state = advance(state, "WORKER_OUTCOME", 3, attempt_id="attempt-A", result_id="result-A",
                    outcome="PR_CREATED", pr_number=501, head_sha=HEAD)
    corrupt = copy.deepcopy(state)
    corrupt["tasks"]["V2-A"]["pr_identity"]["pr_repo"] = "unrelated/repo"
    with pytest.raises(ValueError, match="PR"):
        advance(corrupt, "CI", 4, ci_id="ci-A", pr_number=501, head_sha=HEAD,
                conclusion="success")
    state = advance(state, "CI", 4, ci_id="ci-A", pr_number=501, head_sha=HEAD,
                    conclusion="success")
    state = advance(state, "REVIEW", 5, review_id="review-A", pr_number=501,
                    head_sha=HEAD, reviewer_lanes=list(V1_REVIEW_LANES),
                    outcomes=verdicts("APPROVED"), outcome="APPROVED", findings=[])
    state["tasks"]["V2-A"]["reviews"]["review-A"]["outcomes"]["lead"] = "REJECT"
    with pytest.raises(ValueError, match="review"):
        advance(state, "HEAD_CHANGED", 6, pr_number=501, head_sha=REPAIRED)


def test_rebase_open_approved_pr_requires_new_ci_and_review():
    state = claimed()
    state = advance(state, "DISPATCH", 2, attempt_id="attempt-A", dispatch_id="dispatch-A")
    state = advance(state, "WORKER_OUTCOME", 3, attempt_id="attempt-A", result_id="result-A",
                    outcome="PR_CREATED", pr_number=501, head_sha=HEAD)
    state = advance(state, "CI", 4, ci_id="ci-A", pr_number=501, head_sha=HEAD,
                    conclusion="success")
    state = advance(state, "REVIEW", 5, review_id="review-A", pr_number=501,
                    head_sha=HEAD, reviewer_lanes=list(V1_REVIEW_LANES),
                    outcomes=verdicts("APPROVED"), outcome="APPROVED", findings=[])
    state = apply_event(state, event("REBASE", 6, attempt_id="attempt-B",
                                     request_id="request-B", base_main_sha=MERGED,
                                     budget_reservation_id="reservation-B", head_sha=REPAIRED),
                        queue(), current_main_sha=MERGED)
    assert state["tasks"]["V2-A"]["status"] == "REVIEW_REQUIRED"
    assert state["tasks"]["V2-A"]["pr_identity"]["pr_base_main_sha"] == MERGED
    with pytest.raises(ValueError, match="CI"):
        apply_event(state, event("REVIEW", 7, review_id="review-B", pr_number=501,
                                 head_sha=REPAIRED, reviewer_lanes=list(V1_REVIEW_LANES),
                                 outcomes=verdicts("APPROVED"), outcome="APPROVED",
                                 findings=[]), queue(), current_main_sha=MERGED)


def test_review_requires_matching_v1_receipt():
    state = claimed()
    state = advance(state, "DISPATCH", 2, attempt_id="attempt-A", dispatch_id="dispatch-A")
    state = advance(state, "WORKER_OUTCOME", 3, attempt_id="attempt-A", result_id="result-A",
                    outcome="PR_CREATED", pr_number=501, head_sha=HEAD)
    state = advance(state, "CI", 4, ci_id="ci-A", pr_number=501, head_sha=HEAD,
                    conclusion="success")
    review = event("REVIEW", 5, review_id="review-A", pr_number=501, head_sha=HEAD,
                   reviewer_lanes=list(V1_REVIEW_LANES), outcomes=verdicts("APPROVED"),
                   outcome="APPROVED", findings=[])
    with pytest.raises(ValueError, match="V1 review receipt"):
        apply_event(state, review, queue(), current_main_sha=MAIN)
    reject = {"version": 1, "reviews": {}, "review_attempts": {}, "dispatches": {}, "runs": []}
    reject = add_review_record(reject, task_id="V2-A", pr_number=501, head_sha=HEAD,
                               ci_state="success", outcomes=verdicts("REVISION_REQUIRED"),
                               now=NOW)
    with pytest.raises(ValueError, match="V1 review receipt"):
        apply_event(state, review, queue(), current_main_sha=MAIN, v1_document=reject)


@pytest.mark.parametrize("field,value", [("branch", "auto/data-market/other"),
                                          ("adapter", "claude_runner"),
                                          ("request_id", "forged")])
def test_persisted_attempt_identity_is_immutable(field, value):
    state = claimed()
    state["tasks"]["V2-A"]["attempts"]["attempt-A"][field] = value
    with pytest.raises(ValueError, match="attempt"):
        advance(state, "DISPATCH", 2, attempt_id="attempt-A", dispatch_id="dispatch-A")


def test_persisted_repair_findings_and_active_identity_are_immutable():
    state = claimed()
    state = advance(state, "DISPATCH", 2, attempt_id="attempt-A", dispatch_id="dispatch-A")
    state = advance(state, "WORKER_OUTCOME", 3, attempt_id="attempt-A", result_id="result-A",
                    outcome="PR_CREATED", pr_number=501, head_sha=HEAD)
    state = advance(state, "CI", 4, ci_id="ci-A", pr_number=501, head_sha=HEAD,
                    conclusion="success")
    state = advance(state, "REVIEW", 5, review_id="review-A", pr_number=501,
                    head_sha=HEAD, reviewer_lanes=list(V1_REVIEW_LANES),
                    outcomes=verdicts("REVISION_REQUIRED"), outcome="REVISION_REQUIRED",
                    findings=["real finding"])
    state = advance(state, "REPAIR", 6, repair_id="repair-A", review_id="review-A",
                    attempt_id="attempt-A", owner="data-market")
    for field, value in [("findings", ["forged"]), ("attempt_id", "fake"), ("number", 2)]:
        corrupt = copy.deepcopy(state)
        corrupt["tasks"]["V2-A"]["repairs"]["repair-A"][field] = value
        with pytest.raises(ValueError, match="repair"):
            advance(corrupt, "REPAIRED_HEAD", 7, repair_id="repair-A", head_sha=REPAIRED)


def test_rebase_cannot_reuse_old_head_or_overlap_running_worker():
    state = claimed()
    running = advance(state, "DISPATCH", 2, attempt_id="attempt-A", dispatch_id="dispatch-A")
    running = advance(running, "RUNNING", 3, attempt_id="attempt-A")
    with pytest.raises(ValueError, match="rebase|worker"):
        apply_event(running, event("REBASE", 4, attempt_id="attempt-B", request_id="request-B",
                                   base_main_sha=MERGED, budget_reservation_id="reservation-B"),
                    queue(), current_main_sha=MERGED)
    state = advance(running, "WORKER_OUTCOME", 4, attempt_id="attempt-A", result_id="result-A",
                    outcome="PR_CREATED", pr_number=501, head_sha=HEAD)
    state = advance(state, "CI", 5, ci_id="ci-A", pr_number=501, head_sha=HEAD,
                    conclusion="success")
    state = advance(state, "HEAD_CHANGED", 6, pr_number=501, head_sha=REPAIRED)
    with pytest.raises(ValueError, match="head|CI"):
        apply_event(state, event("REBASE", 7, attempt_id="attempt-B", request_id="request-B",
                                 base_main_sha=MERGED, budget_reservation_id="reservation-B",
                                 head_sha=HEAD), queue(), current_main_sha=MERGED)


def test_repaired_head_must_match_current_repair():
    state = claimed()
    state = advance(state, "DISPATCH", 2, attempt_id="attempt-A", dispatch_id="dispatch-A")
    state = advance(state, "WORKER_OUTCOME", 3, attempt_id="attempt-A", result_id="result-A",
                    outcome="PR_CREATED", pr_number=501, head_sha=HEAD)
    for n, head, next_head in [(4, HEAD, REPAIRED), (9, REPAIRED, "e" * 40)]:
        state = advance(state, "CI", n, ci_id=f"ci-{n}", pr_number=501,
                        head_sha=head, conclusion="success")
        state = advance(state, "REVIEW", n + 1, review_id=f"review-{n}", pr_number=501,
                        head_sha=head, reviewer_lanes=list(V1_REVIEW_LANES),
                        outcomes=verdicts("REVISION_REQUIRED"), outcome="REVISION_REQUIRED",
                        findings=["finding"])
        state = advance(state, "REPAIR", n + 2, repair_id=f"repair-{n}",
                        review_id=f"review-{n}", attempt_id="attempt-A", owner="data-market")
        if n == 9:
            with pytest.raises(ValueError, match="repair"):
                advance(state, "REPAIRED_HEAD", n + 3, repair_id="repair-4", head_sha=next_head)
        state = advance(state, "REPAIRED_HEAD", n + 3,
                        repair_id=f"repair-{n}", head_sha=next_head)


def test_review_wait_and_deferred_integration_resume_at_retry_time():
    state = claimed()
    state = advance(state, "DISPATCH", 2, attempt_id="attempt-A", dispatch_id="dispatch-A")
    state = advance(state, "WORKER_OUTCOME", 3, attempt_id="attempt-A", result_id="result-A",
                    outcome="PR_CREATED", pr_number=501, head_sha=HEAD)
    state = advance(state, "CI", 4, ci_id="ci-A", pr_number=501, head_sha=HEAD,
                    conclusion="success")
    state = advance(state, "REVIEW_WAIT", 5, pr_number=501, head_sha=HEAD,
                    retry_at="2026-09-21T00:00:00Z")
    assert state["tasks"]["V2-A"]["status"] == "WAIT"
    with pytest.raises(ValueError, match="resume"):
        advance(state, "RESUME", 6, phase="review")
    state = advance(state, "RESUME", 6, at="2026-09-22T00:00:00Z", phase="review")
    assert state["tasks"]["V2-A"]["status"] == "REVIEW_REQUIRED"
    state = advance(state, "REVIEW", 7, review_id="review-A", pr_number=501,
                    head_sha=HEAD, reviewer_lanes=list(V1_REVIEW_LANES),
                    outcomes=verdicts("APPROVED"), outcome="APPROVED", findings=[])
    state = advance(state, "INTEGRATION", 8, integration_id="integration-A",
                    review_id="review-A", pr_number=501, head_sha=HEAD,
                    decision="DEFERRED", lead="human-lead",
                    retry_at="2026-09-23T00:00:00Z")
    assert state["tasks"]["V2-A"]["status"] == "WAIT"
    state = advance(state, "RESUME", 9, at="2026-09-24T00:00:00Z", phase="integration")
    assert state["tasks"]["V2-A"]["status"] == "READY_FOR_INTEGRATION"


def test_provider_wait_can_retry_on_new_main_after_due_time():
    state = claimed()
    state = advance(state, "DISPATCH", 2, attempt_id="attempt-A", dispatch_id="dispatch-A")
    state = advance(state, "PROVIDER_TIMEOUT", 3, attempt_id="attempt-A",
                    retry_at="2026-09-21T00:00:00Z")
    state = apply_event(state, event("RETRY", 4, at="2026-09-22T00:00:00Z",
                                     attempt_id="attempt-B", request_id="request-B",
                                     budget_reservation_id="reservation-B",
                                     base_main_sha=MERGED), queue(), current_main_sha=MERGED)
    assert state["tasks"]["V2-A"]["attempts"]["attempt-B"]["base_main_sha"] == MERGED


def test_rebase_after_rejected_review_requires_counted_repair():
    state = claimed()
    state = advance(state, "DISPATCH", 2, attempt_id="attempt-A", dispatch_id="dispatch-A")
    state = advance(state, "WORKER_OUTCOME", 3, attempt_id="attempt-A", result_id="result-A",
                    outcome="PR_CREATED", pr_number=501, head_sha=HEAD)
    state = advance(state, "CI", 4, ci_id="ci-A", pr_number=501, head_sha=HEAD,
                    conclusion="success")
    state = advance(state, "REVIEW", 5, review_id="review-A", pr_number=501,
                    head_sha=HEAD, reviewer_lanes=list(V1_REVIEW_LANES),
                    outcomes=verdicts("REVISION_REQUIRED"), outcome="REVISION_REQUIRED",
                    findings=["must repair"])
    rebase = event("REBASE", 6, attempt_id="attempt-B", request_id="request-B",
                   base_main_sha=MERGED, budget_reservation_id="reservation-B",
                   head_sha=REPAIRED)
    with pytest.raises(ValueError, match="rebase"):
        apply_event(state, rebase, queue(), current_main_sha=MERGED)
    state = apply_event(state, event("REPAIR", 7, repair_id="repair-A", review_id="review-A",
                                     attempt_id="attempt-A", owner="data-market"),
                        queue(), current_main_sha=MERGED)
    with pytest.raises(ValueError, match="repair"):
        apply_event(state, rebase, queue(), current_main_sha=MERGED)
    state = apply_event(state, {**rebase, "repair_id": "repair-A"}, queue(),
                        current_main_sha=MERGED)
    assert state["tasks"]["V2-A"]["repairs"]["repair-A"]["updated_head_sha"] == REPAIRED
    assert state["tasks"]["V2-A"]["status"] == "REVIEW_REQUIRED"
