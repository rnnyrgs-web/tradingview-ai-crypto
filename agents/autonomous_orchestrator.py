from __future__ import annotations

import argparse
import contextlib
import fnmatch
import io
import json
import os
from pathlib import Path
from typing import Any

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[1]
ROLES_PATH = ROOT / "agents" / "roles.json"
PROTECTED_PATTERNS = (
    "AI_STATE.md",
    "agents/*",
    ".github/workflows/*",
    "requirements.txt",
    "Dockerfile",
)
MAX_FILE_READ_BYTES = 80_000
MAX_FILE_WRITE_BYTES = 120_000
ABSOLUTE_MAX_TOOL_STEPS = 32


def bounded_tool_steps(raw: str | None, default: int = 12) -> int:
    try:
        requested = int(raw) if raw is not None else default
    except (TypeError, ValueError):
        requested = default
    return min(max(requested, 1), ABSOLUTE_MAX_TOOL_STEPS)


MAX_TOOL_STEPS = bounded_tool_steps(os.getenv("AGENT_MAX_STEPS"))


def load_roles() -> dict[str, Any]:
    return json.loads(ROLES_PATH.read_text(encoding="utf-8"))


def normalize_relpath(path: str) -> str:
    candidate = Path(path)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError("unsafe path")
    normalized = candidate.as_posix().lstrip("./")
    if not normalized:
        raise ValueError("empty path")
    return normalized


def path_allowed(role: str, path: str) -> bool:
    try:
        normalized = normalize_relpath(path)
    except ValueError:
        return False
    if any(fnmatch.fnmatch(normalized, pattern) for pattern in PROTECTED_PATTERNS):
        return False
    roles = load_roles()
    if role not in roles:
        return False
    return any(fnmatch.fnmatch(normalized, pattern) for pattern in roles[role]["allowed_paths"])


def list_repo_files() -> list[str]:
    files: list[str] = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or ".git" in path.parts:
            continue
        files.append(path.relative_to(ROOT).as_posix())
    return sorted(files)


def read_file(path: str) -> str:
    normalized = normalize_relpath(path)
    target = ROOT / normalized
    if not target.is_file():
        return "ERROR: file does not exist"
    data = target.read_bytes()
    if len(data) > MAX_FILE_READ_BYTES:
        return f"ERROR: file exceeds {MAX_FILE_READ_BYTES} bytes"
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return "ERROR: file is not UTF-8 text"


def write_file(role: str, path: str, content: str) -> str:
    if not path_allowed(role, path):
        return "ERROR: path is not writable for this role"
    encoded = content.encode("utf-8")
    if len(encoded) > MAX_FILE_WRITE_BYTES:
        return f"ERROR: content exceeds {MAX_FILE_WRITE_BYTES} bytes"
    target = ROOT / normalize_relpath(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(encoded)
    return f"WROTE {target.relative_to(ROOT).as_posix()}"


def run_pytest(args: list[str] | None = None) -> str:
    argv = args or ["-q"]
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer), contextlib.redirect_stderr(buffer):
        code = pytest.main(argv)
    output = buffer.getvalue()
    return f"pytest exit={int(code)}\n{output[-40_000:]}"


def tool_specs() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "name": "list_files",
            "description": "List repository files. Use sparingly and prefer targeted reads.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "type": "function",
            "name": "read_file",
            "description": "Read one UTF-8 repository file by relative path.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}},
                "required": ["path"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "write_file",
            "description": "Write one role-allowlisted UTF-8 repository file by relative path.",
            "parameters": {
                "type": "object",
                "properties": {"path": {"type": "string"}, "content": {"type": "string"}},
                "required": ["path", "content"],
                "additionalProperties": False,
            },
        },
        {
            "type": "function",
            "name": "run_pytest",
            "description": "Run pytest in-process with optional pytest arguments.",
            "parameters": {
                "type": "object",
                "properties": {
                    "args": {"type": "array", "items": {"type": "string"}, "maxItems": 12}
                },
                "additionalProperties": False,
            },
        },
    ]


def call_tool(role: str, name: str, args: dict[str, Any]) -> str:
    if name == "list_files":
        return "\n".join(list_repo_files())
    if name == "read_file":
        return read_file(str(args.get("path", "")))
    if name == "write_file":
        return write_file(role, str(args.get("path", "")), str(args.get("content", "")))
    if name == "run_pytest":
        raw_args = args.get("args")
        pytest_args = [str(item) for item in raw_args] if isinstance(raw_args, list) else None
        return run_pytest(pytest_args)
    return "ERROR: unknown tool"


def model_name() -> str:
    model = os.getenv("OPENAI_AGENT_MODEL", "").strip()
    if not model:
        raise RuntimeError("OPENAI_AGENT_MODEL is not configured")
    return model


def api_headers() -> dict[str, str]:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def post_response(payload: dict[str, Any]) -> dict[str, Any]:
    with httpx.Client(timeout=180.0) as client:
        response = client.post("https://api.openai.com/v1/responses", headers=api_headers(), json=payload)
        response.raise_for_status()
        return response.json()


def response_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    out: list[str] = []
    for item in payload.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            text = content.get("text")
            if isinstance(text, str):
                out.append(text)
    return "\n".join(out)


def extract_json(text: str) -> dict[str, Any]:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    return json.loads(stripped)


def plan_tasks(output: Path) -> int:
    state = read_file("AI_STATE.md")
    external = os.getenv("AGENT_EXTERNAL_CONTEXT", "")[-30_000:]
    roles = load_roles()
    prompt = f"""
You are the Lead Integrator planning one fail-closed autonomous development cycle for a crypto quantitative trading/signalling system.

AUTHORITATIVE AI_STATE.md:\n{state}

RECENT GITHUB CONTEXT:\n{external}

SPECIALIST ROLES:\n{json.dumps(roles, indent=2)}

Return JSON only with this shape:
{{
  "cycle_goal": "...",
  "tasks": {{
    "quant-research": {{"status": "TASK|NO_TASK", "task": "..."}},
    "data-market": {{"status": "TASK|NO_TASK", "task": "..."}},
    "strategy-registry": {{"status": "TASK|NO_TASK", "task": "..."}},
    "production-risk": {{"status": "TASK|NO_TASK", "task": "..."}},
    "testing-security": {{"status": "TASK|NO_TASK", "task": "..."}}
  }}
}}
Rules:
- Use AI_STATE.md as authoritative.
- Assign at most one bounded task per role.
- Respect each role's allowed paths exactly.
- Do not assign edits to AI_STATE.md, agents/, workflows, requirements.txt or Dockerfile.
- Never promote research to live use from one OOS pass.
- Preserve no-lookahead and fail-closed behavior.
- Prefer NO_TASK over speculative or unnecessary work.
- Tasks must be small enough for one specialist cycle and testable with repository evidence.
"""
    payload = post_response({"model": model_name(), "input": prompt})
    plan = extract_json(response_text(payload))
    tasks = plan.get("tasks")
    if not isinstance(tasks, dict) or set(tasks) != set(roles):
        raise RuntimeError("planner returned invalid role set")
    for role, task in tasks.items():
        if not isinstance(task, dict) or task.get("status") not in {"TASK", "NO_TASK"}:
            raise RuntimeError(f"planner returned invalid task for {role}")
        if not isinstance(task.get("task"), str):
            raise RuntimeError(f"planner omitted task text for {role}")
    output.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    return 0


def review_diff(reviewer: str, diff_path: Path, output: Path) -> int:
    if reviewer not in {"lead", "security"}:
        raise RuntimeError("unknown reviewer")
    diff = diff_path.read_text(encoding="utf-8")
    if len(diff.encode("utf-8")) > 80_000:
        raise RuntimeError("diff too large")
    if any(
        marker in diff
        for marker in (
            "diff --git a/AI_STATE.md ",
            "diff --git a/agents/",
            "diff --git a/.github/workflows/",
            "diff --git a/requirements.txt ",
            "diff --git a/Dockerfile ",
        )
    ):
        raise RuntimeError("protected orchestration/state path in diff")

    focus = (
        "security, secret handling, path boundaries, malformed input, fail-closed behavior, and whether tests can be bypassed"
        if reviewer == "security"
        else "correctness, compatibility, no-lookahead, research/live isolation, regression risk, and scope discipline"
    )
    prompt = f"""
You are the independent {reviewer} reviewer for an autonomous crypto trading software change.
Review focus: {focus}.

PROPOSED DIFF:\n{diff}

Return JSON only:
{{"approve": true|false, "reason": "specific evidence-based reason", "risk": "low|medium|high"}}
Approve only if the diff is bounded, internally coherent, does not weaken safety gates, and has no unsupported live-trading claims. When evidence is insufficient, reject.
"""
    response = post_response({"model": model_name(), "input": prompt})
    verdict = extract_json(response_text(response))
    if not isinstance(verdict.get("approve"), bool):
        raise RuntimeError("reviewer returned invalid approval")
    if verdict.get("risk") not in {"low", "medium", "high"}:
        raise RuntimeError("reviewer returned invalid risk")
    output.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan")
    plan.add_argument("--output", required=True)

    review = sub.add_parser("review")
    review.add_argument("--reviewer", choices=("lead", "security"), required=True)
    review.add_argument("--diff", required=True)
    review.add_argument("--output", required=True)

    args = parser.parse_args()
    if args.command == "plan":
        return plan_tasks(Path(args.output))
    if args.command == "review":
        return review_diff(args.reviewer, Path(args.diff), Path(args.output))
    raise RuntimeError("unknown command")


if __name__ == "__main__":
    raise SystemExit(main())
