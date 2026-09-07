from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from agents.autonomous_orchestrator import (
    MAX_TOOL_STEPS,
    call_tool,
    load_roles,
    model_name,
    post_response,
    response_text,
    tool_specs,
)


REQUIRED_COMPLETION_MARKERS = (
    "CHANGE_STATUS: READY_FOR_PR",
    "CHANGE_STATUS: NO_CHANGE",
)


def _completion_text(payload: dict[str, Any]) -> str:
    text = response_text(payload).strip()
    if not any(marker in text for marker in REQUIRED_COMPLETION_MARKERS):
        raise RuntimeError("agent ended without required CHANGE_STATUS marker; failing closed")
    return text


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
Assigned task: {task['task']}

Hard rules:
- Execute the assigned task now; never ask what task to perform.
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
- Finish with a concise summary containing exactly one completion marker: CHANGE_STATUS: READY_FOR_PR or CHANGE_STATUS: NO_CHANGE.
"""

    current = post_response(
        {
            "model": model_name(),
            "instructions": instructions,
            "input": (
                f"Complete this assigned task now: {task['task']}\n"
                "Begin by reading AI_STATE.md, inspect only the files needed, use tools to implement the bounded change, "
                "run relevant tests, and finish with the required CHANGE_STATUS marker."
            ),
            "tools": tool_specs(),
        }
    )

    for _ in range(MAX_TOOL_STEPS):
        calls = [item for item in current.get("output", []) if item.get("type") == "function_call"]
        if not calls:
            print(_completion_text(current))
            return 0

        outputs: list[dict[str, Any]] = []
        for call in calls:
            try:
                args = json.loads(call.get("arguments") or "{}")
            except json.JSONDecodeError:
                args = {}
            result = call_tool(role, call.get("name", ""), args)
            outputs.append(
                {
                    "type": "function_call_output",
                    "call_id": call["call_id"],
                    "output": result,
                }
            )

        current = post_response(
            {
                "model": model_name(),
                "instructions": instructions,
                "previous_response_id": current["id"],
                "input": outputs,
                "tools": tool_specs(),
            }
        )

    raise RuntimeError("agent exceeded maximum tool steps; failing closed")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", required=True)
    parser.add_argument("--plan", required=True)
    args = parser.parse_args()
    return execute_task(args.role, Path(args.plan))


if __name__ == "__main__":
    raise SystemExit(main())
