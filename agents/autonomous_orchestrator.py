from __future__ import annotations

import argparse
import contextlib
import fnmatch
import io
import json
import os
import re
import time
from pathlib import Path
from typing import Any

import httpx
import pytest

from orchestration.protected_paths import find_protected_matches, load_protected_paths

ROOT = Path(__file__).resolve().parents[1]
ROLES_PATH = ROOT / "agents" / "roles.json"
# Sourced from orchestration/protected_paths.json so this list cannot drift
# from the one agents/autonomous_cloud_runner.py enforces at candidate
# generation time. See BUG_REGRESSION_LEDGER.md PROTECT-PATH-001.
PROTECTED_PATTERNS = load_protected_paths()
MAX_FILE_READ_BYTES = 80_000
MAX_FILE_WRITE_BYTES = 120_000
ABSOLUTE_MAX_TOOL_STEPS = 32
OPENAI_MAX_ATTEMPTS = 6
OPENAI_BACKOFF_SECONDS = (5, 10, 20, 40, 60)
MAX_ACTIVE_TASKS_PER_CYCLE = 14
MAX_CHANGE_TASKS_PER_CYCLE = 1


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
                "properties": {"args": {"type": "array", "items": {"type": "string"}, "maxItems": 12}},
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


def _retry_delay(response: httpx.Response | None, attempt: int) -> float:
    if response is not None:
        raw = response.headers.get("retry-after", "").strip()
        try:
            delay = float(raw)
            if delay > 0:
                return min(delay, 120.0)
        except ValueError:
            pass
    return float(OPENAI_BACKOFF_SECONDS[min(attempt, len(OPENAI_BACKOFF_SECONDS) - 1)])


def post_response(payload: dict[str, Any]) -> dict[str, Any]:
    retryable_statuses = {408, 409, 429, 500, 502, 503, 504}
    with httpx.Client(timeout=180.0) as client:
        for attempt in range(OPENAI_MAX_ATTEMPTS):
            response: httpx.Response | None = None
            try:
                response = client.post("https://api.openai.com/v1/responses", headers=api_headers(), json=payload)
                if response.status_code == 429:
                    try:
                        body = response.json()
                    except ValueError:
                        body = None
                    error = body.get("error") if isinstance(body, dict) else None
                    if isinstance(error, dict) and (
                        error.get("type") == "insufficient_quota"
                        or error.get("code") in (
                            "insufficient_quota", "credit_balance_exhausted",
                            "organization_usage_limit_exceeded",
                            "organization_spend_limit_exceeded", "project_spend_limit_exceeded",
                        )
                    ):
                        # Do not echo provider bodies or label a spend limit as
                        # transient capacity: retries cannot restore this access.
                        raise RuntimeError("OpenAI quota exhausted: account/budget action required; no automatic retry")
                if response.status_code not in retryable_statuses:
                    response.raise_for_status()
                    return response.json()
                if attempt == OPENAI_MAX_ATTEMPTS - 1:
                    response.raise_for_status()
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt == OPENAI_MAX_ATTEMPTS - 1:
                    raise
            time.sleep(_retry_delay(response, attempt))
    raise RuntimeError("OpenAI response retry loop exited unexpectedly")


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


def anthropic_model() -> str:
    model = os.getenv("ANTHROPIC_REVIEW_MODEL", "").strip()
    if not model:
        raise RuntimeError("ANTHROPIC_REVIEW_MODEL is not configured")
    return model


def anthropic_headers() -> dict[str, str]:
    key = os.getenv("ANTHROPIC_API_KEY", "").strip()
    if not key:
        raise RuntimeError("ANTHROPIC_API_KEY is not configured")
    return {"x-api-key": key, "anthropic-version": "2023-06-01", "content-type": "application/json"}


def post_anthropic_message(system: str, user: str, *, max_tokens: int = 1500) -> dict[str, Any]:
    retryable_statuses = {408, 409, 429, 500, 502, 503, 504}
    payload = {"model": anthropic_model(), "max_tokens": max_tokens, "system": system, "messages": [{"role": "user", "content": user}]}
    with httpx.Client(timeout=180.0) as client:
        for attempt in range(OPENAI_MAX_ATTEMPTS):
            response: httpx.Response | None = None
            try:
                response = client.post("https://api.anthropic.com/v1/messages", headers=anthropic_headers(), json=payload)
                if response.status_code not in retryable_statuses:
                    response.raise_for_status()
                    return response.json()
                if attempt == OPENAI_MAX_ATTEMPTS - 1:
                    response.raise_for_status()
            except (httpx.TimeoutException, httpx.NetworkError):
                if attempt == OPENAI_MAX_ATTEMPTS - 1:
                    raise
            time.sleep(_retry_delay(response, attempt))
    raise RuntimeError("Anthropic response retry loop exited unexpectedly")


def anthropic_response_text(payload: dict[str, Any]) -> str:
    out: list[str] = []
    for block in payload.get("content", []):
        if isinstance(block, dict) and block.get("type") == "text" and isinstance(block.get("text"), str):
            out.append(block["text"])
    return "\n".join(out)


_DIFF_HEADER_RE = re.compile(r"^diff --git a/(?P<a>.+?) b/(?P<b>.+?)$", re.MULTILINE)


def diff_changed_paths(diff_text: str) -> list[str]:
    """Extract the changed file paths from a unified ``git diff`` header.

    Used instead of the tuple-of-substring check this function previously
    used, so protected-path enforcement here shares
    ``orchestration/protected_paths.json`` with every other engine and
    cannot silently diverge from it again.
    """
    paths: set[str] = set()
    for match in _DIFF_HEADER_RE.finditer(diff_text):
        paths.add(match.group("a"))
        paths.add(match.group("b"))
    return sorted(paths)


def extract_json(text: str) -> dict[str, Any]:
    """Extract exactly one reviewer JSON object from otherwise harmless prose.

    Providers occasionally wrap a valid verdict in markdown or append
    explanatory text despite a JSON-only instruction. Accept that presentation
    noise, but fail closed if there is no object, the decoded value is not an
    object, or a second JSON object is present.
    """
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        if lines and lines[0].startswith("```"):
            lines = lines[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()

    try:
        value = json.loads(stripped)
    except json.JSONDecodeError:
        start = stripped.find("{")
        if start < 0:
            raise
        decoder = json.JSONDecoder()
        value, consumed = decoder.raw_decode(stripped[start:])
        trailing = stripped[start + consumed :].strip()
        if trailing:
            second_start = trailing.find("{")
            if second_start >= 0:
                try:
                    decoder.raw_decode(trailing[second_start:])
                except json.JSONDecodeError:
                    pass
                else:
                    raise RuntimeError("reviewer returned multiple JSON objects")
    if not isinstance(value, dict):
        raise RuntimeError("reviewer returned non-object JSON")
    return value


def validate_plan(plan: dict[str, Any], roles: dict[str, Any]) -> None:
    tasks = plan.get("tasks")
    if not isinstance(tasks, dict) or set(tasks) != set(roles):
        raise RuntimeError("planner returned invalid role set")
    active = 0
    changes = 0
    for role, task in tasks.items():
        if not isinstance(task, dict) or task.get("status") not in {"TASK", "NO_TASK"}:
            raise RuntimeError(f"planner returned invalid task for {role}")
        if task.get("mode") not in {"CHANGE", "AUDIT"}:
            raise RuntimeError(f"planner returned invalid mode for {role}")
        if not isinstance(task.get("task"), str):
            raise RuntimeError(f"planner omitted task text for {role}")
        if task["status"] == "TASK":
            active += 1
        if task["mode"] == "CHANGE":
            changes += 1
    if active != len(roles):
        raise RuntimeError(
            f"planner must activate every specialist: {active} active tasks != {len(roles)} roles"
        )
    if changes != MAX_CHANGE_TASKS_PER_CYCLE:
        raise RuntimeError(
            f"planner must assign exactly one CHANGE task: {changes} != {MAX_CHANGE_TASKS_PER_CYCLE}"
        )


def plan_tasks(output: Path) -> int:
    state = read_file("AI_STATE.md")
    external = os.getenv("AGENT_EXTERNAL_CONTEXT", "")[-30_000:]
    roles = load_roles()
    task_shape = ",\n    ".join(
        f'"{role}": {{"status": "TASK", "mode": "CHANGE|AUDIT", "task": "..."}}' for role in roles
    )
    prompt = f"""
You are the Lead Integrator planning one fail-closed autonomous development cycle for a crypto quantitative trading/signalling system.

AUTHORITATIVE AI_STATE.md:\n{state}

RECENT GITHUB CONTEXT:\n{external}

SPECIALIST ROLES:\n{json.dumps(roles, indent=2)}

Return JSON only with this exact role set:
{{
  "cycle_goal": "...",
  "tasks": {{
    {task_shape}
  }}
}}
Rules:
- Use AI_STATE.md as authoritative.
- Assign at most one bounded task per role.
- Assign one small, useful TASK to every specialist in every hourly cycle so all {MAX_ACTIVE_TASKS_PER_CYCLE} specialists inspect or improve their owned area.
- Assign exactly {MAX_CHANGE_TASKS_PER_CYCLE} role mode=CHANGE. Every other role must be mode=AUDIT and read-only. Choose the single change with the highest evidence-backed priority from AI_STATE.md.
- Keep each task tightly bounded and evidence-driven. An inspection may finish with NO_CHANGE; never invent a code change merely to appear busy.
- Respect each role's allowed paths exactly.
- Do not assign edits to AI_STATE.md, agents/, workflows, requirements.txt or Dockerfile.
- Never promote research to live use from one OOS pass.
- Preserve no-lookahead and fail-closed behavior.
- Use TASK for every role. AUDIT roles report findings but cannot write. The CHANGE worker must report NO_CHANGE when no safe, useful repository change is justified.
- Tasks must be small enough for one specialist cycle and testable with repository evidence.
"""
    payload = post_response({"model": model_name(), "input": prompt})
    plan = extract_json(response_text(payload))
    validate_plan(plan, roles)
    output.write_text(json.dumps(plan, indent=2) + "\n", encoding="utf-8")
    return 0


REVIEWERS = {"lead", "security", "claude-adversarial"}
REQUIRED_FALSIFICATION_FINDINGS = (
    "leakage_lookahead",
    "oos_contamination",
    "overlapping_observations",
    "point_in_time_universe",
    "multiple_testing",
    "unrealistic_costs",
    "timestamp_errors",
    "regime_instability",
    "insufficient_sample_size",
    "baseline_mismatch",
    "paper_ledger_integrity",
)


def review_diff(reviewer: str, diff_path: Path, output: Path) -> int:
    if reviewer not in REVIEWERS:
        raise RuntimeError("unknown reviewer")
    diff = diff_path.read_text(encoding="utf-8")
    if len(diff.encode("utf-8")) > 80_000:
        raise RuntimeError("diff too large")
    protected_hits = find_protected_matches(diff_changed_paths(diff))
    if protected_hits:
        raise RuntimeError(f"protected path(s) in diff: {protected_hits}")

    if reviewer == "claude-adversarial":
        return _review_diff_claude_adversarial(diff, output)

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


def _review_diff_claude_adversarial(diff: str, output: Path) -> int:
    """Independent Claude review of a candidate diff.

    Must be genuinely independent of the implementing engine's own claims:
    it is instructed to actively try to falsify the change against eleven
    named failure modes rather than confirm it, and its approval is
    documented (here and in the prompt itself) as never sufficient by
    itself to promote a strategy, weaken a validation gate, or authorize
    live trading -- ``forward_proof.py``, ``robustness.py``, and
    ``multiple_testing.py`` remain the only source of promotion-grade
    quantitative evidence.
    """
    system = (
        "You are an independent adversarial scientific reviewer for a crypto trading "
        "signal system. Your job is to actively try to FALSIFY the claimed improvement "
        "in the diff you are given, not to confirm it. You are reviewing a candidate "
        "produced by a different engine (Claude Code or ChatGPT); your review must be "
        "genuinely independent of that engine's own claims about correctness or evidence "
        "quality -- do not simply trust its summary or test results. Your approval is "
        "never sufficient to promote a strategy, weaken a validation gate, or authorize "
        "live trading; it is one input among the canonical quantitative gates "
        "(forward_proof.py, robustness.py, multiple_testing.py), which alone can "
        "establish scientific evidence."
    )
    findings_schema = ", ".join(f'"{name}": "..."' for name in REQUIRED_FALSIFICATION_FINDINGS)
    user = f"""
Adversarially review this diff. For each of the eleven failure modes below, state whether
the diff shows evidence of the problem, evidence the problem is avoided, or gives
insufficient evidence to tell -- insufficient evidence must be treated as a finding against
approval, never silently passed.

1. leakage_lookahead: does any feature or label use information not available at decision time?
2. oos_contamination: is untouched out-of-sample evidence reused, or opened more than once?
3. overlapping_observations: are forward-return windows counted as independent when they are not?
4. point_in_time_universe: could survivorship or backfilled universe membership bias the result?
5. multiple_testing: how many variants were implicitly or explicitly searched, and is that accounted for?
6. unrealistic_costs: are fees/spread/slippage/adverse-selection modeled realistically and cost-stressed per this project's convention?
7. timestamp_errors: could any timestamp be stale, future, or inconsistent with the claimed causal order?
8. regime_instability: does the claimed effect hold across more than one regime/period, or only in a cherry-picked window?
9. insufficient_sample_size: does the independent sample count meet this project's predeclared minimums for the horizon in question?
10. baseline_mismatch: is the comparison against the correct frozen baseline, not a weaker or different one?
11. paper_ledger_integrity: does the change touch, or could it indirectly corrupt, the append-only paper ledger's authenticity?

PROPOSED DIFF:
{diff}

Return JSON only:
{{"approve": true|false, "reason": "specific evidence-based reason", "risk": "low|medium|high",
  "falsification_findings": {{{findings_schema}}}}}
Approve only if every finding above is either "avoided" or "not applicable to this diff" with a
stated reason, the diff is bounded and internally coherent, it does not weaken any safety or
validation gate, and it makes no unsupported live-trading or promotion claim. Reject when
evidence for any finding is insufficient to rule the problem out -- do not give the benefit of
the doubt.

Response budget: aim for at most 45 words per finding and 80 words for reason,
within the existing 2000-token output allowance. Include every required finding;
cite the decisive code location/evidence concisely instead of repeating the diff.
This is a writing budget, not permission to omit findings, skip analysis, or approve
an unresolved concern. Do not truncate JSON or use ellipses in place of evidence.
"""
    response = post_anthropic_message(system, user, max_tokens=2000)
    verdict = extract_json(anthropic_response_text(response))
    if not isinstance(verdict.get("approve"), bool):
        raise RuntimeError("reviewer returned invalid approval")
    if verdict.get("risk") not in {"low", "medium", "high"}:
        raise RuntimeError("reviewer returned invalid risk")
    findings = verdict.get("falsification_findings")
    if not isinstance(findings, dict) or set(REQUIRED_FALSIFICATION_FINDINGS) - set(findings):
        raise RuntimeError("claude-adversarial reviewer omitted required falsification findings")
    # Preserve any schema-valid rejection; never retry away a negative verdict.
    # Approval additionally needs affirmative provider completion, even when a
    # cut-off response happens to contain a parseable JSON object.
    if verdict["approve"] and response.get("stop_reason") != "end_turn":
        raise RuntimeError("temporarily unavailable: Claude reviewer response incomplete; approval withheld")
    output.write_text(json.dumps(verdict, indent=2) + "\n", encoding="utf-8")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    plan = sub.add_parser("plan")
    plan.add_argument("--output", required=True)

    review = sub.add_parser("review")
    review.add_argument("--reviewer", choices=sorted(REVIEWERS), required=True)
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
