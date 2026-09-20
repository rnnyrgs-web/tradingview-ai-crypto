from __future__ import annotations

import argparse
import copy
import json
import re
from datetime import timedelta
from pathlib import Path

# This helper is executed directly by the GitHub Actions workflow after the
# openai-agents package is installed. That dependency owns a top-level
# ``agents`` package, so importing our sibling through ``agents.*`` can resolve
# to the dependency instead of this repository. Use a relative import when the
# file is imported as a module and a direct sibling import when it is executed
# as a script.
if __package__:
    from .autonomous_cloud_runner import (
        CONFIG_PATH,
        PolicyError,
        apply_ci_status,
        iso,
        load_config,
        load_state,
        reserved_cost_usd,
        retry_delay_seconds,
        safe_branch,
        save_state,
        utc_now,
    )
else:
    from autonomous_cloud_runner import (
        CONFIG_PATH,
        PolicyError,
        apply_ci_status,
        iso,
        load_config,
        load_state,
        reserved_cost_usd,
        retry_delay_seconds,
        safe_branch,
        save_state,
        utc_now,
    )


def mark_waiting_ci(state: dict, *, branch: str, pr_number: int, head_sha: str) -> dict:
    updated = copy.deepcopy(state)
    active = updated.get("active_task")
    if not isinstance(active, dict) or active.get("phase") != "RUNNING":
        raise PolicyError("PR publication requires a RUNNING owned task")
    if branch != active.get("branch"):
        raise PolicyError("published branch does not match owned task branch")
    if branch in {"main", "master"}:
        raise PolicyError("cannot publish autonomous candidate to main")
    active["phase"] = "WAITING_CI"
    active["pr_number"] = int(pr_number)
    active["head_sha"] = head_sha
    active["ci_status"] = "queued"
    return updated


def mark_failure(state: dict, *, reason_code: str, config_path: Path = CONFIG_PATH) -> dict:
    config = load_config(config_path)
    updated = copy.deepcopy(state)
    active = updated.get("active_task")
    if not isinstance(active, dict):
        raise PolicyError("failure accounting requires an active task")
    role = str(active.get("role", ""))
    task_id = str(active.get("task_id", ""))
    if role not in config["roles"] or not task_id:
        raise PolicyError("active task is malformed")
    failures = updated.setdefault("task_failures", {})
    count = int(failures.get(task_id, 0)) + 1
    failures[task_id] = count
    now = utc_now()
    reserve = reserved_cost_usd(config, role)
    updated.setdefault("runs", []).append(
        {
            "started_at": active.get("started_at") or iso(now),
            "finished_at": iso(now),
            "role": role,
            "task_id": task_id,
            "model": config["roles"][role]["model"],
            "status": "FAILED_RESERVED",
            "failure_reason": reason_code,
            "input_tokens": 0,
            "cached_input_tokens": 0,
            "output_tokens": 0,
            "reserved_cost_usd": round(reserve, 8),
            "actual_cost_usd": round(reserve, 8),
        }
    )
    if count > int(config["policy"]["task_retry_limit"]):
        active["phase"] = "CI_FAILED"
        active["failure_reason"] = reason_code
        active["failure_count"] = count
        updated["paused_reason"] = "TASK_RETRY_LIMIT"
        return updated
    delay = retry_delay_seconds(config, count - 1)
    updated["active_task"] = None
    updated["next_eligible_at"] = iso(now + timedelta(seconds=delay))
    updated["paused_reason"] = reason_code
    return updated


def mark_dispatch_result(state: dict, *, request_id: str, task_id: str,
                         workflow_run_id: int, base_main_sha: str, plan: dict,
                         result: dict | None, pr_number: int | None,
                         head_sha: str | None) -> dict:
    """Bind one worker result to the immutable workflow dispatch in runner state."""
    if (not re.fullmatch(r"[0-9a-f]{24}", request_id)
            or not re.fullmatch(r"[A-Z0-9][A-Z0-9_-]{2,99}", task_id)
            or not isinstance(workflow_run_id, int) or workflow_run_id <= 0
            or not re.fullmatch(r"[0-9a-f]{40}", base_main_sha)
            or not isinstance(plan, dict) or not isinstance(state, dict)
            or state.get("version") != 1):
        raise ValueError("malformed dispatch result identity")
    if plan.get("run") is True:
        if plan.get("task_id") != task_id:
            raise ValueError("worker plan task ID mismatch")
        worker = result.get("outcome") if isinstance(result, dict) else None
        worker_status = worker.get("status") if isinstance(worker, dict) else None
        if worker_status == "READY_FOR_PR":
            if (not isinstance(pr_number, int) or pr_number <= 0
                    or not isinstance(head_sha, str)
                    or not re.fullmatch(r"[0-9a-f]{40}", head_sha)):
                raise ValueError("published PR receipt missing exact head")
            status, reason = "PR_CREATED", "candidate PR published"
        elif worker_status in {"NO_CHANGE", "BLOCKED"}:
            summary = worker.get("summary")
            if not isinstance(summary, str) or not summary.strip():
                raise ValueError("worker outcome summary missing")
            status, reason = worker_status, summary.strip()[:500]
        else:
            status, reason = "FAILED", "WORKER_RESULT_MISSING_OR_MALFORMED"
    elif plan.get("run") is False:
        reason = plan.get("reason")
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("worker plan reason missing")
        if reason == "DISPATCH_TASK_ID_MISMATCH":
            status = "TASK_MISMATCH"
        elif reason == "NO_READY_AUTONOMOUS_TASK":
            status = "NOT_CLAIMED"
        else:
            status = "WAIT"
    else:
        raise ValueError("worker plan run flag malformed")
    receipt = {"request_id": request_id, "workflow_run_id": workflow_run_id,
               "task_id": task_id, "base_main_sha": base_main_sha,
               "branch": safe_branch("data-market", task_id),
               "status": status, "reason": reason}
    if status == "PR_CREATED":
        receipt.update(pr_number=pr_number, head_sha=head_sha)
    if status == "WAIT":
        receipt["retry_at"] = state.get("next_eligible_at") or iso(utc_now() + timedelta(hours=1))
    updated = copy.deepcopy(state)
    results = updated.setdefault("dispatch_results", {})
    if not isinstance(results, dict):
        raise ValueError("malformed durable dispatch results")
    if request_id in results:
        if results[request_id] != receipt:
            raise ValueError("dispatch result identity already has a different outcome")
        return state
    results[request_id] = receipt
    return updated


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    pr = sub.add_parser("mark-pr")
    pr.add_argument("--state", required=True)
    pr.add_argument("--branch", required=True)
    pr.add_argument("--pr-number", required=True, type=int)
    pr.add_argument("--head-sha", required=True)

    ci = sub.add_parser("mark-ci")
    ci.add_argument("--state", required=True)
    ci.add_argument("--conclusion", required=True)
    ci.add_argument("--head-sha", required=True)

    failed = sub.add_parser("mark-failure")
    failed.add_argument("--state", required=True)
    failed.add_argument("--reason-code", required=True)
    failed.add_argument("--config", default=str(CONFIG_PATH))

    show = sub.add_parser("show")
    show.add_argument("--state", required=True)

    dispatch = sub.add_parser("mark-dispatch-result")
    dispatch.add_argument("--state", required=True)
    dispatch.add_argument("--request-id", required=True)
    dispatch.add_argument("--task-id", required=True)
    dispatch.add_argument("--run-id", required=True, type=int)
    dispatch.add_argument("--base-sha", required=True)
    dispatch.add_argument("--plan", required=True)
    dispatch.add_argument("--result", required=True)
    dispatch.add_argument("--pr-number", default="")
    dispatch.add_argument("--head-sha", default="")

    args = parser.parse_args()
    path = Path(args.state)
    state = load_state(path)
    if args.command == "mark-pr":
        state = mark_waiting_ci(state, branch=args.branch, pr_number=args.pr_number, head_sha=args.head_sha)
        save_state(path, state)
        return 0
    if args.command == "mark-ci":
        state = apply_ci_status(state, args.conclusion, args.head_sha)
        save_state(path, state)
        return 0
    if args.command == "mark-failure":
        state = mark_failure(state, reason_code=args.reason_code, config_path=Path(args.config))
        save_state(path, state)
        return 0
    if args.command == "show":
        print(json.dumps(state, indent=2, sort_keys=True))
        return 0
    if args.command == "mark-dispatch-result":
        plan = json.loads(Path(args.plan).read_text(encoding="utf-8"))
        result_path = Path(args.result)
        result = json.loads(result_path.read_text(encoding="utf-8")) if result_path.exists() else None
        state = mark_dispatch_result(
            state, request_id=args.request_id, task_id=args.task_id,
            workflow_run_id=args.run_id, base_main_sha=args.base_sha,
            plan=plan, result=result,
            pr_number=int(args.pr_number) if args.pr_number else None,
            head_sha=args.head_sha or None)
        save_state(path, state)
        return 0
    raise PolicyError("unknown state command")


if __name__ == "__main__":
    raise SystemExit(main())
