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
MAX_TOOL_STEPS = int(os.getenv("AGENT_MAX_STEPS", "12"))
MAX_FILE_READ_BYTES = 80_000
MAX_FILE_WRITE_BYTES = 120_000


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
        return "ERROR: path is outside this role's allowlist or is protected"
    encoded = content.encode("utf-8")
    if len(encoded) > MAX_FILE_WRITE_BYTES:
        return f"ERROR: content exceeds {MAX_FILE_WRITE_BYTES} bytes"
    target = ROOT / normalize_relpath(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return "OK"


def run_pytest(target: str = "") -> str:
    args = ["-q"]
    if target:
        normalized = normalize_relpath(target)
        if not normalized.startswith("tests/"):
            return "ERROR: pytest target must be under tests/"
        args.append(normalized)
    stdout = io.StringIO()
    stderr = io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        exit_code = int(pytest.main(args))
    output = stdout.getvalue() + stderr.getvalue()
    return f"exit_code={exit_code}\n{output[-30_000:]}"


def api_headers() -> dict[str, str]:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not key:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    return {"Authorization": f"Bearer {key}", "Content-Type": "application/json"}


def model_name() -> str:
    model = os.getenv("OPENAI_AGENT_MODEL", "").strip()
    if not model:
        raise RuntimeError("OPENAI_AGENT_MODEL is not configured")
    return model


def response_text(payload: dict[str, Any]) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    chunks: list[str] = []
    for item in payload.get("output", []):
        if item.get("type") != "message":
            continue
        for content in item.get("content", []):
            text = content.get("text")
            if isinstance(text, str):
                chunks.append(text)
    return "\n".join(chunks)


def extract_json(text: str) -> Any:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if len(lines) >= 3:
            stripped = "\n".join(lines[1:-1]).strip()
    try:
        return json.loads(stripped)
    except json.JSONDecodeError:
        start_candidates = [i for i in (stripped.find("{"), stripped.find("[")) if i >= 0]
        if not start_candidates:
            raise
        start = min(start_candidates)
        for end in range(len(stripped), start, -1):
            try:
                return json.loads(stripped[start:end])
            except json.JSONDecodeError:
                continue
        raise


def post_response(body: dict[str, Any]) -> dict[str, Any]:
    with httpx.Client(timeout=120.0) as client:
        resp = client.post("https://api.openai.com/v1/responses", headers=api_headers(), json=body)
        resp.raise_for_status()
        return resp.json()


def planning_context() -> str:
    state = read_file("AI_STATE.md")
    external = os.getenv("AGENT_EXTERNAL_CONTEXT", "").strip()
    return f"AI_STATE.md:\n{state}\n\nExternal GitHub context:\n{external}"


def make_plan(output_path: Path) -> None:
    roles = load_roles()
    prompt = f"""
You are the Lead Integrator planner for a crypto quantitative trading/signalling repository.

Authoritative context follows. Respect the EXACT NEXT STEP in AI_STATE.md unless a newer explicit user priority in context supersedes it.

{planning_context()}

Create at most one bounded task for each specialist. Tasks should be independently executable and avoid overlapping files. If a role should do nothing this cycle, set status to NO_TASK. Never ask a specialist to edit AI_STATE.md, agents/, GitHub workflow files, requirements.txt, or Dockerfile. Never permit live weighting of research strategies without repeated robust OOS evidence and a hard registry gate. Missing evidence must fail closed.

Roles and missions:
{json.dumps(roles, indent=2)}

Return JSON only with this exact shape:
{{
  "cycle_goal": "...",
  "tasks": {{
    "quant-research": {{"status":"TASK|NO_TASK","task":"..."}},
    "data-market": {{"status":"TASK|NO_TASK","task":"..."}},
    "strategy-registry": {{"status":"TASK|NO_TASK","task":"..."}},
    "production-risk": {{"status":"TASK|NO_TASK","task":"..."}},
    "testing-security": {{"status":"TASK|NO_TASK","task":"..."}}
  }}
}}
"""
    payload = post_response({"model": model_name(), "input": prompt})
    plan = extract_json(response_text(payload))
    if not isinstance(plan, dict) or not isinstance(plan.get("tasks"), dict):
        raise RuntimeError("planner returned invalid structure")
    for role in roles:
        task = plan["tasks"].get(role)
        if not isinstance(task, dict) or task.get("status") not in {"TASK", "NO_TASK"}:
            raise RuntimeError(f"planner omitted or malformed role: {role}")
    output_path.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")


def tool_specs() -> list[dict[str, Any]]:
    return [
        {
            "type": "function",
            "name": "list_files",
            "description": "List repository files.",
            "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
        },
        {
            "type": "function",
            "name": "read_file",
            "description": "Read one UTF-8 repository file.",
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
            "description": "Write one complete UTF-8 file. Writes are restricted to the role allowlist.",
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
            "description": "Run pytest globally or on one tests/ path.",
            "parameters": {
                "type": "object",
                "properties": {"target": {"type": "string"}},
                "additionalProperties": False,
            },
        },
    ]


def call_tool(role: str, name: str, args: dict[str, Any]) -> str:
    if name == "list_files":
        return "\n".join(list_repo_files())
    if name == "read_file":
        return read_file(str(args["path"]))
    if name == "write_file":
        return write_file(role, str(args["path"]), str(args["content"]))
    if name == "run_pytest":
        return run_pytest(str(args.get("target", "")))
    return "ERROR: unknown tool"


def execute_task(role: str, plan_path: Path) -> int:
    roles = load_roles()
    if role not in roles:
        raise RuntimeError(f"unknown role {role}")
    plan = json.loads(plan_path.read_text(encoding="utf-8"))
    task = plan["tasks"][role]
    if task["status"] == "NO_TASK":
        print("NO_TASK")
        return 0

    instructions = f"""
You are the {role} autonomous specialist in a crypto quantitative trading system.
Mission: {roles[role]['mission']}
Task: {task['task']}

Hard rules:
- Read AI_STATE.md before deciding anything, but never edit it.
- Stay inside the allowed paths for your role: {roles[role]['allowed_paths']}.
- Never edit agents/, .github/workflows/, requirements.txt, Dockerfile, or AI_STATE.md.
- Preserve no-lookahead and fail-closed behavior.
- Never manufacture backtest evidence, prices, workflow results, or live readiness.
- Do not weaken validation/risk/security gates for more signals.
- Make the smallest coherent change that completes the task.
- Add or update tests when appropriate.
- Run pytest before finishing.
- If the task cannot be completed safely with available evidence/files, make no change and explain why.
- Finish with a concise summary containing CHANGE_STATUS: READY_FOR_PR or CHANGE_STATUS: NO_CHANGE.
"""

    initial = post_response({
        "model": model_name(),
        "instructions": instructions,
        "input": "Begin by reading AI_STATE.md and inspecting only the files needed for your task.",
        "tools": tool_specs(),
    })
    current = initial
    for _ in range(MAX_TOOL_STEPS):
        calls = [item for item in current.get("output", []) if item.get("type") == "function_call"]
        if not calls:
            print(response_text(current))
            return 0
        outputs: list[dict[str, Any]] = []
        for call in calls:
            try:
                args = json.loads(call.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            result = call_tool(role, call.get("name", ""), args)
            outputs.append({"type": "function_call_output", "call_id": call["call_id"], "output": result})
        current = post_response({
            "model": model_name(),
            "previous_response_id": current["id"],
            "input": outputs,
            "tools": tool_specs(),
        })
    raise RuntimeError("agent exceeded maximum tool steps; failing closed")


def review_diff(diff_path: Path, reviewer: str) -> dict[str, Any]:
    diff = diff_path.read_text(encoding="utf-8")
    if len(diff) > 80_000:
        raise RuntimeError("diff too large for autonomous review")
    if any(marker in diff for marker in ("AI_STATE.md", ".github/workflows/", "agents/autonomous_orchestrator.py")):
        return {"approve": False, "reason": "protected orchestration/state path changed"}
    lens = "lead integrator" if reviewer == "lead" else "independent testing/security reviewer"
    prompt = f"""
You are the {lens} for a real-money-adjacent crypto trading/signalling repository.
Review this proposed diff adversarially. Reject if it weakens fail-closed behavior, introduces lookahead/data leakage, bypasses OOS/registry gates, creates unsafe production behavior, exposes secrets, lacks necessary tests, or makes claims unsupported by code/evidence.

DIFF:\n{diff}

Return JSON only: {{"approve": true|false, "reason": "brief exact reason", "risk": "LOW|MEDIUM|HIGH"}}
"""
    payload = post_response({"model": model_name(), "input": prompt})
    result = extract_json(response_text(payload))
    if not isinstance(result, dict) or not isinstance(result.get("approve"), bool):
        raise RuntimeError("reviewer returned invalid structure")
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    p_plan = sub.add_parser("plan")
    p_plan.add_argument("--output", required=True)

    p_work = sub.add_parser("work")
    p_work.add_argument("--role", required=True)
    p_work.add_argument("--plan", required=True)

    p_review = sub.add_parser("review")
    p_review.add_argument("--reviewer", choices=["lead", "security"], required=True)
    p_review.add_argument("--diff", required=True)
    p_review.add_argument("--output", required=True)

    args = parser.parse_args()
    if args.command == "plan":
        make_plan(Path(args.output))
        return 0
    if args.command == "work":
        return execute_task(args.role, Path(args.plan))
    if args.command == "review":
        result = review_diff(Path(args.diff), args.reviewer)
        Path(args.output).write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
        print(json.dumps(result))
        return 0
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
