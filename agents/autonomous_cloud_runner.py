from __future__ import annotations

import argparse
import contextlib
import copy
import fnmatch
import io
import json
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "orchestration" / "autonomous_specialist_runner.json"
COORDINATION_PATH = ROOT / "orchestration" / "specialist_coordination.json"
PROTECTED_PATHS = (
    "AI_STATE.md", "AGENTS.md", "docs/CHATGPT_SPECIALISTS.md", "agents/*",
    "orchestration/*", ".github/workflows/*", "requirements.txt", "Dockerfile",
    "live_promotions.json", ".env*", "**/.env*",
)
TERMINAL_AGENT_STATUSES = {"READY_FOR_PR", "NO_CHANGE", "BLOCKED"}
RUNNING_RECOVERY_MINUTES = 60


class PolicyError(RuntimeError):
    pass


@dataclass(frozen=True)
class Decision:
    run: bool
    reason: str
    role: str | None = None
    task_id: str | None = None
    branch: str | None = None
    reserved_cost_usd: float = 0.0

    def as_dict(self) -> dict[str, Any]:
        return {
            "run": self.run, "reason": self.reason, "role": self.role,
            "task_id": self.task_id, "branch": self.branch,
            "reserved_cost_usd": round(self.reserved_cost_usd, 8),
        }


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def parse_iso(value: str | None) -> datetime | None:
    return None if not value else datetime.fromisoformat(value.replace("Z", "+00:00")).astimezone(timezone.utc)


def load_json(path: Path) -> dict[str, Any]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise PolicyError(f"{path.name} must contain an object")
    return payload


def load_config(path: Path = CONFIG_PATH) -> dict[str, Any]:
    config = load_json(path)
    validate_config(config)
    return config


def load_coordination(path: Path = COORDINATION_PATH) -> dict[str, Any]:
    payload = load_json(path)
    if not isinstance(payload.get("roles"), dict) or not isinstance(payload.get("tasks"), list):
        raise PolicyError("specialist coordination state is malformed")
    return payload


def default_state() -> dict[str, Any]:
    return {"version": 1, "runs": [], "active_task": None, "next_eligible_at": None,
            "paused_reason": None, "last_seen_main_sha": None, "task_failures": {}}


def load_state(path: Path) -> dict[str, Any]:
    if not path.exists():
        return default_state()
    state = load_json(path)
    if state.get("version") != 1 or not isinstance(state.get("runs"), list):
        raise PolicyError("runner state is malformed")
    state.setdefault("task_failures", {})
    return state


def save_state(path: Path, state: dict[str, Any]) -> None:
    path.write_text(json.dumps(state, indent=2, sort_keys=True) + "\n", encoding="utf-8")


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
        if int(settings.get("max_turns", 999)) > 4 or int(settings.get("max_output_tokens_per_turn", 999999)) > 2000:
            raise PolicyError("v1 turn/token ceiling exceeded")


def cost_usd(config: dict[str, Any], model: str, input_tokens: int, output_tokens: int, cached_input_tokens: int = 0) -> float:
    p = config["models"][model]
    cached = max(0, min(int(cached_input_tokens), int(input_tokens)))
    uncached = max(0, int(input_tokens) - cached)
    return (uncached * float(p["input_usd_per_million"]) + cached * float(p["cached_input_usd_per_million"]) + int(output_tokens) * float(p["output_usd_per_million"])) / 1_000_000


def reserved_cost_usd(config: dict[str, Any], role: str) -> float:
    s = config["roles"][role]
    return cost_usd(config, s["model"], int(s["reserved_max_input_tokens_per_run"]), int(s["reserved_max_output_tokens_per_run"]))


def spend_since(state: dict[str, Any], start: datetime) -> float:
    total = 0.0
    for row in state.get("runs", []):
        when = parse_iso(row.get("finished_at") or row.get("started_at"))
        if when and when >= start:
            total += float(row.get("actual_cost_usd", 0) or 0)
    return total


def day_start(now: datetime) -> datetime:
    return now.astimezone(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)


def month_start(now: datetime) -> datetime:
    return now.astimezone(timezone.utc).replace(day=1, hour=0, minute=0, second=0, microsecond=0)


def budget_gate(config: dict[str, Any], state: dict[str, Any], role: str, now: datetime) -> tuple[bool, str, float]:
    raw_reserve, b = reserved_cost_usd(config, role), config["budget"]
    reserve = raw_reserve * float(b.get("provider_retry_safety_multiplier", 1.0))
    daily, monthly = spend_since(state, day_start(now)), spend_since(state, month_start(now))
    if daily + reserve > float(b["runner_daily_api_budget_usd"]):
        return False, "DAILY_API_BUDGET", reserve
    if monthly + reserve > float(b["runner_monthly_api_budget_usd"]):
        return False, "MONTHLY_API_BUDGET", reserve
    projected = float(b["baseline_infrastructure_reserve_usd"]) + monthly + reserve + float(b["pause_buffer_usd"])
    if projected > float(b["project_monthly_ceiling_usd"]):
        return False, "PROJECT_MONTHLY_CEILING", reserve
    return True, "OK", reserve


def retry_delay_seconds(config: dict[str, Any], retry_index: int) -> int:
    if retry_index < 0:
        raise PolicyError("retry index cannot be negative")
    return min(int(config["policy"]["retry_cap_seconds"]), int(config["policy"]["retry_base_seconds"]) * (2 ** retry_index))


def safe_branch(role: str, task_id: str) -> str:
    branch = f"auto/{role.strip().lower()}/{task_id.strip().lower().replace('_', '-')}"
    validate_branch(branch, role, task_id)
    return branch


def validate_branch(branch: str, role: str, task_id: str) -> None:
    if branch in {"main", "master"} or not branch.startswith(f"auto/{role}/") or task_id.lower().replace("_", "-") not in branch:
        raise PolicyError("specialist branch isolation violation")


def validate_action(action: str, actor_role: str, target: str | None = None) -> None:
    if action in {"merge_pr", "enable_auto_merge", "trade", "place_order", "connect_broker"}:
        raise PolicyError(f"forbidden autonomous action: {action}")
    if action in {"push", "write_branch"} and target in {"main", "master"}:
        raise PolicyError("specialist cannot write main")
    if action == "merge_own_pr":
        raise PolicyError(f"specialist {actor_role} cannot merge its own PR")


def path_allowed(config: dict[str, Any], role: str, path: str) -> bool:
    candidate = Path(path)
    if candidate.is_absolute() or ".." in candidate.parts:
        return False
    normalized = candidate.as_posix().lstrip("./")
    if not normalized or any(fnmatch.fnmatch(normalized, p) for p in PROTECTED_PATHS):
        return False
    return any(fnmatch.fnmatch(normalized, p) for p in config["roles"][role]["allowed_paths"])


def validate_outcome_dict(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict) or payload.get("status") not in TERMINAL_AGENT_STATUSES:
        raise PolicyError("malformed agent output")
    if not isinstance(payload.get("summary"), str) or not payload["summary"].strip():
        raise PolicyError("agent summary missing")
    for key in ("tests", "evidence", "risks", "changed_files"):
        if not isinstance(payload.get(key), list) or not all(isinstance(v, str) for v in payload[key]):
            raise PolicyError(f"agent output field {key} malformed")
    return payload


def coordination_task(coordination: dict[str, Any], task_id: str) -> dict[str, Any] | None:
    return next((t for t in coordination["tasks"] if t.get("id") == task_id), None)


def recover_state(state: dict[str, Any], coordination: dict[str, Any], now: datetime) -> dict[str, Any]:
    recovered = copy.deepcopy(state)
    active = recovered.get("active_task")
    if not isinstance(active, dict):
        return recovered
    task = coordination_task(coordination, str(active.get("task_id", "")))
    if task is None or task.get("status") == "DONE":
        recovered["active_task"], recovered["paused_reason"] = None, None
        return recovered
    if active.get("phase") == "RUNNING":
        started = parse_iso(active.get("started_at"))
        if started and now - started >= timedelta(minutes=RUNNING_RECOVERY_MINUTES):
            recovered["active_task"] = None
    return recovered


def highest_ready_task(config: dict[str, Any], coordination: dict[str, Any]) -> dict[str, Any] | None:
    roles = set(config["autonomous_roles"])
    candidates = [t for t in coordination["tasks"] if t.get("owner") in roles and t.get("status") == "READY" and not t.get("blockers")]
    return min(candidates, key=lambda t: (int(t.get("priority", 999999)), str(t.get("id", ""))), default=None)


def plan_decision(config: dict[str, Any], coordination: dict[str, Any], state: dict[str, Any], current_main_sha: str, now: datetime) -> Decision:
    if not config.get("enabled"):
        return Decision(False, "RUNNER_DISABLED")
    state = recover_state(state, coordination, now)
    active = state.get("active_task")
    if isinstance(active, dict):
        return Decision(False, "STALE_MAIN_WITH_ACTIVE_TASK" if active.get("base_main_sha") != current_main_sha else f"ACTIVE_TASK_{active.get('phase', 'UNKNOWN')}")
    eligible = parse_iso(state.get("next_eligible_at"))
    if eligible and now < eligible:
        return Decision(False, "COOLDOWN")
    task = highest_ready_task(config, coordination)
    if task is None:
        return Decision(False, "NO_READY_AUTONOMOUS_TASK")
    role = str(task["owner"])
    if task.get("branch") != coordination["roles"].get(role, {}).get("branch"):
        return Decision(False, "COORDINATION_BRANCH_MISMATCH")
    ok, reason, reserve = budget_gate(config, state, role, now)
    if not ok:
        return Decision(False, reason, role, str(task["id"]), reserved_cost_usd=reserve)
    return Decision(True, "READY", role, str(task["id"]), safe_branch(role, str(task["id"])), reserve)


def apply_ci_status(state: dict[str, Any], conclusion: str, exact_head_sha: str | None = None) -> dict[str, Any]:
    updated = copy.deepcopy(state)
    active = updated.get("active_task")
    if not isinstance(active, dict) or active.get("phase") != "WAITING_CI":
        raise PolicyError("CI status can only update WAITING_CI task")
    if exact_head_sha and active.get("head_sha") and exact_head_sha != active.get("head_sha"):
        active["phase"], active["ci_reason"] = "CI_FAILED", "STALE_CI_HEAD"
    elif conclusion == "success":
        active["phase"], active["ci_status"] = "WAITING_LEAD", "success"
    elif conclusion in {"failure", "cancelled", "timed_out", "action_required"}:
        active["phase"], active["ci_status"] = "CI_FAILED", conclusion
    else:
        active["ci_status"] = conclusion
    return updated


def run_with_retries(operation: Callable[[], Any], config: dict[str, Any], sleep_fn: Callable[[float], None] = time.sleep) -> Any:
    for attempt in range(int(config["policy"]["max_retries"]) + 1):
        try:
            return operation()
        except Exception:
            if attempt >= int(config["policy"]["max_retries"]):
                raise
            sleep_fn(retry_delay_seconds(config, attempt))
    raise PolicyError("retry loop exited unexpectedly")


def _current_branch_from_git_head() -> str:
    head = (ROOT / ".git" / "HEAD").read_text(encoding="utf-8").strip()
    prefix = "ref: refs/heads/"
    return head[len(prefix):] if head.startswith(prefix) else ""


def _usage(result: Any) -> tuple[int, int, int]:
    usage = getattr(getattr(result, "context_wrapper", None), "usage", None)
    if usage is None:
        raise PolicyError("Agents SDK result did not expose usage")
    details = getattr(usage, "input_tokens_details", None)
    return int(getattr(usage, "input_tokens", 0) or 0), int(getattr(usage, "output_tokens", 0) or 0), int(getattr(details, "cached_tokens", 0) or 0) if details else 0


def run_agent(config: dict[str, Any], coordination: dict[str, Any], decision: Decision) -> tuple[dict[str, Any], dict[str, int]]:
    from agents import Agent, ModelSettings, Runner, function_tool
    from pydantic import BaseModel, Field
    from typing import Literal

    if not decision.run or not decision.role or not decision.task_id or not decision.branch:
        raise PolicyError("invalid runnable decision")
    role, expected_branch = decision.role, decision.branch
    task = coordination_task(coordination, decision.task_id)
    if task is None:
        raise PolicyError("owned task disappeared")
    settings = config["roles"][role]

    class Outcome(BaseModel):
        status: Literal["READY_FOR_PR", "NO_CHANGE", "BLOCKED"]
        summary: str = Field(min_length=1, max_length=4000)
        tests: list[str] = Field(default_factory=list, max_length=20)
        evidence: list[str] = Field(default_factory=list, max_length=30)
        risks: list[str] = Field(default_factory=list, max_length=20)
        changed_files: list[str] = Field(default_factory=list, max_length=30)

    @function_tool
    def read_repo_file(path: str) -> str:
        """Read one bounded UTF-8 repository file; env/secret files are unavailable."""
        candidate = Path(path)
        if candidate.is_absolute() or ".." in candidate.parts:
            return "ERROR: unsafe path"
        normalized = candidate.as_posix().lstrip("./")
        if any(fnmatch.fnmatch(normalized, p) for p in (".env*", "**/.env*", ".git/*")):
            return "ERROR: protected path"
        target = ROOT / normalized
        try:
            data = target.read_bytes()
            if not target.is_file() or len(data) > int(settings["max_file_read_bytes"]):
                return "ERROR: unavailable or too large"
            return data.decode("utf-8")
        except (OSError, UnicodeDecodeError):
            return "ERROR: unavailable or too large"

    @function_tool
    def write_repo_file(path: str, content: str) -> str:
        """Write one role-allowlisted file only on the exact isolated task branch."""
        if _current_branch_from_git_head() != expected_branch:
            raise PolicyError("working tree is not isolated task branch")
        if not path_allowed(config, role, path):
            return "ERROR: path is not writable for this role"
        data = content.encode("utf-8")
        if len(data) > int(settings["max_file_write_bytes"]):
            return "ERROR: content exceeds write limit"
        target = ROOT / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        return f"WROTE {target.relative_to(ROOT).as_posix()}"

    @function_tool
    def run_pytest(args: list[str] | None = None) -> str:
        """Run bounded pytest in-process and return a truncated test result."""
        import pytest
        safe = [str(v) for v in (args or ["-q"])]
        if len(safe) > 12 or any(v.startswith("--rootdir") or v.startswith("-c") for v in safe):
            return "ERROR: unsafe pytest arguments"
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            code = pytest.main(safe)
        return f"pytest exit={int(code)}\n{buffer.getvalue()[-16000:]}"

    state_text = (ROOT / "AI_STATE.md").read_text(encoding="utf-8")
    protocol = (ROOT / "AGENTS.md").read_text(encoding="utf-8") + "\n" + (ROOT / "docs/CHATGPT_SPECIALISTS.md").read_text(encoding="utf-8")
    instructions = f"""You are the autonomous {role} specialist. Mission: {settings['mission']}\nOwned task: {json.dumps(task)}\nCanonical state:\n{state_text}\nProtocol:\n{protocol}\nHard rules: work only on {expected_branch} and the owned READY task. You have no git push, merge, workflow, broker, trading, credential, network or shell tool. Never edit orchestration, agents, workflows, canonical state/protocol, live promotions, credentials or paper history. Preserve chronology, untouched OOS, robustness, multiple-testing protection, point-in-time safety, genuine-forward requirements, execution/risk gates and immutable fingerprints. Never fabricate data/evidence. Missing evidence is BLOCKED/NO_CHANGE/RESEARCH_ONLY. Do not change production thresholds or claim profitability without canonical proof. READY_FOR_PR only means candidate for deterministic tests and manual Lead review; it never authorizes merge or live trading."""
    agent = Agent(name=f"{role} autonomous specialist", instructions=instructions, model=settings["model"],
                  model_settings=ModelSettings(max_tokens=int(settings["max_output_tokens_per_turn"]), parallel_tool_calls=False, include_usage=True),
                  tools=[read_repo_file, write_repo_file, run_pytest], output_type=Outcome)
    result = run_with_retries(lambda: Runner.run_sync(agent, "Complete the owned task now with the smallest scientifically safe change and relevant tests.", max_turns=int(settings["max_turns"])), config)
    raw = result.final_output.model_dump() if hasattr(result.final_output, "model_dump") else result.final_output
    outcome = validate_outcome_dict(raw)
    inp, out, cached = _usage(result)
    return outcome, {"input_tokens": inp, "output_tokens": out, "cached_input_tokens": cached}


def record_run_result(config: dict[str, Any], state: dict[str, Any], decision: Decision, outcome: dict[str, Any], usage: dict[str, int], now: datetime) -> dict[str, Any]:
    updated = copy.deepcopy(state)
    actual = cost_usd(config, config["roles"][decision.role]["model"], usage["input_tokens"], usage["output_tokens"], usage.get("cached_input_tokens", 0))
    updated.setdefault("runs", []).append({"started_at": (updated.get("active_task") or {}).get("started_at", iso(now)), "finished_at": iso(now), "role": decision.role, "task_id": decision.task_id, "model": config["roles"][decision.role]["model"], "status": outcome["status"], "input_tokens": usage["input_tokens"], "cached_input_tokens": usage.get("cached_input_tokens", 0), "output_tokens": usage["output_tokens"], "reserved_cost_usd": round(decision.reserved_cost_usd, 8), "actual_cost_usd": round(actual, 8)})
    updated["next_eligible_at"] = iso(now + timedelta(hours=float(config["policy"]["successful_run_cooldown_hours"])))
    if actual > decision.reserved_cost_usd + 1e-9:
        updated["paused_reason"] = "USAGE_EXCEEDED_RESERVATION"
    return updated


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    val = sub.add_parser("validate"); val.add_argument("--config", default=str(CONFIG_PATH))
    plan = sub.add_parser("plan"); plan.add_argument("--state", required=True); plan.add_argument("--main-sha", required=True); plan.add_argument("--output", required=True)
    execute = sub.add_parser("execute"); execute.add_argument("--state", required=True); execute.add_argument("--decision", required=True); execute.add_argument("--output", required=True)
    args = parser.parse_args()
    config = load_config(Path(getattr(args, "config", CONFIG_PATH)))
    if args.command == "validate":
        print("autonomous specialist runner: valid"); return 0
    coordination = load_coordination()
    if args.command == "plan":
        path = Path(args.state); state = recover_state(load_state(path), coordination, utc_now())
        decision = plan_decision(config, coordination, state, args.main_sha, utc_now())
        state["last_seen_main_sha"] = args.main_sha; save_state(path, state)
        Path(args.output).write_text(json.dumps(decision.as_dict(), indent=2) + "\n", encoding="utf-8")
        print(json.dumps(decision.as_dict(), separators=(",", ":"))); return 0
    path = Path(args.state); state = load_state(path); decision = Decision(**load_json(Path(args.decision)))
    if not decision.run:
        raise PolicyError("execute called for non-runnable decision")
    now = utc_now(); state["active_task"] = {"role": decision.role, "task_id": decision.task_id, "branch": decision.branch, "phase": "RUNNING", "base_main_sha": state.get("last_seen_main_sha"), "started_at": iso(now)}; save_state(path, state)
    outcome, usage = run_agent(config, coordination, decision); state = record_run_result(config, state, decision, outcome, usage, utc_now())
    if outcome["status"] in {"NO_CHANGE", "BLOCKED"}:
        state["active_task"] = None
    save_state(path, state); Path(args.output).write_text(json.dumps({"outcome": outcome, "usage": usage}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": outcome["status"], "task_id": decision.task_id}, separators=(",", ":"))); return 0


if __name__ == "__main__":
    raise SystemExit(main())
