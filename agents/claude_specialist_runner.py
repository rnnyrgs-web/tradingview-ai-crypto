from __future__ import annotations

import argparse
import contextlib
import fnmatch
import io
import json
import os
import time
from pathlib import Path
from typing import Any

import httpx

# Mirrors the import-collision defense in agents/autonomous_cloud_state.py:
# this module is executed both as `python -m agents.claude_specialist_runner`
# and directly as a script, and must not depend on any pip-installed
# top-level `agents` package (this engine uses no SDK -- only httpx -- so the
# collision that forces autonomous_cloud_runner.py's Agents-SDK import to be
# deferred inside a function does not apply here, but the dual-import
# pattern is kept for consistency and because PYTHONPATH is the only thing
# that makes `agents.*` resolve to this repository's agents/ directory).
if __package__:
    from .autonomous_cloud_runner import (
        Decision,
        PolicyError,
        coordination_task,
        iso,
        load_config,
        load_coordination,
        load_json,
        load_state,
        path_allowed,
        plan_decision,
        record_run_result,
        save_state,
        utc_now,
        validate_outcome_dict,
    )
else:
    from autonomous_cloud_runner import (
        Decision,
        PolicyError,
        coordination_task,
        iso,
        load_config,
        load_coordination,
        load_json,
        load_state,
        path_allowed,
        plan_decision,
        record_run_result,
        save_state,
        utc_now,
        validate_outcome_dict,
    )

ROOT = Path(__file__).resolve().parents[1]
CONFIG_PATH = ROOT / "orchestration" / "autonomous_specialist_runner_claude.json"

ANTHROPIC_MAX_ATTEMPTS = 6
ANTHROPIC_BACKOFF_SECONDS = (5, 10, 20, 40, 60)


def _anthropic_headers() -> dict[str, str]:
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise PolicyError("ANTHROPIC_API_KEY is not configured")
    return {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}


def _post_anthropic(payload: dict[str, Any]) -> dict[str, Any]:
    retryable = {408, 409, 429, 500, 502, 503, 504}
    with httpx.Client(timeout=180.0) as client:
        for attempt in range(ANTHROPIC_MAX_ATTEMPTS):
            response: httpx.Response | None = None
            try:
                response = client.post("https://api.anthropic.com/v1/messages", headers=_anthropic_headers(), json=payload)
                if response.status_code not in retryable:
                    response.raise_for_status()
                    return response.json()
                if attempt == ANTHROPIC_MAX_ATTEMPTS - 1:
                    response.raise_for_status()
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt == ANTHROPIC_MAX_ATTEMPTS - 1:
                    raise
            time.sleep(ANTHROPIC_BACKOFF_SECONDS[min(attempt, len(ANTHROPIC_BACKOFF_SECONDS) - 1)])
    raise PolicyError("Anthropic response retry loop exited unexpectedly")


def _current_branch_from_git_head() -> str:
    head = (ROOT / ".git" / "HEAD").read_text(encoding="utf-8").strip()
    prefix = "ref: refs/heads/"
    return head[len(prefix):] if head.startswith(prefix) else ""


def _tool_specs() -> list[dict[str, Any]]:
    return [
        {
            "name": "read_repo_file",
            "description": "Read one bounded UTF-8 repository file; env/secret files are unavailable.",
            "input_schema": {"type": "object", "properties": {"path": {"type": "string"}}, "required": ["path"]},
        },
        {
            "name": "write_repo_file",
            "description": "Write one role-allowlisted file only on the exact isolated task branch.",
            "input_schema": {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
            },
        },
        {
            "name": "run_pytest",
            "description": "Run bounded pytest in-process and return a truncated test result.",
            "input_schema": {"type": "object", "properties": {"args": {"type": "array", "items": {"type": "string"}}}},
        },
        {
            "name": "submit_outcome",
            "description": "Submit the final structured outcome and stop.",
            "input_schema": {
                "type": "object",
                "properties": {
                    "status": {"type": "string", "enum": ["READY_FOR_PR", "NO_CHANGE", "BLOCKED"]},
                    "summary": {"type": "string"},
                    "tests": {"type": "array", "items": {"type": "string"}},
                    "evidence": {"type": "array", "items": {"type": "string"}},
                    "risks": {"type": "array", "items": {"type": "string"}},
                    "changed_files": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["status", "summary"],
            },
        },
    ]


def run_agent(config: dict[str, Any], coordination: dict[str, Any], decision: Decision) -> tuple[dict[str, Any], dict[str, int]]:
    """Bounded Claude research-role tool-use loop.

    Mirrors ``agents.autonomous_cloud_runner.run_agent()``'s sandbox (same
    three read/write/pytest tools, same branch/path enforcement, same
    terminal-status contract validated by ``validate_outcome_dict``) but
    calls the Anthropic Messages API directly with ``tool_use`` instead of
    the OpenAI Agents SDK, so this engine carries no dependency on that SDK
    and cannot collide with its package name.
    """
    if not decision.run or not decision.role or not decision.task_id or not decision.branch:
        raise PolicyError("invalid runnable decision")
    role, expected_branch = decision.role, decision.branch
    task = coordination_task(coordination, decision.task_id)
    if task is None:
        raise PolicyError("owned task disappeared")
    settings = config["roles"][role]

    def read_repo_file(path: str) -> str:
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

    def write_repo_file(path: str, content: str) -> str:
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

    def run_pytest_tool(args: list[str] | None = None) -> str:
        import pytest

        safe = [str(v) for v in (args or ["-q"])]
        if len(safe) > 12 or any(v.startswith("--rootdir") or v.startswith("-c") for v in safe):
            return "ERROR: unsafe pytest arguments"
        buffer = io.StringIO()
        with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
            code = pytest.main(safe)
        return f"pytest exit={int(code)}\n{buffer.getvalue()[-16000:]}"

    tool_impls = {"read_repo_file": read_repo_file, "write_repo_file": write_repo_file, "run_pytest": run_pytest_tool}

    state_text = (ROOT / "AI_STATE.md").read_text(encoding="utf-8")
    protocol_text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    system = (
        f"You are the autonomous {role} research specialist. Mission: {settings['mission']}\n"
        f"Owned task: {json.dumps(task)}\n"
        f"Canonical state:\n{state_text}\n"
        f"Protocol:\n{protocol_text}\n"
        f"Hard rules: work only on {expected_branch} and the owned READY task. "
        "You have no git push, merge, workflow, broker, trading, credential, network, or shell "
        "tool beyond the three provided. Never edit orchestration, agents, workflows, canonical "
        "state/protocol, live promotions, credentials, or paper history -- those paths are "
        "rejected by write_repo_file regardless of what you request. Preserve chronology, "
        "untouched OOS, robustness, multiple-testing protection, point-in-time safety, "
        "genuine-forward requirements, and immutable fingerprints. Never fabricate data or "
        "evidence. Missing evidence is BLOCKED/NO_CHANGE/RESEARCH_ONLY. "
        "READY_FOR_PR only means candidate for deterministic tests and manual Lead review; it "
        "never authorizes merge or live trading. Call submit_outcome exactly once when done."
    )

    messages: list[dict[str, Any]] = [
        {
            "role": "user",
            "content": "Complete the owned task now with the smallest scientifically safe change and "
            "relevant tests, or return NO_CHANGE/BLOCKED via submit_outcome.",
        }
    ]
    max_turns = int(settings["max_turns"])
    total_input = total_output = total_cached = 0
    for _ in range(max_turns):
        payload = {
            "model": settings["model"],
            "max_tokens": int(settings["max_output_tokens_per_turn"]),
            "system": system,
            "messages": messages,
            "tools": _tool_specs(),
        }
        response = _post_anthropic(payload)
        usage = response.get("usage", {})
        total_input += int(usage.get("input_tokens", 0) or 0)
        total_output += int(usage.get("output_tokens", 0) or 0)
        total_cached += int(usage.get("cache_read_input_tokens", 0) or 0)
        content_blocks = response.get("content", [])
        messages.append({"role": "assistant", "content": content_blocks})
        tool_uses = [b for b in content_blocks if isinstance(b, dict) and b.get("type") == "tool_use"]
        if not tool_uses:
            break
        tool_results = []
        submitted: dict[str, Any] | None = None
        for call in tool_uses:
            name = call.get("name")
            call_input = call.get("input") or {}
            if name == "submit_outcome":
                submitted = call_input
                result_text = "recorded"
            elif name in tool_impls:
                try:
                    result_text = tool_impls[name](**call_input)
                except TypeError:
                    result_text = "ERROR: malformed tool call"
            else:
                result_text = "ERROR: unknown tool"
            tool_results.append({"type": "tool_result", "tool_use_id": call.get("id"), "content": str(result_text)})
        if submitted is not None:
            outcome = validate_outcome_dict(
                {
                    "status": submitted.get("status"),
                    "summary": submitted.get("summary", ""),
                    "tests": submitted.get("tests", []),
                    "evidence": submitted.get("evidence", []),
                    "risks": submitted.get("risks", []),
                    "changed_files": submitted.get("changed_files", []),
                }
            )
            return outcome, {"input_tokens": total_input, "output_tokens": total_output, "cached_input_tokens": total_cached}
        messages.append({"role": "user", "content": tool_results})
    raise PolicyError("Claude research runner exceeded its turn budget without calling submit_outcome")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    plan = sub.add_parser("plan")
    plan.add_argument("--state", required=True)
    plan.add_argument("--main-sha", required=True)
    plan.add_argument("--output", required=True)
    execute = sub.add_parser("execute")
    execute.add_argument("--state", required=True)
    execute.add_argument("--decision", required=True)
    execute.add_argument("--output", required=True)
    args = parser.parse_args()

    config = load_config(CONFIG_PATH)
    if args.command == "validate":
        print("claude specialist runner: valid")
        return 0
    coordination = load_coordination()
    if args.command == "plan":
        path = Path(args.state)
        state = load_state(path)
        decision = plan_decision(config, coordination, state, args.main_sha, utc_now())
        state["last_seen_main_sha"] = args.main_sha
        save_state(path, state)
        Path(args.output).write_text(json.dumps(decision.as_dict(), indent=2) + "\n", encoding="utf-8")
        print(json.dumps(decision.as_dict(), separators=(",", ":")))
        return 0

    path = Path(args.state)
    state = load_state(path)
    decision = Decision(**load_json(Path(args.decision)))
    if not decision.run:
        raise PolicyError("execute called for non-runnable decision")
    now = utc_now()
    state["active_task"] = {
        "role": decision.role,
        "task_id": decision.task_id,
        "branch": decision.branch,
        "phase": "RUNNING",
        "base_main_sha": state.get("last_seen_main_sha"),
        "started_at": iso(now),
    }
    save_state(path, state)
    outcome, usage = run_agent(config, coordination, decision)
    state = record_run_result(config, state, decision, outcome, usage, utc_now())
    if outcome["status"] in {"NO_CHANGE", "BLOCKED"}:
        state["active_task"] = None
    save_state(path, state)
    Path(args.output).write_text(json.dumps({"outcome": outcome, "usage": usage}, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"status": outcome["status"], "task_id": decision.task_id}, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
