from __future__ import annotations

import argparse
import copy
import json
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
        PolicyError,
        apply_ci_status,
        iso,
        load_config,
        load_state,
        reserved_cost_usd,
        retry_delay_seconds,
        save_state,
        utc_now,
    )
else:
    from autonomous_cloud_runner import (
        PolicyError,
        apply_ci_status,
        iso,
        load_config,
        load_state,
        reserved_cost_usd,
        retry_delay_seconds,
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


def mark_failure(state: dict, *, reason_code: str) -> dict:
    config = load_config()
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

    show = sub.add_parser("show")
    show.add_argument("--state", required=True)

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
        state = mark_failure(state, reason_code=args.reason_code)
        save_state(path, state)
        return 0
    if args.command == "show":
        print(json.dumps(state, indent=2, sort_keys=True))
        return 0
    raise PolicyError("unknown state command")


if __name__ == "__main__":
    raise SystemExit(main())