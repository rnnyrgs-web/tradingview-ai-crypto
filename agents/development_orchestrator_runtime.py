"""GitHub state and existing-worker dispatch adapters for development V1.

The adapter transfers task identifiers and review-request metadata only. It
does not read or transmit PR diff content, merge PRs, or edit main.
"""

from __future__ import annotations

import re
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import quote

import httpx

from agents.autonomous_cloud_runner import budget_gate, default_state
from agents.development_orchestrator import (WORKFLOW, parse_lead_execution_issue,
                                             run_existing_review_cycle)
from orchestration.specialist_coordination import load_state
from orchestration.shared_budget import (
    FLEET_COORDINATION_PATH,
    _gh_get_content,
    _gh_put_content,
    fleet_budget_gate,
    pending_reservations_spend,
)


STATE_FILE = "development_orchestrator_state.json"
STATE_BRANCH = "automation/specialist-runner-state"
REPO_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
TASK_ID_RE = re.compile(r"^[A-Z0-9][A-Z0-9_-]{2,99}$")
SHA_RE = re.compile(r"^[0-9a-f]{40}$")
REQUEST_RE = re.compile(r"^[0-9a-f]{24}$")


class GitHubAPI:
    def __init__(self, repo: str, token: str, client: httpx.Client):
        if not REPO_RE.fullmatch(repo) or not token:
            raise ValueError("GitHub repository/token unavailable")
        self.repo, self.token, self.client = repo, token, client
        self.base = f"https://api.github.com/repos/{repo}"

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.token}", "Accept": "application/vnd.github+json"}

    def _get(self, path: str, *, params: dict | None = None):
        response = self.client.get(self.base + path, params=params, headers=self._headers())
        if response.status_code != 200:
            raise RuntimeError(f"GitHub GET {path} failed: HTTP {response.status_code}")
        return response.json()

    def current_main_sha(self) -> str:
        sha = self._get("/branches/main")["commit"]["sha"]
        if not SHA_RE.fullmatch(str(sha)):
            raise RuntimeError("malformed main SHA")
        return str(sha)

    def get_pr(self, number: int) -> dict:
        if not isinstance(number, int) or number <= 0:
            raise ValueError("invalid PR number")
        value = self._get(f"/pulls/{number}")
        if not isinstance(value, dict):
            raise RuntimeError("malformed PR")
        return value

    def security_runs(self, branch: str) -> list[dict]:
        value = self._get("/actions/workflows/security.yml/runs",
                          params={"branch": branch, "per_page": 100})
        runs = value.get("workflow_runs") if isinstance(value, dict) else None
        if not isinstance(runs, list):
            raise RuntimeError("malformed security runs")
        return runs

    def get_review_issue(self, head_sha: str) -> dict | None:
        if not SHA_RE.fullmatch(head_sha):
            raise ValueError("invalid reviewed SHA")
        response = self.client.get(
            "https://api.github.com/search/issues",
            params={"q": f'repo:{self.repo} is:issue in:title "autonomous-review: {head_sha}"',
                    "per_page": 100},
            headers=self._headers(),
        )
        if response.status_code != 200:
            raise RuntimeError(f"review issue lookup failed: HTTP {response.status_code}")
        payload = response.json()
        items = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            raise RuntimeError("malformed review issue search")
        if isinstance(payload.get("total_count"), int) and payload["total_count"] > 100:
            raise RuntimeError("review issue search is incomplete")
        exact = [item for item in items if isinstance(item, dict)
                 and item.get("title") == f"autonomous-review: {head_sha}"
                 and item.get("state") == "open"]
        if len(exact) > 1:
            raise RuntimeError("ambiguous exact-head review issues")
        return exact[0] if exact else None

    def get_lead_review_execution(self, head_sha: str, branch: str) -> dict:
        if not SHA_RE.fullmatch(head_sha):
            raise ValueError("invalid reviewed SHA")
        response = self.client.get(
            "https://api.github.com/search/issues",
            params={"q": f'repo:{self.repo} is:issue in:title "autonomous-review-attempt: {head_sha}"',
                    "per_page": 100},
            headers=self._headers(),
        )
        if response.status_code != 200:
            raise RuntimeError(f"review execution lookup failed: HTTP {response.status_code}")
        payload = response.json()
        items = payload.get("items") if isinstance(payload, dict) else None
        if not isinstance(items, list):
            raise RuntimeError("malformed review execution search")
        if isinstance(payload.get("total_count"), int) and payload["total_count"] > 100:
            raise RuntimeError("review execution search is incomplete")
        exact = [item for item in items if isinstance(item, dict)
                 and re.fullmatch(r"autonomous-review-attempt: " + head_sha + r" run=[1-9][0-9]*",
                                  str(item.get("title"))) and item.get("state") == "open"]
        if not exact:
            return {"status": "MISSING"}
        if len(exact) != 1:
            raise RuntimeError("ambiguous exact-head review executions")
        parsed = parse_lead_execution_issue(exact[0], head_sha=head_sha, branch=branch)
        if parsed is None:
            raise RuntimeError("malformed exact-head review execution receipt")
        run = self._get(f"/actions/runs/{parsed['run_id']}")
        if (not isinstance(run, dict) or run.get("id") != parsed["run_id"]
                or run.get("name") != "Autonomous Lead Integrator"
                or run.get("head_sha") != parsed["main_sha"]
                or run.get("head_branch") != "main"):
            raise RuntimeError("review receipt does not match Lead workflow run")
        if run.get("status") in {"queued", "in_progress"}:
            return {"status": "RUNNING", "run_id": parsed["run_id"]}
        if run.get("status") != "completed":
            raise RuntimeError("malformed Lead workflow run status")
        if parsed["status"] == "STARTED":
            return {"status": "FAILED", "run_id": parsed["run_id"]}
        if parsed["status"] == "APPROVED" and run.get("conclusion") != "success":
            raise RuntimeError("approved receipt has failed workflow run")
        if parsed["status"] in {"REJECTED", "FAILED"} and run.get("conclusion") == "success":
            raise RuntimeError("failed review receipt has successful workflow run")
        return {key: value for key, value in parsed.items() if key in {"status", "run_id", "outcomes"}}

    def lead_can_review(self, branch: str, head_sha: str, main_sha: str) -> bool:
        return branch.startswith("auto/") and self.pr_base_is_current(branch, head_sha, main_sha)

    def pr_base_is_current(self, branch: str, head_sha: str, main_sha: str) -> bool:
        if (not isinstance(branch, str) or not branch or not SHA_RE.fullmatch(head_sha)
                or not SHA_RE.fullmatch(main_sha)):
            return False
        comparison = self._get(f"/compare/{main_sha}...{head_sha}")
        if not isinstance(comparison, dict):
            raise RuntimeError("malformed Lead review route comparison")
        merge_base = comparison.get("merge_base_commit")
        return (isinstance(merge_base, dict) and merge_base.get("sha") == main_sha
                and isinstance(comparison.get("ahead_by"), int)
                and comparison["ahead_by"] > 0)

    def branch_exists(self, branch: str) -> bool:
        if not branch.startswith("auto/"):
            raise ValueError("invalid autonomous task branch")
        path = "/git/ref/heads/" + quote(branch, safe="/")
        response = self.client.get(self.base + path, headers=self._headers())
        if response.status_code == 404:
            return False
        if response.status_code != 200:
            raise RuntimeError(f"branch lookup failed: HTTP {response.status_code}")
        return True

    def request_review(self, task_id: str, pr_number: int, head_sha: str) -> None:
        if not TASK_ID_RE.fullmatch(task_id) or pr_number <= 0 or not SHA_RE.fullmatch(head_sha):
            raise ValueError("malformed review request identity")
        body = ("Development Orchestrator V1 review request.\n\n"
                f"Canonical task: `{task_id}`\nPR: #{pr_number}\nExact head: `{head_sha}`\n\n"
                "Independent Security, Lead, and adversarial review is required on this "
                "exact head before Lead integration. This request grants no merge, "
                "strategy-promotion, broker, or trading authority.")
        response = self.client.post(self.base + f"/issues/{pr_number}/comments",
                                    headers=self._headers(), json={"body": body})
        if response.status_code != 201:
            raise RuntimeError(f"review request was not acknowledged: HTTP {response.status_code}")

    def dispatch_workflow(self, workflow: str, inputs: dict[str, str]) -> None:
        if (workflow != WORKFLOW or set(inputs) != {"task_id", "orchestrator_request_id"}
                or not TASK_ID_RE.fullmatch(inputs["task_id"])
                or not REQUEST_RE.fullmatch(inputs["orchestrator_request_id"])):
            raise ValueError("unsupported workflow dispatch")
        response = self.client.post(
            self.base + f"/actions/workflows/{WORKFLOW}/dispatches",
            headers=self._headers(), json={"ref": "main", "inputs": inputs},
        )
        if response.status_code != 204:
            raise RuntimeError(f"workflow dispatch was not acknowledged: HTTP {response.status_code}")

    def find_dispatch_run(self, task_id: str, request_ids: list[str],
                          main_sha: str, earliest_at: datetime) -> dict | None:
        if (not TASK_ID_RE.fullmatch(task_id) or not SHA_RE.fullmatch(main_sha)
                or not request_ids or any(not REQUEST_RE.fullmatch(value) for value in request_ids)
                or earliest_at.tzinfo is None):
            raise ValueError("malformed dispatch lookup identity")
        titles = {f"Cloud specialist task={task_id} request={value}": value
                  for value in request_ids}
        matches: list[dict] = []
        complete = False
        for page in range(1, 6):
            payload = self._get(f"/actions/workflows/{WORKFLOW}/runs",
                                params={"event": "workflow_dispatch", "branch": "main",
                                        "per_page": 100, "page": page})
            runs = payload.get("workflow_runs") if isinstance(payload, dict) else None
            if not isinstance(runs, list):
                raise RuntimeError("malformed dispatch run listing")
            for run in runs:
                if not isinstance(run, dict):
                    raise RuntimeError("malformed dispatch run")
                try:
                    created = datetime.fromisoformat(run["created_at"].replace("Z", "+00:00"))
                    if created.tzinfo is None:
                        raise ValueError("naive dispatch run timestamp")
                except (KeyError, AttributeError, ValueError) as exc:
                    raise RuntimeError("malformed dispatch run timestamp") from exc
                request_id = titles.get(run.get("display_title"))
                if request_id and run.get("head_sha") != main_sha:
                    raise RuntimeError("dispatch request ID appeared on a different main head")
                if request_id and run.get("event") != "workflow_dispatch":
                    raise RuntimeError("dispatch request ID appeared on a non-dispatch run")
                if request_id:
                    matches.append({"id": run.get("id"), "request_id": request_id,
                                    "task_id": task_id, "head_sha": main_sha,
                                    "status": run.get("status"),
                                    "conclusion": run.get("conclusion")})
                if created < earliest_at:
                    complete = True
            if len(runs) < 100 or complete:
                complete = True
                break
        if not complete:
            raise RuntimeError("dispatch run listing incomplete; absence not proven")
        if len(matches) > 1:
            raise RuntimeError("ambiguous exact dispatch runs")
        return matches[0] if matches else None

    def get_dispatch_outcome(self, run_id: int, request_id: str, task_id: str,
                             main_sha: str, branch: str) -> dict | None:
        if (not isinstance(run_id, int) or run_id <= 0
                or not REQUEST_RE.fullmatch(request_id)
                or not TASK_ID_RE.fullmatch(task_id)
                or not SHA_RE.fullmatch(main_sha)
                or not branch.startswith("auto/")):
            raise ValueError("malformed worker outcome lookup")
        state, _ = _gh_get_content(repo=self.repo, path="runner_state.json",
                                   ref=STATE_BRANCH, token=self.token)
        if not isinstance(state, dict) or not isinstance(state.get("dispatch_results"), dict):
            return None
        receipt = state["dispatch_results"].get(request_id)
        if receipt is None:
            return None
        if (not isinstance(receipt, dict) or receipt.get("request_id") != request_id
                or receipt.get("workflow_run_id") != run_id
                or receipt.get("task_id") != task_id
                or receipt.get("base_main_sha") != main_sha
                or receipt.get("branch") != branch):
            raise RuntimeError("worker outcome identity mismatch")
        return {key: value for key, value in receipt.items()
                if key in {"status", "reason", "retry_at", "pr_number", "head_sha"}}


class GitHubStateStore:
    def __init__(self, repo: str, token: str, ref: str = STATE_BRANCH):
        if ref in {"main", "master"} or not ref.startswith("automation/"):
            raise ValueError("orchestrator state must use an automation branch")
        self.repo, self.token, self.ref = repo, token, ref
        self.sha: str | None = None

    def load(self) -> dict:
        value, self.sha = _gh_get_content(repo=self.repo, path=STATE_FILE,
                                          ref=self.ref, token=self.token)
        if value is None:
            return {"version": 1, "reviews": {}, "dispatches": {},
                    "review_attempts": {}, "runs": []}
        if not isinstance(value, dict):
            raise RuntimeError("malformed durable orchestrator state")
        return value

    def save(self, value: dict) -> None:
        sha = _gh_put_content(repo=self.repo, path=STATE_FILE, ref=self.ref,
                              token=self.token, content=value,
                              message="Record bounded development orchestration state",
                              sha=self.sha)
        if sha is None:
            raise RuntimeError("durable orchestrator state compare-and-swap conflict")
        self.sha = sha


class FleetBudget:
    """Read-only preflight; the receiving workflow still reserves atomically."""

    def __init__(self, repo: str, token: str, ref: str = STATE_BRANCH):
        self.repo, self.token, self.ref = repo, token, ref

    def _state(self, path: str) -> dict:
        value, _ = _gh_get_content(repo=self.repo, path=path, ref=self.ref,
                                   token=self.token)
        if value is None:
            return default_state()
        if not isinstance(value, dict) or not isinstance(value.get("runs"), list):
            raise RuntimeError(f"malformed fleet spend state: {path}")
        return value

    def can_dispatch(self, config: dict, role: str, now: datetime) -> bool:
        own = self._state("runner_state.json")
        ok, _, _ = budget_gate(config, own, role, now)
        if not ok:
            return False
        siblings = [self._state(path) for path in
                    ("runner_state_claude.json", "runner_state_claude_code.json", STATE_FILE)]
        coordination, _ = _gh_get_content(repo=self.repo, path=FLEET_COORDINATION_PATH,
                                          ref=self.ref, token=self.token)
        if coordination is not None and (
            not isinstance(coordination, dict)
            or not isinstance(coordination.get("pending_reservations"), list)
        ):
            raise RuntimeError("malformed fleet coordination state")
        pending = pending_reservations_spend(coordination or {"pending_reservations": []}, now)
        ok, _, _ = fleet_budget_gate(config, own, siblings, role, now,
                                     pending_reservations_usd=pending)
        return ok


def main() -> int:
    import argparse
    from agents.autonomous_cloud_runner import load_config

    parser = argparse.ArgumentParser(description="Bounded development orchestration cycle")
    parser.add_argument("--main-sha", required=True)
    args = parser.parse_args()
    token = os.environ.get("GH_TOKEN", "")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not token or not REPO_RE.fullmatch(repo):
        raise RuntimeError("GitHub token/repository unavailable")
    root = Path(__file__).resolve().parents[1]
    coordination = load_state()
    policy = json.loads((root / "orchestration/model_routing_policy.json").read_text(encoding="utf-8"))
    config = load_config()
    state_ref = config["policy"]["state_branch"]
    with httpx.Client(timeout=30) as client:
        api = GitHubAPI(repo, token, client)
        store = GitHubStateStore(repo, token, state_ref)
        budget = FleetBudget(repo, token, state_ref)
        result = run_existing_review_cycle(coordination, policy, config, api, store, budget,
                                           datetime.now(timezone.utc), args.main_sha)
    print(json.dumps({"lifecycle": result.lifecycle.value if result.lifecycle else None,
                      "reason": result.reason, "task_id": result.task_id,
                      "head_sha": result.head_sha}, sort_keys=True))
    return 0


if __name__ == "__main__":
    sys.exit(main())
