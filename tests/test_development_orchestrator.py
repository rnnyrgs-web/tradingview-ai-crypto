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
    task.update(id="COORD-TEST-ORCH-001", status="READY", priority=1,
                dependencies=[], blockers=[], fingerprint_id=None, pr=None,
                eligible_engines=["chatgpt"], engine_claim=None, work_mode="AUDIT")
    task.pop("completion_evidence", None)
    coordination["tasks"].append(task)
    return task


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


def _existing_review_issue(head: str = HEAD) -> dict:
    body = ("Candidate branch: `auto/data-market/coord-test-orch-001`\n"
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
    coordination = load_state()
    _ready_task(coordination, role="testing-security")
    decision = select_successor(coordination, _policy(), _config(),
                                claimed_branches=set(), dispatches={}, budget_allowed=True)
    assert decision.run is False
    assert decision.reason == "MANUAL_ADAPTER_REQUIRED"


def test_blocked_and_ineligible_tasks_do_not_dispatch():
    coordination = load_state()
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
    decision = select_successor(load_state(), _policy(), _config(), set(), {}, True)
    assert decision.run is False
    assert decision.reason == "NO_READY_TASK"
    assert not hasattr(decision, "merge")


def test_orchestrator_workflow_has_no_merge_or_trading_step():
    workflow = Path(".github/workflows/development_orchestrator.yml").read_text(encoding="utf-8")
    assert "python -m agents.development_orchestrator_runtime" in workflow
    for forbidden in ("gh pr merge", "enable-auto-merge", "git push origin main",
                      "place_order", "trade_authority"):
        assert forbidden not in workflow


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

    def branch_exists(self, branch):
        return branch in self.branches

    def dispatch_workflow(self, workflow, inputs):
        self.sent.append((workflow, inputs))


class _Store:
    def __init__(self):
        self.value = {"version": 1, "reviews": {}, "dispatches": {}, "review_attempts": {}, "runs": []}
        self.writes = 0

    def load(self):
        return copy.deepcopy(self.value)

    def save(self, value):
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
    assert second.reason == "WAIT_FOR_INDEPENDENT_REVIEW"
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


def test_safe_cycle_dispatches_once_and_waits_for_canonical_claim():
    coordination = load_state()
    task = _ready_task(coordination)
    api, store, budget = _API(), _Store(), _Budget()
    first = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                      budget, NOW, api.main_sha)
    second = run_existing_review_cycle(coordination, _policy(), _config(), api, store,
                                       budget, NOW, api.main_sha)
    assert first.reason == "DISPATCHED"
    assert second.reason == "TASK_ALREADY_CLAIMED"
    assert api.sent == [("autonomous_cloud_specialist.yml", {"task_id": task["id"]})]
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
    result = run_existing_review_cycle(load_state(), _policy(), _config(), api, store,
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
    api.dispatch_workflow("autonomous_cloud_specialist.yml", {"task_id": "COORD-TEST-001"})
    assert client.calls[0][0].endswith("/actions/workflows/autonomous_cloud_specialist.yml/dispatches")
    assert client.calls[0][1]["json"] == {"ref": "main", "inputs": {"task_id": "COORD-TEST-001"}}
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
