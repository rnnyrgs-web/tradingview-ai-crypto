from __future__ import annotations

import argparse
import fnmatch
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

CONFIG_PATH = Path("orchestration/autonomous_specialist_runner.json")
COORDINATION_PATH = Path("orchestration/specialist_coordination.json")
PROTECTED_PATHS_PATH = Path("orchestration/protected_paths.json")


class PolicyError(RuntimeError):
    pass


def _now_utc() -> datetime:
    return datetime.now(timezone.utc)


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def default_state() -> dict[str, Any]:
    return {
        "version": 1,
        "active_task": None,
        "last_success_at": None,
        "paused_reason": None,
        "monthly_spend_usd": 0.0,
        "daily_spend_usd": 0.0,
        "daily_spend_date": None,
        "failures": [],
    }


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    config = json.loads(path.read_text())
    validate_config(config)
    return config


def load_coordination(path: Path = COORDINATION_PATH) -> dict[str, Any]:
    return json.loads(path.read_text())


def validate_config(config: dict[str, Any]) -> None:
    policy, budget = config.get("policy"), config.get("budget")
    roles, models = config.get("roles"), config.get("models")
    if not all(isinstance(v, dict) for v in (policy, budget, roles, models)):
        raise PolicyError("runner config sections are missing")
    if policy.get("max_concurrent_agent_runs") != 1 or policy.get("max_agent_runs_per_invocation") != 1:
        raise PolicyError("v1 runner must remain single-agent and single-run")
    for field in ("specialists_write_main", "specialists_merge_own_prs", "automatic_merge", "trade_authority", "broker_connected"):
        if policy.get(field) is not False:
            raise PolicyError(f"unsafe runner policy: {field}")
    if policy.get("coordination_updates") != "LEAD_ONLY":
        raise PolicyError("coordination changes must remain Lead-only")
    if policy.get("state_branch") in {"main", "master"}:
        raise PolicyError("runner state branch must not be main")
    if float(budget.get("project_monthly_ceiling_usd", -1)) != 30.0:
        raise PolicyError("project monthly ceiling must remain USD 30")
    if sum(float(budget[k]) for k in ("baseline_infrastructure_reserve_usd", "runner_monthly_api_budget_usd", "pause_buffer_usd")) > 30:
        raise PolicyError("configured reserve can exceed project ceiling")
    autonomous = config.get("autonomous_roles")
    if not isinstance(autonomous, list) or len(autonomous) != 1 or set(autonomous) != set(roles):
        raise PolicyError("v1 must configure exactly one autonomous role")
    for role, settings in roles.items():
        model = settings.get("model")
        if model not in models or models[model].get("enabled") is not True:
            raise PolicyError(f"role {role} uses unavailable model")
        # Keep the runner tightly bounded, but allow the Claude Code specialist
        # enough turns to complete one small implementation-and-test cycle.
        if int(settings.get("max_turns", 999)) > 8 or int(settings.get("max_output_tokens_per_turn", 999999)) > 2000:
            raise PolicyError("v1 turn/token ceiling exceeded")


def cost_usd(config: dict[str, Any], model: str, input_tokens: int, output_tokens: int, cached_input_tokens: int = 0) -> float:
    p = config["models"][model]
    cached = max(0, min(int(cached_input_tokens), int(input_tokens)))
    uncached = max(0, int(input_tokens) - cached)
    return (uncached * float(p["input_usd_per_million"]) + cached * float(p["cached_input_usd_per_million"]) + int(output_tokens) * float(p["output_usd_per_million"])) / 1_000_000


def reserved_cost_usd(config: dict[str, Any], role: str) -> float:
    s = config["roles"][role]
    return cost_usd(config, s["model"], int(s["reserved_max_input_tokens_per_run"]), int(s["reserved_max_output_tokens_per_run"]))


def load_protected_paths(path: Path = PROTECTED_PATHS_PATH) -> list[str]:
    data = json.loads(path.read_text())
    return list(data.get("protected_paths", []))


def path_allowed(config: dict[str, Any], role: str, path: str) -> bool:
    normalized = path.replace("\\", "/")
    if any(fnmatch.fnmatch(normalized, pattern) for pattern in load_protected_paths()):
        return False
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in config["roles"][role].get("allowed_paths", []))


def coordination_task(coordination: dict[str, Any], task_id: str) -> dict[str, Any]:
    for task in coordination.get("tasks", []):
        if task.get("id") == task_id:
            return task
    raise PolicyError(f"coordination task not found: {task_id}")


def _fresh_daily_spend(state: dict[str, Any], now: datetime) -> float:
    return float(state.get("daily_spend_usd", 0.0)) if state.get("daily_spend_date") == now.date().isoformat() else 0.0


def plan_decision(config: dict[str, Any], coordination: dict[str, Any], state: dict[str, Any], main_sha: str, now: datetime | None = None) -> dict[str, Any]:
    now = now or _now_utc()
    if not config.get("enabled", False):
        return {"run": False, "reason": "RUNNER_DISABLED"}
    if state.get("active_task"):
        return {"run": False, "reason": "ACTIVE_TASK_PRESENT"}
    last_success = _parse_time(state.get("last_success_at"))
    cooldown_hours = float(config["policy"].get("successful_run_cooldown_hours", 0))
    if last_success and (now - last_success).total_seconds() < cooldown_hours * 3600:
        return {"run": False, "reason": "SUCCESS_COOLDOWN"}

    for task in coordination.get("tasks", []):
        if task.get("owner") not in config["autonomous_roles"] or task.get("status") != "READY":
            continue
        role = task["owner"]
        reservation = reserved_cost_usd(config, role)
        budget = config["budget"]
        if float(state.get("monthly_spend_usd", 0.0)) + reservation > float(budget["runner_monthly_api_budget_usd"]):
            return {"run": False, "reason": "MONTHLY_BUDGET_LIMIT"}
        if _fresh_daily_spend(state, now) + reservation > float(budget["runner_daily_api_budget_usd"]):
            return {"run": False, "reason": "DAILY_BUDGET_LIMIT"}
        branch = f"{config['policy']['task_branch_prefix']}{role}/{task['id'].lower()}"
        return {
            "run": True,
            "reason": "READY",
            "role": role,
            "task_id": task["id"],
            "branch": branch,
            "reserved_cost_usd": reservation,
            "main_sha": main_sha,
        }
    return {"run": False, "reason": "NO_READY_TASK"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    plan = sub.add_parser("plan")
    plan.add_argument("--state", required=True)
    plan.add_argument("--main-sha", required=True)
    plan.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    config = load_config()
    if args.command == "validate":
        print("autonomous cloud runner: valid")
        return 0

    state_path = Path(args.state)
    state = json.loads(state_path.read_text()) if state_path.exists() else default_state()
    decision = plan_decision(config, load_coordination(), state, args.main_sha)
    Path(args.output).write_text(json.dumps(decision, indent=2, sort_keys=True))
    print(json.dumps(decision, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
