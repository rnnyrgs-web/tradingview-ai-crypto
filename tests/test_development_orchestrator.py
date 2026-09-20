"""Regression coverage for the bounded development orchestration loop."""

from __future__ import annotations

import copy
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from agents.development_orchestrator import (
    REVIEW_LANES,
    Lifecycle,
    add_review_record,
    reconcile_candidate,
    review_identity,
    parse_existing_lead_review,
    parse_lead_execution_issue,
    run_existing_review_cycle,
    select_successor,
    verify_dispatch_task,
)
from orchestration.specialist_coordination import load_state


NOW = datetime(2026, 9, 19, 16, 0, tzinfo=timezone.utc)
HEAD = "a" * 40
NEW_HEAD = "b" * 40


def _ready_task(coordination: dict, *, role: str = "data-market") -> dict:
    task = copy.deepcopy(next(row for row in coordination["tasks"] if row["owner"] == role))
    task.update(id="COORD-TEST-ORCH-001", status="READY", priority=0,
                dependencies=[], blockers=[], fingerprint_id=None, pr=None,
                eligible_engines=["chatgpt"], engine_claim=None, work_mode="AUDIT")
    task.pop("completion_evidence", None)
    coordination["tasks"].append(task)
    return task


def _idle_coordination() -> dict:
    coordination = load_state()
    for task in coordination["tasks"]:
        if task["status"] == "READY":
            task["status"] = "BLOCKED"
            task["blockers"] = ["test-only idle queue"]
    return coordination


def _pr(head: str = HEAD) -> dict:
    return {"number": 501, "state": "open", "merged": False,
            "head": {"sha": head, "ref": "auto/data-market/coord-test-orch-001",
                     "repo": {"full_name": "rnnyrgs-web/tradingview-ai-crypto"}},
            "base": {"ref": "main"}, "user": {"login": "author"},
            "updated_at": "2026-09-19T15:55:00Z"}


def _ci(head: str = HEAD, conclusion: str = "success") -> list[dict]:
    return [{"head_sha": head, "status": "completed", "conclusion": conclusion,
             "name": "Security and Reliability"}]


def _approved_record(task_id: str, head: str = HEAD) -> dict:
    state = {"version": 1, "reviews": {}, "dispatches": {}, "runs": []}
    state = add_review_record(state, task_id=task_id, pr_number=501, head_sha=head,
                              ci_state="success", outcomes={lane: "APPROVE" for lane in REVIEW_LANES},
                              now=NOW)
    return next(iter(state["reviews"].values()))


def test_repeated_completion_uses_durable_exact_head_review_once():
    record = _approved_record("COORD-TEST-ORCH-001")
    task = {"id": "COORD-TEST-ORCH-001", "status": "PR_OPEN"}
    first = reconcile_candidate(task, _pr(), _ci(), record, NOW)
    second = reconcile_candidate(task, _pr(), _ci(), record, NOW)
    assert first == second
    assert first.lifecycle is Lifecycle.READY_FOR_INTEGRATION
    assert first.needs_review is False


def test_changed_head_invalidates_old_approval():
    task = {"id": "COORD-TEST-ORCH-001", "status": "PR_OPEN"}
    decision = reconcile_candidate(task, _pr(NEW_HEAD), _ci(NEW_HEAD),
                                   _approved_record(task["id"]), NOW)
    assert decision.lifecycle is Lifecycle.AWAITING_REVIEW
    assert decision.needs_review is True
    assert decision.reason == "HEAD_CHANGED"


def test_failed_ci_never_becomes_integration_ready():
    task = {"id": "COORD-TEST-ORCH-001", "status": "PR_OPEN"}
    decision = reconcile_candidate(task, _pr(), _ci(conclusion="failure"),
                                   _approved_record(task["id"]), NOW)
    assert decision.lifecycle is Lifecycle.REVISION_REQUIRED
    assert decision.needs_review is False


def test_missing_pending_and_stale_ci_fail_closed():
    task = {"id": "COORD-TEST-ORCH-001", "status": "PR_OPEN"}
    assert reconcile_candidate(task, _pr(), [], None, NOW).lifecycle is Lifecycle.RUNNING
    assert reconcile_candidate(task, _pr(), _ci(NEW_HEAD), None, NOW).lifecycle is Lifecycle.RUNNING
    old = _pr()
    old["updated_at"] = (NOW - timedelta(days=8)).isoformat()
    assert reconcile_candidate(task, old, [], None, NOW).lifecycle is Lifecycle.BLOCKED


def test_malformed_pr_and_review_fail_closed():
    task = {"id": "COORD-TEST-ORCH-001", "status": "PR_OPEN"}
    assert reconcile_candidate(task, {}, _ci(), None, NOW).lifecycle is Lifecycle.BLOCKED
    bad_review = _approved_record(task["id"])
    bad_review["outcomes"].pop("security")
    assert reconcile_candidate(task, _pr(), _ci(), bad_review, NOW).lifecycle is Lifecycle.BLOCKED


def test_review_record_identity_is_idempotent_and_contains_required_fields():
    state = {"version": 1, "reviews": {}, "dispatches": {}, "runs": []}
    outcomes = {lane: "APPROVE" for lane in REVIEW_LANES}
    first = add_review_record(state, task_id="COORD-TEST-ORCH-001", pr_number=501,
                              head_sha=HEAD, ci_state="success", outcomes=outcomes, now=NOW)
    second = add_review_record(first, task_id="COORD-TEST-ORCH-001", pr_number=501,
                               head_sha=HEAD, ci_state="success", outcomes=outcomes, now=NOW)
    assert first == second
    key = review_identity("COORD-TEST-ORCH-001", 501, HEAD)
    assert first["reviews"][key] == {
        "fingerprint": key, "task_id": "COORD-TEST-ORCH-001", "pr_number": 501,
        "head_sha": HEAD, "reviewer_lanes": list(REVIEW_LANES),
        "outcomes": outcomes, "outcome": "APPROVE", "ci_state": "success",
        "reviewed_at": "2026-09-19T16:00:00Z",
    }


def _existing_review_issue(head: str = HEAD, branch: str = "auto/data-market/coord-test-orch-001") -> dict:
    body = (f"Candidate branch: `{branch}`\n"
            f"Exact reviewed SHA: `{head}`\n\n"
            "Security and Reliability: PASS on exact candidate SHA.\n\n"
            "Autonomous Security review:\n```json\n{\"approve\":true,\"risk\":\"low\"}\n```\n"
            "Autonomous Lead review:\n```json\n{\"approve\":true,\"risk\":\"low\"}\n```\n"
            "Independent Claude adversarial review:\n```json\n{\"approve\":true,\"risk\":\"low\",\"falsification_findings\":{\"scope\":\"none\"}}\n```\n")
    return {"title": f"autonomous-review: {head}", "body": body,
            "user": {"login": "github-actions[bot]"}, "state": "open"}


def test_existing_three_lane_review_issue_requires_exact_head_and_bot_provenance():
    issue = _existing_review_issue()
    branch = "auto/data-market/coord-test-orch-001"
    assert parse_existing_lead_review(issue, head_sha=HEAD, branch=branch) == {
        lane: "APPROVE" for lane in REVIEW_LANES
    }
    assert parse_existing_lead_review(issue, head_sha=NEW_HEAD, branch=branch) is None
    issue["user"]["login"] = "untrusted-user"
    assert parse_existing_lead_review(issue, head_sha=HEAD, branch=branch) is None


def _lead_attempt_issue(status: str = "REJECTED", head: str = HEAD,
                        branch: str = "auto/data-market/coord-test-orch-001") -> dict:
    body = (f"Candidate branch: `{branch}`\nExact reviewed SHA: `{head}`\n"
            f"Workflow run: `91`\nWorkflow main SHA: `{'c' * 40}`\nOutcome: `{status}`\n")
    if status == "REJECTED":
        body += ("\nAutonomous Security review:\n```json\n{\"approve\":true,\"risk\":\"low\"}\n```\n"
                 "\nAutonomous Lead review:\n```json\n{\"approve\":false,\"risk\":\"high\"}\n```\n"
                 "\nIndependent Claude adversarial review:\n```json\n{\"approve\":true,\"risk\":\"low\"}\n```\n")
    return {"title": f"autonomous-review-attempt: {head} run=91", "body": body,
            "user": {"login": "github-actions[bot]"}, "state": "open"}


def test_lead_attempt_receipt_binds_bot_branch_head_run_and_three_lanes():
    issue = _lead_attempt_issue()
    assert parse_lead_execution_issue(issue, head_sha=HEAD,
                                      branch="auto/data-market/coord-test-orch-001") == {
        "status": "REJECTED", "run_id": 91, "main_sha": "c" * 40,
        "outcomes": {"security": "APPROVE", "lead": "REJECT", "claude-adversarial": "APPROVE"}}
    assert parse_lead_execution_issue(issue, head_sha=NEW_HEAD,
                                      branch="auto/data-market/coord-test-orch-001") is None
    issue["user"]["login"] = "untrusted-user"
    assert parse_lead_execution_issue(issue, head_sha=HEAD,
                                      branch="auto/data-market/coord-test-orch-001") is None


def test_duplicate_claim_is_rejected():
    coordination = load_state()
    task = _ready_task(coordination)
    decision = select_successor(coordination, _policy(), _config(),
                                claimed_branches={"auto/data-market/coord-test-orch-001"},
                                dispatches={}, budget_allowed=True)
    assert decision.run is False
    assert decision.reason == "TASK_ALREADY_CLAIMED"
    assert decision.task_id == task["id"]


def test_unsupported_engine_route_returns_wait():
    coordination = _idle_coordination()
    _ready_task(coordination, role="testing-security")
    decision = select_successor(coordination, _policy(), _config(),
                                claimed_branches=set(), dispatches={}, budget_allowed=True)
    assert decision.run is False
    assert decision.reason == "MANUAL_ADAPTER_REQUIRED"


def test_blocked_and_ineligible_tasks_do_not_dispatch():
    coordination = _idle_coordination()
    blocked = _ready_task(coordination)
    blocked["status"] = "BLOCKED"
    blocked["blockers"] = ["evidence missing"]
    assert select_successor(coordination, _policy(), _config(), set(), {}, True).reason == "NO_READY_TASK"
    blocked["status"] = "READY"
    blocked["blockers"] = []
    blocked["eligible_engines"] = ["claude-code"]
    assert select_successor(coordination, _policy(), _config(), set(), {}, True).reason == "ENGINE_INELIGIBLE"


def test_shared_budget_denial_prevents_paid_dispatch():
    coordination = load_state()
    _ready_task(coordination)
    decision = select_successor(coordination, _policy(), _config(), set(), {}, False)
    assert decision.run is False
    assert decision.reason == "SHARED_BUDGET_DENIED"


def test_exact_task_id_is_sent_and_verified_by_receiving_runner():
    coordination = load_state()
    task = _ready_task(coordination)
    decision = select_successor(coordination, _policy(), _config(), set(), {}, True)
    assert decision.run is True
    assert decision.workflow == "autonomous_cloud_specialist.yml"
    assert decision.inputs == {"task_id": task["id"]}
    verify_dispatch_task(task["id"], task)
    with pytest.raises(ValueError, match="task ID mismatch"):
        verify_dispatch_task("COORD-WRONG-001", task)


def test_no_clean_successor_returns_wait_and_no_merge_action():
    decision = select_successor(_idle_coordination(), _policy(), _config(), set(), {}, True)
    assert decision.run is False
    assert decision.reason == "NO_READY_TASK"
    assert not hasattr(decision, "merge")


def test_orchestrator_workflow_has_no_merge_or_trading_step():
    workflow = Path(".github/workflows/development_orchestrator.yml").read_text(encoding="utf-8")
    assert "python -m agents.development_orchestrator_runtime" in workflow
    for forbidden in ("gh pr merge", "enable-auto-merge", "git push origin main",
                      "place_order", "trade_authority"):
        assert forbidden not in workflow


def test_existing_lead_workflow_records_exact_review_start_and_terminal_outcome():
    lead = Path(".github/workflows/autonomous_lead.yml").read_text(encoding="utf-8")
    cloud = Path(".github/workflows/autonomous_cloud_specialist.yml").read_text(encoding="utf-8")
    assert "autonomous-review-attempt: $HEAD_SHA run=$GITHUB_RUN_ID" in lead
    assert "Outcome: `STARTED`" in lead
    assert 'outcome = "REJECTED"' in lead
    assert 'outcome = "FAILED"' in lead
    assert "if: always() && steps.review_attempt.outputs.issue != ''" in lead
    assert "gh issue edit \"$ISSUE_NUMBER\"" in lead
    assert "run-name: Cloud specialist task=${{ inputs.task_id }} request=${{ inputs.orchestrator_request_id }}" in cloud


class _API:
    def __init__(self):
        self.repo = "rnnyrgs-web/tradingview-ai-crypto"
        self.main_sha = "c" * 40
        self.pr = _pr()
        self.ci = _ci()
        self.branches: set[str] = set()
        self.sent: list[tuple[str, dict]] = []
        self.requests: list[tuple[str, int, str]] = []
        self.review_issue: dict | None = None
        self.review_execution: dict = {"status": "MISSING"}
        self.lead_reviewable = True
        self.dispatch_runs: list[dict] = []
        self.dispatch_error = False
        self.worker_outcome = None
        self.pr_base_current = True

    def current_main_sha(self):
        return self.main_sha

    def get_pr(self, number):
        assert number == 501
        return self.pr

    def security_runs(self, branch):
        return self.ci

    def request_review(self, task_id, number, head):
        self.requests.append((task_id, number, head))

    def get_review_issue(self, head):
        return self.review_issue

    def get_lead_review_execution(self, head, branch):
        return self.review_execution

    def lead_can_review(self, branch, head, main_sha):
        return self.lead_reviewable and branch.startswith("auto/")

    def pr_base_is_current(self, branch, head, main_sha):
        return self.pr_base_current

    def branch_exists(self, branch):
        return branch in self.branches

    def dispatch_workflow(self, workflow, inputs):
        self.sent.append((workflow, inputs))
        if self.dispatch_error:
            raise RuntimeError("dispatch acknowledgment lost")

    def find_dispatch_run(self, task_id, request_ids, main_sha, earliest_at):
        matches = [run for run in self.dispatch_runs if run["request_id"] in request_ids
                   and run["task_id"] == task_id and run["head_sha"] == main_sha]
        if len(matches) > 1:
            raise RuntimeError("ambiguous exact dispatch runs")
        return matches[0] if matches else None

    def get_dispatch_outcome(self, run_id, request_id, task_id, main_sha, branch):
        return self.worker_outcome


class _Store:
    def __init__(self):
        self.value = {"version": 1, "reviews": {}, "dispatches": {}, "review_attempts": {}, "runs": []}
        self.writes = 0
        self.fail_on_write: int | None = None

    def load(self):
        return copy.deepcopy(self.value)

    def save(self, value):
        if self.fail_on_write == self.writes + 1:
            self.writes += 1
            raise RuntimeError("durable CAS write failed")
        self.value = copy.deepcopy(value)
        self.writes += 1


class _Budget:
    def __init__(self, allowed=True):
        self.allowed = allowed

    def can_dispatch(self, config, role, now):
        return self.allowed


def _pr_open_coordination():
    coordination = load_state()
    task = _ready_task(coordination)
    task["status"] = "PR_OPEN"
    task["pr"] = 501
    return coordination, task


def test_existing_review_cycle_requests_once_then_imports_exact_three_lane_receipt():
    coordination, task = _pr_open_coordination()
    api, store, budget = _API(), _Store(), _Budget()
    first = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                      budget, NOW, api.main_sha)
    second = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                       budget, NOW, api.main_sha)
    assert first.reason == "REVIEW_REQUESTED"
    assert second.reason == "REVIEW_EVIDENCE_MISSING"
    assert api.requests == [(task["id"], 501, HEAD)]
    api.review_issue = _existing_review_issue()
    third = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                      budget, NOW, api.main_sha)
    fourth = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                       budget, NOW, api.main_sha)
    assert third.lifecycle is Lifecycle.READY_FOR_INTEGRATION
    assert fourth.reason == "WAIT_FOR_LEAD_INTEGRATION"
    assert len(store.value["reviews"]) == 1
    assert store.value["review_attempts"][review_identity(task["id"], 501, HEAD)]["status"] == "COMPLETED"
    assert api.sent == []


def test_existing_review_cycle_rejects_issue_for_old_head():
    coordination, task = _pr_open_coordination()
    api, store, budget = _API(), _Store(), _Budget()
    api.pr = _pr(NEW_HEAD)
    api.ci = _ci(NEW_HEAD)
    api.review_issue = _existing_review_issue(HEAD)
    decision = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                         budget, NOW, api.main_sha)
    assert decision.lifecycle is Lifecycle.AWAITING_REVIEW
    assert decision.reason == "REVIEW_REQUESTED"
    assert store.value["reviews"] == {}
    assert api.requests == [(task["id"], 501, NEW_HEAD)]


def test_rejected_exact_head_review_becomes_revision_required_once():
    coordination, task = _pr_open_coordination()
    api, store, budget = _API(), _Store(), _Budget()
    api.review_execution = {"status": "REJECTED", "outcomes": {
        "security": "APPROVE", "lead": "REJECT", "claude-adversarial": "APPROVE"}}
    first = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                      budget, NOW, api.main_sha)
    second = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                       budget, NOW, api.main_sha)
    assert first.lifecycle is second.lifecycle is Lifecycle.REVISION_REQUIRED
    assert first.reason == "REVIEW_REJECTED"
    assert store.value["reviews"][review_identity(task["id"], 501, HEAD)]["outcome"] == "REJECT"
    assert api.requests == []


def test_failed_review_execution_blocks_and_missing_evidence_times_out():
    coordination, task = _pr_open_coordination()
    api, store, budget = _API(), _Store(), _Budget()
    api.review_execution = {"status": "FAILED", "run_id": 91}
    failed = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                       budget, NOW, api.main_sha)
    assert failed.lifecycle is Lifecycle.BLOCKED
    assert failed.reason == "REVIEW_WORKFLOW_FAILED"
    assert store.value["reviews"] == {}
    api.review_execution = {"status": "MISSING"}
    waiting = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                        budget, NOW, api.main_sha)
    assert waiting.lifecycle is Lifecycle.BLOCKED
    assert api.requests == []

    fresh_store = _Store()
    first = run_existing_review_cycle(coordination, _policy(), _config(), api, fresh_store,
                                      budget, NOW, api.main_sha)
    timeout = run_existing_review_cycle(coordination, _policy(), _config(), api, fresh_store,
                                        budget, NOW + timedelta(hours=3), api.main_sha)
    assert first.reason == "REVIEW_REQUESTED"
    assert timeout.reason == "REVIEW_EVIDENCE_TIMEOUT"
    assert timeout.lifecycle is Lifecycle.MANUAL_REVIEW_REQUIRED
    assert fresh_store.value["reviews"] == {}
    assert len(api.requests) == 1


def test_completed_approval_without_exact_head_receipt_is_durably_blocked():
    coordination, task = _pr_open_coordination()
    api, store, budget = _API(), _Store(), _Budget()
    api.review_execution = {"status": "APPROVED", "run_id": 91}
    first = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                      budget, NOW, api.main_sha)
    writes = store.writes
    second = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                       budget, NOW + timedelta(minutes=1), api.main_sha)
    assert first.reason == second.reason == "APPROVAL_RECEIPT_MISSING"
    assert first.lifecycle is second.lifecycle is Lifecycle.BLOCKED
    assert store.writes == writes
    assert store.value["review_attempts"][review_identity(task["id"], 501, HEAD)]["status"] == "BLOCKED"
    assert store.value["reviews"] == {}


def test_supported_review_route_reports_running_and_unsupported_route_waits_manual():
    coordination, task = _pr_open_coordination()
    api, store, budget = _API(), _Store(), _Budget()
    first = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                      budget, NOW, api.main_sha)
    api.review_execution = {"status": "RUNNING", "run_id": 92}
    running = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                        budget, NOW, api.main_sha)
    assert first.reason == "REVIEW_REQUESTED"
    assert running.lifecycle is Lifecycle.REVIEWING
    assert running.reason == "REVIEW_WORKFLOW_RUNNING"
    api.review_issue = _existing_review_issue()
    still_running = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                              budget, NOW, api.main_sha)
    assert still_running.lifecycle is Lifecycle.REVIEWING
    assert store.value["reviews"] == {}
    api.review_issue = None

    manual_store = _Store()
    api.pr["head"]["ref"] = task["branch"]
    api.lead_reviewable = False
    api.review_execution = {"status": "MISSING"}
    manual = run_existing_review_cycle(coordination, _policy(), _config(), api, manual_store,
                                       budget, NOW, api.main_sha)
    assert manual.lifecycle is Lifecycle.MANUAL_REVIEW_REQUIRED
    assert manual.reason == "MANUAL_REVIEW_REQUIRED"
    assert manual_store.value["review_attempts"][review_identity(task["id"], 501, HEAD)]["status"] == "MANUAL_REVIEW_REQUIRED"
    assert len(api.requests) == 1
    api.review_issue = _existing_review_issue(branch=task["branch"])
    imported = run_existing_review_cycle(coordination, _policy(), _config(), api, manual_store,
                                         budget, NOW, api.main_sha)
    assert imported.lifecycle is Lifecycle.READY_FOR_INTEGRATION


def test_dispatch_post_failure_recovers_only_after_proven_absence_and_one_retry():
    coordination = load_state()
    task = _ready_task(coordination)
    api, store, budget = _API(), _Store(), _Budget()
    api.dispatch_error = True
    first = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                      budget, NOW, api.main_sha)
    immediate = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                          budget, NOW + timedelta(minutes=1), api.main_sha)
    api.dispatch_error = False
    retried = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                        budget, NOW + timedelta(minutes=6), api.main_sha)
    again = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                      budget, NOW + timedelta(minutes=7), api.main_sha)
    assert first.reason == "DISPATCH_OUTCOME_UNKNOWN"
    assert immediate.reason == "DISPATCH_VISIBILITY_WAIT"
    assert retried.reason == "DISPATCH_RETRIED"
    assert again.reason == "DISPATCH_VISIBILITY_WAIT"
    assert len(api.sent) == 2
    assert [call[1]["task_id"] for call in api.sent] == [task["id"], task["id"]]
    assert api.sent[0][1]["orchestrator_request_id"] != api.sent[1][1]["orchestrator_request_id"]
    exhausted = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                           budget, NOW + timedelta(minutes=12), api.main_sha)
    repeated = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                          budget, NOW + timedelta(minutes=13), api.main_sha)
    assert exhausted.reason == repeated.reason == "DISPATCH_RETRY_EXHAUSTED"
    assert exhausted.lifecycle is repeated.lifecycle is Lifecycle.BLOCKED
    assert len(api.sent) == 2


def test_dispatch_run_is_adopted_when_post_succeeds_but_receipt_save_fails():
    coordination = load_state()
    task = _ready_task(coordination)
    api, store, budget = _API(), _Store(), _Budget()
    store.fail_on_write = 2
    with pytest.raises(RuntimeError, match="durable CAS"):
        run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                  budget, NOW, api.main_sha)
    assert store.value["dispatches"][task["id"]]["status"] == "REQUESTED"
    request_id = api.sent[0][1]["orchestrator_request_id"]
    api.dispatch_runs = [{"id": 123, "request_id": request_id,
                          "task_id": task["id"], "head_sha": api.main_sha,
                          "status": "queued"}]
    store.fail_on_write = None
    adopted = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                        budget, NOW + timedelta(minutes=1), api.main_sha)
    assert adopted.reason == "DISPATCH_RUN_ADOPTED"
    assert store.value["dispatches"][task["id"]]["run_id"] == 123
    assert len(api.sent) == 1
    api.dispatch_runs = []
    remembered = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                            budget, NOW + timedelta(minutes=20), api.main_sha)
    assert remembered.reason == "DISPATCH_RUN_PREVIOUSLY_OBSERVED"
    assert len(api.sent) == 1


def test_completed_failed_dispatch_is_durable_blocker_without_retry():
    coordination = load_state()
    task = _ready_task(coordination)
    api, store, budget = _API(), _Store(), _Budget()
    run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                              budget, NOW, api.main_sha)
    request_id = api.sent[0][1]["orchestrator_request_id"]
    api.dispatch_runs = [{"id": 124, "request_id": request_id,
                          "task_id": task["id"], "head_sha": api.main_sha,
                          "status": "completed", "conclusion": "failure"}]
    first = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                      budget, NOW + timedelta(minutes=1), api.main_sha)
    second = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                       budget, NOW + timedelta(minutes=2), api.main_sha)
    assert first.reason == second.reason == "WORKFLOW_FAILED"
    assert first.lifecycle is second.lifecycle is Lifecycle.BLOCKED
    assert store.value["dispatches"][task["id"]]["status"] == "BLOCKED"
    assert len(api.sent) == 1


def _complete_dispatch(coordination, api, store, budget, task, outcome, *, main_advanced=False):
    original_main = api.main_sha
    run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                              budget, NOW, original_main)
    request_id = api.sent[0][1]["orchestrator_request_id"]
    api.dispatch_runs = [{"id": 125, "request_id": request_id,
                          "task_id": task["id"], "head_sha": original_main,
                          "status": "completed", "conclusion": "success"}]
    api.worker_outcome = outcome
    if main_advanced:
        api.main_sha = "d" * 40
    return run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                     budget, NOW + timedelta(minutes=1), api.main_sha)


def test_main_advance_adopts_original_dispatch_and_requires_fresh_pr_base():
    coordination = load_state()
    task = _ready_task(coordination)
    api, store, budget = _API(), _Store(), _Budget()
    result = _complete_dispatch(coordination, api, store, budget, task,
                                {"status": "PR_CREATED", "reason": "candidate PR published",
                                 "pr_number": 501,
                                 "head_sha": HEAD}, main_advanced=True)
    assert result.lifecycle is Lifecycle.AWAITING_REVIEW
    assert store.value["dispatches"][task["id"]]["main_sha"] == "c" * 40
    assert store.value["dispatches"][task["id"]]["run_id"] == 125
    assert len(api.sent) == 1
    task["status"], task["pr"] = "PR_OPEN", 501
    api.pr_base_current = False
    stale = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                      budget, NOW + timedelta(minutes=2), api.main_sha)
    assert stale.reason == "STALE_PR_BASE"
    assert stale.lifecycle is Lifecycle.REVISION_REQUIRED


def test_created_pr_enters_exact_head_review_after_canonical_pr_open():
    coordination = load_state()
    task = _ready_task(coordination)
    api, store, budget = _API(), _Store(), _Budget()
    _complete_dispatch(coordination, api, store, budget, task,
                       {"status": "PR_CREATED", "reason": "candidate PR published",
                        "pr_number": 501, "head_sha": HEAD})
    task["status"], task["pr"] = "PR_OPEN", 501
    result = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                       budget, NOW + timedelta(minutes=2), api.main_sha)
    assert result.lifecycle is Lifecycle.AWAITING_REVIEW
    assert result.reason == "REVIEW_REQUESTED"
    assert result.head_sha == HEAD


def test_created_pr_with_wrong_branch_fails_closed():
    coordination = load_state()
    task = _ready_task(coordination)
    api, store, budget = _API(), _Store(), _Budget()
    api.pr["head"]["ref"] = "auto/data-market/other-task"
    result = _complete_dispatch(coordination, api, store, budget, task,
                                {"status": "PR_CREATED", "reason": "candidate PR published",
                                 "pr_number": 501, "head_sha": HEAD})
    assert result.reason == "WORKER_PR_MISMATCH"
    assert result.lifecycle is Lifecycle.BLOCKED
    assert len(api.sent) == 1


@pytest.mark.parametrize("status,lifecycle", [
    ("NO_CHANGE", Lifecycle.DONE),
    ("BLOCKED", Lifecycle.BLOCKED),
    ("WAIT", Lifecycle.READY),
    ("TASK_MISMATCH", Lifecycle.BLOCKED),
    ("NOT_CLAIMED", Lifecycle.BLOCKED),
    ("FAILED", Lifecycle.BLOCKED),
])
def test_successful_no_pr_outcome_reconciles_without_redispatch(status, lifecycle):
    coordination = load_state()
    task = _ready_task(coordination)
    api, store, budget = _API(), _Store(), _Budget()
    outcome = {"status": status, "reason": "bounded worker result"}
    if status == "WAIT":
        outcome["retry_at"] = (NOW + timedelta(hours=1)).isoformat()
    first = _complete_dispatch(coordination, api, store, budget, task, outcome)
    second = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                       budget, NOW + timedelta(minutes=2), api.main_sha)
    assert first.lifecycle is second.lifecycle is lifecycle
    assert first.reason == second.reason
    assert store.value["dispatches"][task["id"]]["worker_outcome"] == outcome
    assert len(api.sent) == 1


def _completed_wait(*, main_advanced=False):
    coordination = _idle_coordination()
    task = _ready_task(coordination)
    api, store, budget = _API(), _Store(), _Budget()
    outcome = {"status": "WAIT", "reason": "cooldown",
               "retry_at": (NOW + timedelta(hours=1)).isoformat()}
    observed = _complete_dispatch(coordination, api, store, budget, task, outcome,
                                  main_advanced=main_advanced)
    assert observed.reason == "WORKER_WAIT"
    return coordination, task, api, store, budget


def _archived_receipt(intent):
    receipt = copy.deepcopy(intent)
    receipt.pop("history", None)
    return receipt


def test_wait_before_retry_at_is_repeatable_without_a_second_dispatch():
    coordination, task, api, store, budget = _completed_wait()
    original = copy.deepcopy(store.value["dispatches"][task["id"]])
    writes = store.writes
    for minute in (2, 30, 59):
        result = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                           budget, NOW + timedelta(minutes=minute), api.main_sha)
        assert result.reason == "WORKER_WAIT"
    assert store.value["dispatches"][task["id"]] == original
    assert store.writes == writes
    assert len(api.sent) == 1


@pytest.mark.parametrize("minutes", [60, 61])
@pytest.mark.parametrize("main_advanced", [False, True])
def test_wait_releases_once_at_or_after_deadline_on_current_main(minutes, main_advanced):
    coordination, task, api, store, budget = _completed_wait(main_advanced=main_advanced)
    original = copy.deepcopy(store.value["dispatches"][task["id"]])
    released = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                         budget, NOW + timedelta(minutes=minutes), api.main_sha)
    fresh = store.value["dispatches"][task["id"]]
    assert released.reason == "WAIT_REDISPATCHED"
    assert fresh["status"] == "DISPATCHED"
    assert fresh["main_sha"] == api.main_sha
    assert fresh["generation"] == 1
    assert fresh["history"] == [_archived_receipt(original)]
    assert fresh["attempts"][0]["request_id"] != original["attempts"][0]["request_id"]
    assert api.sent[-1][1]["orchestrator_request_id"] == fresh["attempts"][0]["request_id"]
    assert len(api.sent) == 2
    for minute in (minutes, minutes + 1):
        repeated = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                             budget, NOW + timedelta(minutes=minute), api.main_sha)
        assert repeated.reason == "DISPATCH_VISIBILITY_WAIT"
    assert len(api.sent) == 2
    assert store.value["dispatches"][task["id"]]["history"] == [_archived_receipt(original)]


def test_wait_release_rechecks_canonical_ownership_branch_and_budget():
    for change, expected in [
        (lambda task, api, budget: task.update(eligible_engines=["claude-code"]), "ENGINE_INELIGIBLE"),
        (lambda task, api, budget: task.update(eligible_engines=["chatgpt", "claude-code"],
                                               engine_claim="claude-code"), "OTHER_ENGINE_CLAIM"),
        (lambda task, api, budget: api.branches.add("auto/data-market/coord-test-orch-001"),
         "TASK_ALREADY_CLAIMED"),
        (lambda task, api, budget: setattr(budget, "allowed", False), "SHARED_BUDGET_DENIED"),
    ]:
        coordination, task, api, store, budget = _completed_wait()
        change(task, api, budget)
        result = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                           budget, NOW + timedelta(hours=1), api.main_sha)
        assert result.reason == expected
        assert len(api.sent) == 1
        assert store.value["dispatches"][task["id"]]["status"] == "COMPLETED"


def test_wait_release_never_runs_after_canonical_task_stops_being_ready():
    coordination, task, api, store, budget = _completed_wait()
    task["status"] = "BLOCKED"
    task["blockers"] = ["new canonical blocker"]
    result = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                       budget, NOW + timedelta(hours=1), api.main_sha)
    assert result.reason == "NO_READY_TASK"
    assert len(api.sent) == 1


def test_wait_release_first_cas_failure_does_not_post_and_can_restart():
    coordination, task, api, store, budget = _completed_wait()
    original = copy.deepcopy(store.value["dispatches"][task["id"]])
    store.fail_on_write = store.writes + 1
    with pytest.raises(RuntimeError, match="durable CAS"):
        run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                  budget, NOW + timedelta(hours=1), api.main_sha)
    assert store.value["dispatches"][task["id"]] == original
    assert len(api.sent) == 1
    restarted = _Store()
    restarted.value = copy.deepcopy(store.value)
    released = run_existing_review_cycle(coordination, _policy(), _config(), api, restarted,
                                         budget, NOW + timedelta(hours=1), api.main_sha)
    assert released.reason == "WAIT_REDISPATCHED"
    assert restarted.value["dispatches"][task["id"]]["history"] == [_archived_receipt(original)]
    assert len(api.sent) == 2


def test_concurrent_wait_release_stale_cas_cannot_post_twice():
    coordination, task, api, store, budget = _completed_wait()
    remote = {"value": copy.deepcopy(store.value), "revision": 0}

    class SnapshotStore:
        def __init__(self):
            self.snapshot = copy.deepcopy(remote["value"])
            self.revision = remote["revision"]

        def load(self):
            return copy.deepcopy(self.snapshot)

        def save(self, value):
            if self.revision != remote["revision"]:
                raise RuntimeError("durable CAS conflict")
            remote["value"] = copy.deepcopy(value)
            remote["revision"] += 1
            self.revision = remote["revision"]
            self.snapshot = copy.deepcopy(value)

    first, stale = SnapshotStore(), SnapshotStore()
    released = run_existing_review_cycle(coordination, _policy(), _config(), api, first,
                                         budget, NOW + timedelta(hours=1), api.main_sha)
    assert released.reason == "WAIT_REDISPATCHED"
    with pytest.raises(RuntimeError, match="durable CAS conflict"):
        run_existing_review_cycle(coordination, _policy(), _config(), api, stale,
                                  budget, NOW + timedelta(hours=1), api.main_sha)
    assert len(api.sent) == 2
    replayed = run_existing_review_cycle(coordination, _policy(), _config(), api,
                                         SnapshotStore(), budget,
                                         NOW + timedelta(hours=1), api.main_sha)
    assert replayed.reason == "DISPATCH_VISIBILITY_WAIT"
    assert len(api.sent) == 2


def test_wait_release_second_cas_failure_adopts_exact_run_after_restart():
    coordination, task, api, store, budget = _completed_wait()
    original = copy.deepcopy(store.value["dispatches"][task["id"]])
    store.fail_on_write = store.writes + 2
    with pytest.raises(RuntimeError, match="durable CAS"):
        run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                  budget, NOW + timedelta(hours=1), api.main_sha)
    pending = store.value["dispatches"][task["id"]]
    assert pending["status"] == "REQUESTED"
    assert pending["history"] == [_archived_receipt(original)]
    assert len(api.sent) == 2
    api.dispatch_runs = [{"id": 126, "request_id": pending["attempts"][0]["request_id"],
                          "task_id": task["id"], "head_sha": api.main_sha,
                          "status": "queued", "conclusion": None}]
    restarted = _Store()
    restarted.value = copy.deepcopy(store.value)
    adopted = run_existing_review_cycle(coordination, _policy(), _config(), api, restarted,
                                        budget, NOW + timedelta(hours=1, minutes=1), api.main_sha)
    assert adopted.reason == "DISPATCH_RUN_ADOPTED"
    assert restarted.value["dispatches"][task["id"]]["run_id"] == 126
    assert len(api.sent) == 2


def test_wait_release_post_uncertainty_adopts_exact_run_without_duplicate():
    coordination, task, api, store, budget = _completed_wait()
    original = copy.deepcopy(store.value["dispatches"][task["id"]])
    api.dispatch_error = True
    uncertain = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                          budget, NOW + timedelta(hours=1), api.main_sha)
    assert uncertain.reason == "DISPATCH_OUTCOME_UNKNOWN"
    pending = copy.deepcopy(store.value["dispatches"][task["id"]])
    assert pending["history"] == [_archived_receipt(original)]
    assert len(api.sent) == 2
    api.dispatch_runs = [{"id": 126, "request_id": pending["attempts"][0]["request_id"],
                          "task_id": task["id"], "head_sha": api.main_sha,
                          "status": "queued", "conclusion": None}]
    adopted = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                        budget, NOW + timedelta(hours=1, minutes=1), api.main_sha)
    assert adopted.reason == "DISPATCH_RUN_ADOPTED"
    assert len(api.sent) == 2
    api.dispatch_runs = []
    repeated = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                         budget, NOW + timedelta(hours=1, minutes=6), api.main_sha)
    assert repeated.reason == "DISPATCH_RUN_PREVIOUSLY_OBSERVED"
    assert len(api.sent) == 2


def test_wait_release_post_uncertainty_uses_bounded_retry_without_run():
    coordination, task, api, store, budget = _completed_wait()
    original = copy.deepcopy(store.value["dispatches"][task["id"]])
    api.dispatch_error = True
    uncertain = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                          budget, NOW + timedelta(hours=1), api.main_sha)
    assert uncertain.reason == "DISPATCH_OUTCOME_UNKNOWN"
    api.dispatch_error = False
    retried = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                        budget, NOW + timedelta(hours=1, minutes=6), api.main_sha)
    assert retried.reason == "DISPATCH_RETRIED"
    assert len(api.sent) == 3
    assert store.value["dispatches"][task["id"]]["history"] == [_archived_receipt(original)]
    assert len(store.value["dispatches"][task["id"]]["attempts"]) == 2


@pytest.mark.parametrize("retry_at", [None, "bad", "2026-09-19T17:00:00"])
def test_wait_release_rejects_missing_or_malformed_retry_at(retry_at):
    coordination, task, api, store, budget = _completed_wait()
    store.value["dispatches"][task["id"]]["worker_outcome"]["retry_at"] = retry_at
    result = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                       budget, NOW + timedelta(hours=2), api.main_sha)
    assert result.reason == "MALFORMED_WORKER_OUTCOME"
    assert result.lifecycle is Lifecycle.BLOCKED
    assert len(api.sent) == 1


def test_wait_release_rejects_corrupt_historical_receipt():
    coordination, task, api, store, budget = _completed_wait()
    run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                              budget, NOW + timedelta(hours=1), api.main_sha)
    store.value["dispatches"][task["id"]]["history"][0]["worker_outcome"] = None
    result = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                       budget, NOW + timedelta(hours=1, minutes=1), api.main_sha)
    assert result.reason == "MALFORMED_DISPATCH_INTENT"
    assert result.lifecycle is Lifecycle.BLOCKED
    assert len(api.sent) == 2


def test_wait_release_is_bounded_across_multiple_completed_waits():
    coordination, task, api, store, budget = _completed_wait()
    first = copy.deepcopy(store.value["dispatches"][task["id"]])
    released = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                         budget, NOW + timedelta(hours=1), api.main_sha)
    assert released.reason == "WAIT_REDISPATCHED"
    second_id = api.sent[-1][1]["orchestrator_request_id"]
    api.dispatch_runs = [{"id": 126, "request_id": second_id,
                          "task_id": task["id"], "head_sha": api.main_sha,
                          "status": "completed", "conclusion": "success"}]
    api.worker_outcome = {"status": "WAIT", "reason": "cooldown again",
                          "retry_at": (NOW + timedelta(hours=2)).isoformat()}
    observed = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                         budget, NOW + timedelta(hours=1, minutes=1), api.main_sha)
    assert observed.reason == "WORKER_WAIT"
    second = copy.deepcopy(store.value["dispatches"][task["id"]])
    released_again = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                               budget, NOW + timedelta(hours=2), api.main_sha)
    assert released_again.reason == "WAIT_REDISPATCHED"
    third = store.value["dispatches"][task["id"]]
    assert third["generation"] == 2
    assert third["history"] == [_archived_receipt(first), _archived_receipt(second)]
    assert len({record["attempts"][0]["request_id"] for record in
                [first, second, third]}) == 3
    third_id = api.sent[-1][1]["orchestrator_request_id"]
    api.dispatch_runs = [{"id": 127, "request_id": third_id,
                          "task_id": task["id"], "head_sha": api.main_sha,
                          "status": "completed", "conclusion": "success"}]
    api.worker_outcome = {"status": "WAIT", "reason": "still cooling down",
                          "retry_at": (NOW + timedelta(hours=3)).isoformat()}
    run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                              budget, NOW + timedelta(hours=2, minutes=1), api.main_sha)
    exhausted = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                          budget, NOW + timedelta(hours=3), api.main_sha)
    assert exhausted.reason == "WAIT_RETRY_EXHAUSTED"
    assert exhausted.lifecycle is Lifecycle.BLOCKED
    assert len(api.sent) == 3


@pytest.mark.parametrize("field,value", [
    ("run_status", "in_progress"),
    ("run_conclusion", "failure"),
    ("run_id", None),
    ("status", "OBSERVED"),
])
def test_wait_release_rejects_corrupt_active_receipt(field, value):
    coordination, task, api, store, budget = _completed_wait()
    store.value["dispatches"][task["id"]][field] = value
    result = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                       budget, NOW + timedelta(hours=1), api.main_sha)
    assert result.reason == "MALFORMED_DISPATCH_INTENT"
    assert result.lifecycle is Lifecycle.BLOCKED
    assert len(api.sent) == 1


def test_wait_release_rejects_request_identity_mismatch():
    coordination, task, api, store, budget = _completed_wait()
    store.value["dispatches"][task["id"]]["attempts"][0]["request_id"] = "f" * 24
    result = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                       budget, NOW + timedelta(hours=1), api.main_sha)
    assert result.reason == "MALFORMED_DISPATCH_INTENT"
    assert len(api.sent) == 1


def test_wait_release_rejects_missing_durable_receipt():
    coordination, task, api, store, budget = _completed_wait()
    store.value["dispatches"][task["id"]].pop("worker_outcome")
    result = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                       budget, NOW + timedelta(hours=1), api.main_sha)
    assert result.reason == "MALFORMED_DISPATCH_INTENT"
    assert result.lifecycle is Lifecycle.BLOCKED
    assert len(api.sent) == 1


def test_wait_release_rejects_missing_historical_receipt():
    coordination, task, api, store, budget = _completed_wait()
    run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                              budget, NOW + timedelta(hours=1), api.main_sha)
    store.value["dispatches"][task["id"]]["history"] = []
    result = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                       budget, NOW + timedelta(hours=1, minutes=1), api.main_sha)
    assert result.reason == "MALFORMED_DISPATCH_INTENT"
    assert result.lifecycle is Lifecycle.BLOCKED
    assert len(api.sent) == 2


@pytest.mark.parametrize("outcome", [None, {}, {"status": "NO_CHANGE"},
                                     {"status": "MERGE", "reason": "bad"}])
def test_successful_run_without_valid_worker_receipt_fails_closed(outcome):
    coordination = load_state()
    task = _ready_task(coordination)
    api, store, budget = _API(), _Store(), _Budget()
    result = _complete_dispatch(coordination, api, store, budget, task, outcome)
    assert result.lifecycle is Lifecycle.BLOCKED
    assert len(api.sent) == 1


def test_terminal_no_change_allows_successor_only_after_canonical_completion():
    coordination = _idle_coordination()
    first_task = _ready_task(coordination)
    api, store, budget = _API(), _Store(), _Budget()
    _complete_dispatch(coordination, api, store, budget, first_task,
                       {"status": "NO_CHANGE", "reason": "nothing valid to change"})
    first_task["status"] = "DONE"
    second_task = _ready_task(coordination)
    second_task["id"] = "COORD-TEST-ORCH-002"
    second_task["priority"] = 1
    result = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                       budget, NOW + timedelta(minutes=2), api.main_sha)
    assert result.task_id == second_task["id"]
    assert len(api.sent) == 2


def test_safe_cycle_dispatches_once_and_waits_for_canonical_claim():
    coordination = load_state()
    task = _ready_task(coordination)
    api, store, budget = _API(), _Store(), _Budget()
    first = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                      budget, NOW, api.main_sha)
    second = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                       budget, NOW, api.main_sha)
    assert first.reason == "DISPATCHED"
    assert second.reason == "DISPATCH_VISIBILITY_WAIT"
    assert len(api.sent) == 1
    assert api.sent[0][0] == "autonomous_cloud_specialist.yml"
    assert api.sent[0][1]["task_id"] == task["id"]
    assert store.value["dispatches"][task["id"]]["status"] == "DISPATCHED"


def test_safe_cycle_budget_denial_and_stale_main_fail_closed():
    coordination = load_state()
    _ready_task(coordination)
    api, store, budget = _API(), _Store(), _Budget(False)
    denied = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                       budget, NOW, api.main_sha)
    stale = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                      budget, NOW, "d" * 40)
    assert denied.reason == "SHARED_BUDGET_DENIED"
    assert stale.reason == "MAIN_CHANGED"
    assert api.sent == []
    assert store.writes == 0


def test_safe_cycle_malformed_state_and_failed_ci_do_not_review():
    coordination, _ = _pr_open_coordination()
    api, store, budget = _API(), _Store(), _Budget()
    api.ci = _ci(conclusion="failure")
    failure = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                        budget, NOW, api.main_sha)
    assert failure.lifecycle is Lifecycle.REVISION_REQUIRED
    assert api.requests == []
    store.value.pop("reviews")
    malformed = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                          budget, NOW, api.main_sha)
    assert malformed.reason == "MALFORMED_ORCHESTRATOR_STATE"
    assert store.writes == 0


def test_safe_cycle_without_canonical_successor_waits():
    api, store, budget = _API(), _Store(), _Budget()
    result = run_existing_review_cycle(_idle_coordination(), _policy(), _config(), api, store,
                                       budget, NOW, api.main_sha)
    assert result.reason == "NO_READY_TASK"
    assert api.sent == []


def test_git_hub_state_store_uses_non_main_cas_and_rejects_conflict(monkeypatch):
    from agents.development_orchestrator_runtime import GitHubStateStore

    remote = {"value": None, "sha": None, "writes": []}

    def get_content(**kwargs):
        assert kwargs["ref"] == "automation/specialist-runner-state"
        assert kwargs["path"] == "development_orchestrator_state.json"
        return copy.deepcopy(remote["value"]), remote["sha"]

    def put_content(**kwargs):
        assert kwargs["ref"] != "main"
        assert kwargs["sha"] == remote["sha"]
        remote["value"] = copy.deepcopy(kwargs["content"])
        remote["sha"] = "blob-1"
        remote["writes"].append(kwargs)
        return remote["sha"]

    monkeypatch.setattr("agents.development_orchestrator_runtime._gh_get_content", get_content)
    monkeypatch.setattr("agents.development_orchestrator_runtime._gh_put_content", put_content)
    store = GitHubStateStore("rnnyrgs-web/tradingview-ai-crypto", "token", "automation/specialist-runner-state")
    state = store.load()
    assert state == {"version": 1, "reviews": {}, "dispatches": {}, "review_attempts": {}, "runs": []}
    store.save(state)
    assert len(remote["writes"]) == 1
    monkeypatch.setattr("agents.development_orchestrator_runtime._gh_put_content", lambda **kwargs: None)
    with pytest.raises(RuntimeError, match="conflict"):
        store.save(state)


def test_real_dispatch_adapter_requires_exact_workflow_and_github_acknowledgment():
    from agents.development_orchestrator_runtime import GitHubAPI

    class Response:
        status_code = 204
        text = ""

    class Client:
        def __init__(self):
            self.calls = []

        def post(self, url, **kwargs):
            self.calls.append((url, kwargs))
            return Response()

    client = Client()
    api = GitHubAPI("rnnyrgs-web/tradingview-ai-crypto", "token", client)
    api.dispatch_workflow("autonomous_cloud_specialist.yml", {
        "task_id": "COORD-TEST-001", "orchestrator_request_id": "a" * 24})
    assert client.calls[0][0].endswith("/actions/workflows/autonomous_cloud_specialist.yml/dispatches")
    assert client.calls[0][1]["json"] == {"ref": "main", "inputs": {
        "task_id": "COORD-TEST-001", "orchestrator_request_id": "a" * 24}}
    with pytest.raises(ValueError):
        api.dispatch_workflow("unsafe.yml", {"task_id": "COORD-TEST-001"})


def test_review_request_adapter_posts_only_exact_metadata():
    from agents.development_orchestrator_runtime import GitHubAPI

    class Response:
        status_code = 201
        text = ""

    class Client:
        def __init__(self):
            self.calls = []

        def post(self, url, **kwargs):
            self.calls.append((url, kwargs))
            return Response()

    client = Client()
    api = GitHubAPI("rnnyrgs-web/tradingview-ai-crypto", "token", client)
    api.request_review("COORD-TEST-ORCH-001", 501, HEAD)
    url, kwargs = client.calls[0]
    assert url.endswith("/issues/501/comments")
    assert "COORD-TEST-ORCH-001" in kwargs["json"]["body"]
    assert HEAD in kwargs["json"]["body"]
    assert "diff --git" not in kwargs["json"]["body"]


def test_review_issue_lookup_requires_unambiguous_exact_title():
    from agents.development_orchestrator_runtime import GitHubAPI

    class Response:
        status_code = 200

        def __init__(self, items):
            self.items = items

        def json(self):
            return {"items": self.items}

    class Client:
        def __init__(self):
            self.items = []

        def get(self, url, **kwargs):
            assert url == "https://api.github.com/search/issues"
            assert HEAD in kwargs["params"]["q"]
            return Response(self.items)

    client = Client()
    api = GitHubAPI("rnnyrgs-web/tradingview-ai-crypto", "token", client)
    assert api.get_review_issue(HEAD) is None
    client.items = [_existing_review_issue(), {"title": "unrelated", "state": "open"}]
    assert api.get_review_issue(HEAD) == client.items[0]
    client.items.append(copy.deepcopy(client.items[0]))
    with pytest.raises(RuntimeError, match="ambiguous"):
        api.get_review_issue(HEAD)


def test_lead_execution_adapter_checks_exact_bot_receipt_and_workflow_run():
    from agents.development_orchestrator_runtime import GitHubAPI

    class Response:
        status_code = 200

        def __init__(self, payload):
            self.payload = payload

        def json(self):
            return self.payload

    class Client:
        def __init__(self):
            self.issue = _lead_attempt_issue()
            self.status = "completed"
            self.conclusion = "failure"

        def get(self, url, **kwargs):
            if url.endswith("/actions/runs/91"):
                return Response({"id": 91, "name": "Autonomous Lead Integrator",
                                 "head_sha": "c" * 40, "head_branch": "main",
                                 "status": self.status, "conclusion": self.conclusion})
            assert url == "https://api.github.com/search/issues"
            return Response({"items": [self.issue]})

    client = Client()
    api = GitHubAPI("rnnyrgs-web/tradingview-ai-crypto", "token", client)
    rejected = api.get_lead_review_execution(HEAD, "auto/data-market/coord-test-orch-001")
    assert rejected["status"] == "REJECTED"
    assert rejected["outcomes"]["lead"] == "REJECT"
    client.issue = _lead_attempt_issue("STARTED")
    client.status, client.conclusion = "in_progress", None
    assert api.get_lead_review_execution(HEAD, "auto/data-market/coord-test-orch-001")["status"] == "RUNNING"
    client.status, client.conclusion = "completed", "failure"
    assert api.get_lead_review_execution(HEAD, "auto/data-market/coord-test-orch-001")["status"] == "FAILED"


def test_lead_route_requires_auto_branch_forked_from_current_main():
    from agents.development_orchestrator_runtime import GitHubAPI

    class Response:
        status_code = 200

        def __init__(self, sha):
            self.sha = sha

        def json(self):
            return {"merge_base_commit": {"sha": self.sha}, "ahead_by": 1}

    class Client:
        def __init__(self):
            self.base = "c" * 40

        def get(self, url, **kwargs):
            assert "/compare/" in url
            return Response(self.base)

    client = Client()
    api = GitHubAPI("rnnyrgs-web/tradingview-ai-crypto", "token", client)
    assert api.lead_can_review("auto/data-market/task", HEAD, "c" * 40)
    assert api.pr_base_is_current("auto/data-market/task", HEAD, "c" * 40)
    assert not api.lead_can_review("agent/data-market", HEAD, "c" * 40)
    client.base = "d" * 40
    assert not api.lead_can_review("auto/data-market/task", HEAD, "c" * 40)
    assert not api.pr_base_is_current("auto/data-market/task", HEAD, "c" * 40)


def test_dispatch_outcome_adapter_requires_exact_runner_receipt(monkeypatch):
    from agents.development_orchestrator_runtime import GitHubAPI

    receipt = {"request_id": "a" * 24, "workflow_run_id": 125,
               "task_id": "COORD-TEST-001", "base_main_sha": "c" * 40,
               "branch": "auto/data-market/coord-test-001",
               "status": "NO_CHANGE", "reason": "no valid change"}
    remote = {"dispatch_results": {"a" * 24: receipt}}
    monkeypatch.setattr("agents.development_orchestrator_runtime._gh_get_content",
                        lambda **kwargs: (remote, "blob"))
    api = GitHubAPI("rnnyrgs-web/tradingview-ai-crypto", "token", object())
    result = api.get_dispatch_outcome(125, "a" * 24, "COORD-TEST-001", "c" * 40,
                                      "auto/data-market/coord-test-001")
    assert result == {"status": "NO_CHANGE", "reason": "no valid change"}
    remote["dispatch_results"]["a" * 24] = dict(receipt, workflow_run_id=126)
    with pytest.raises(RuntimeError, match="identity"):
        api.get_dispatch_outcome(125, "a" * 24, "COORD-TEST-001", "c" * 40,
                                 "auto/data-market/coord-test-001")


def test_runner_receipt_classifies_pr_no_change_blocked_wait_and_mismatch():
    from agents.autonomous_cloud_state import mark_dispatch_result

    base = {"version": 1, "runs": [], "dispatch_results": {},
            "next_eligible_at": "2026-09-19T17:00:00Z"}
    cases = [
        ({"run": True, "task_id": "COORD-TEST-001"},
         {"outcome": {"status": "READY_FOR_PR", "summary": "candidate"}},
         501, HEAD, "PR_CREATED"),
        ({"run": True, "task_id": "COORD-TEST-001"},
         {"outcome": {"status": "NO_CHANGE", "summary": "nothing valid"}},
         None, None, "NO_CHANGE"),
        ({"run": True, "task_id": "COORD-TEST-001"},
         {"outcome": {"status": "BLOCKED", "summary": "data missing"}},
         None, None, "BLOCKED"),
        ({"run": False, "reason": "COOLDOWN"}, None, None, None, "WAIT"),
        ({"run": False, "reason": "DISPATCH_TASK_ID_MISMATCH"},
         None, None, None, "TASK_MISMATCH"),
    ]
    for plan, result, pr_number, head, expected in cases:
        updated = mark_dispatch_result(base, request_id="a" * 24,
                                       task_id="COORD-TEST-001", workflow_run_id=125,
                                       base_main_sha="c" * 40, plan=plan,
                                       result=result, pr_number=pr_number, head_sha=head)
        receipt = updated["dispatch_results"]["a" * 24]
        assert receipt["status"] == expected
        assert receipt["task_id"] == "COORD-TEST-001"
        assert receipt["workflow_run_id"] == 125
        assert receipt["base_main_sha"] == "c" * 40
        assert mark_dispatch_result(updated, request_id="a" * 24,
                                    task_id="COORD-TEST-001", workflow_run_id=125,
                                    base_main_sha="c" * 40, plan=plan,
                                    result=result, pr_number=pr_number, head_sha=head) == updated


def test_runner_receipt_rejects_mismatched_task_and_pr_without_head():
    from agents.autonomous_cloud_state import mark_dispatch_result

    state = {"version": 1, "runs": [], "dispatch_results": {}}
    with pytest.raises(ValueError):
        mark_dispatch_result(state, request_id="a" * 24,
                             task_id="COORD-TEST-001", workflow_run_id=125,
                             base_main_sha="c" * 40,
                             plan={"run": True, "task_id": "OTHER"}, result=None,
                             pr_number=None, head_sha=None)
    with pytest.raises(ValueError):
        mark_dispatch_result(state, request_id="a" * 24,
                             task_id="COORD-TEST-001", workflow_run_id=125,
                             base_main_sha="c" * 40,
                             plan={"run": True, "task_id": "COORD-TEST-001"},
                             result={"outcome": {"status": "READY_FOR_PR", "summary": "x"}},
                             pr_number=None, head_sha=None)


def test_dispatch_run_adapter_requires_exact_run_name_head_and_complete_listing():
    from agents.development_orchestrator_runtime import GitHubAPI

    class Response:
        status_code = 200

        def __init__(self, runs):
            self.runs = runs

        def json(self):
            return {"workflow_runs": self.runs}

    class Client:
        def __init__(self):
            self.runs = []

        def get(self, url, **kwargs):
            assert url.endswith("/actions/workflows/autonomous_cloud_specialist.yml/runs")
            return Response(self.runs)

    client = Client()
    api = GitHubAPI("rnnyrgs-web/tradingview-ai-crypto", "token", client)
    request_id = "a" * 24
    assert api.find_dispatch_run("COORD-TEST-001", [request_id], "c" * 40, NOW) is None
    client.runs = [{"id": 99, "display_title": f"Cloud specialist task=COORD-TEST-001 request={request_id}",
                    "head_sha": "c" * 40, "status": "queued", "conclusion": None,
                    "event": "workflow_dispatch",
                    "created_at": "2026-09-19T16:01:00Z"}]
    assert api.find_dispatch_run("COORD-TEST-001", [request_id], "c" * 40, NOW)["id"] == 99
    client.runs[0]["head_sha"] = "d" * 40
    with pytest.raises(RuntimeError, match="different main head"):
        api.find_dispatch_run("COORD-TEST-001", [request_id], "c" * 40, NOW)
    client.runs = [{"id": index, "display_title": "unrelated", "head_sha": "c" * 40,
                    "event": "workflow_dispatch", "status": "completed", "conclusion": "success",
                    "created_at": "2026-09-19T16:01:00Z"} for index in range(100)]
    with pytest.raises(RuntimeError, match="incomplete"):
        api.find_dispatch_run("COORD-TEST-001", [request_id], "c" * 40, NOW)


def test_dispatch_preflight_reads_shared_fleet_spend_and_denies_over_ceiling(monkeypatch):
    from agents.development_orchestrator_runtime import FleetBudget

    def get_content(**kwargs):
        if kwargs["path"] == "runner_state.json":
            return {"version": 1, "runs": []}, "sha-a"
        if kwargs["path"] == "runner_state_claude.json":
            return {"version": 1, "runs": [{"finished_at": "2026-09-19T15:00:00Z",
                                               "actual_cost_usd": 29.9}]}, "sha-b"
        if kwargs["path"] in {"runner_state_claude_code.json", "development_orchestrator_state.json"}:
            return {"version": 1, "runs": []}, "sha-c"
        if kwargs["path"] == "fleet_coordination.json":
            return {"version": 1, "pending_reservations": []}, "sha-d"
        raise AssertionError(kwargs["path"])

    monkeypatch.setattr("agents.development_orchestrator_runtime._gh_get_content", get_content)
    budget = FleetBudget("rnnyrgs-web/tradingview-ai-crypto", "token")
    assert budget.can_dispatch(_config(), "data-market", NOW) is False


def _policy() -> dict:
    import json
    from pathlib import Path
    return json.loads(Path("orchestration/model_routing_policy.json").read_text(encoding="utf-8"))


def _config() -> dict:
    from agents.autonomous_cloud_runner import load_config
    return load_config()
