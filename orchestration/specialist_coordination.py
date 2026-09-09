from __future__ import annotations

import argparse
import json
from pathlib import Path

from signal_development import load_objective

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "orchestration" / "specialist_coordination.json"

VALID_STATUSES = {"READY", "IN_PROGRESS", "BLOCKED", "PR_OPEN", "DONE", "QUEUED"}
REQUIRED_ROLES = {
    "quant-research",
    "signal-accuracy",
    "data-market",
    "regime-selection",
    "execution-microstructure",
    "production-risk",
    "testing-security",
}


def load_state(path: Path = STATE_PATH) -> dict:
    load_objective()
    payload = json.loads(path.read_text(encoding="utf-8"))
    validate_state(payload)
    return payload


def validate_state(payload: dict) -> None:
    if not isinstance(payload, dict):
        raise RuntimeError("coordination state must be an object")
    roles = payload.get("roles")
    tasks = payload.get("tasks")
    policy = payload.get("policy")
    if not isinstance(roles, dict) or set(roles) != REQUIRED_ROLES:
        raise RuntimeError("coordination state must define exactly the seven specialist roles")
    if not isinstance(tasks, list) or not tasks:
        raise RuntimeError("coordination state tasks must be a non-empty list")
    if not isinstance(policy, dict):
        raise RuntimeError("coordination policy missing")
    if policy.get("specialists_write_main") is not False:
        raise RuntimeError("specialists must not write main")
    if policy.get("specialists_merge_own_prs") is not False:
        raise RuntimeError("specialists must not merge their own PRs")
    if policy.get("automatic_merge") is not False:
        raise RuntimeError("automatic merge must remain disabled")
    if policy.get("broker_connected") is not False:
        raise RuntimeError("broker must remain disconnected")
    if int(policy.get("monthly_infrastructure_ceiling_usd", -1)) != 30:
        raise RuntimeError("monthly infrastructure ceiling must remain USD 30")

    ids: set[str] = set()
    by_id: dict[str, dict] = {}
    active_by_owner: dict[str, list[str]] = {role: [] for role in REQUIRED_ROLES}
    for task in tasks:
        if not isinstance(task, dict):
            raise RuntimeError("task must be an object")
        task_id = str(task.get("id", "")).strip()
        owner = str(task.get("owner", "")).strip()
        status = str(task.get("status", "")).strip()
        if not task_id or task_id in ids:
            raise RuntimeError(f"duplicate or missing task id: {task_id}")
        ids.add(task_id)
        by_id[task_id] = task
        if owner not in REQUIRED_ROLES:
            raise RuntimeError(f"invalid owner for {task_id}: {owner}")
        if status not in VALID_STATUSES:
            raise RuntimeError(f"invalid status for {task_id}: {status}")
        if not isinstance(task.get("dependencies"), list) or not isinstance(task.get("blockers"), list):
            raise RuntimeError(f"dependencies/blockers must be lists for {task_id}")
        if not isinstance(task.get("evidence_required"), list) or not task["evidence_required"]:
            raise RuntimeError(f"evidence_required missing for {task_id}")
        if status in {"READY", "IN_PROGRESS", "PR_OPEN"}:
            active_by_owner[owner].append(task_id)
        expected_branch = roles[owner].get("branch")
        if task.get("branch") != expected_branch:
            raise RuntimeError(f"branch mismatch for {task_id}: expected {expected_branch}")
        if status == "PR_OPEN" and not task.get("pr"):
            raise RuntimeError(f"PR_OPEN task missing pr for {task_id}")
        if status == "BLOCKED" and not task.get("blockers"):
            raise RuntimeError(f"BLOCKED task missing blocker for {task_id}")

    for owner, active in active_by_owner.items():
        if len(active) > 1:
            raise RuntimeError(f"duplicate active ownership for {owner}: {active}")

    for task in tasks:
        for dep in task["dependencies"]:
            dep_text = str(dep).strip()
            dep_id = dep_text.split(maxsplit=1)[0] if dep_text.startswith("COORD-") else None
            if dep_id and dep_id not in by_id:
                raise RuntimeError(f"unknown task dependency {dep} in {task['id']}")
        nxt = task.get("next_task")
        if nxt is not None and nxt not in by_id:
            raise RuntimeError(f"unknown next_task {nxt} in {task['id']}")


def role_queue(payload: dict, role: str) -> list[dict]:
    if role not in REQUIRED_ROLES:
        raise RuntimeError(f"unknown specialist role: {role}")
    rank = {"IN_PROGRESS": 0, "PR_OPEN": 1, "READY": 2, "BLOCKED": 3, "QUEUED": 4, "DONE": 5}
    rows = [task for task in payload["tasks"] if task["owner"] == role]
    return sorted(rows, key=lambda task: (rank[task["status"]], int(task.get("priority", 9999)), task["id"]))


def next_task(payload: dict, role: str) -> dict | None:
    for task in role_queue(payload, role):
        if task["status"] in {"IN_PROGRESS", "PR_OPEN", "READY"}:
            return task
    for task in role_queue(payload, role):
        if task["status"] == "QUEUED":
            return task
    return None


def compact_snapshot(payload: dict) -> dict:
    objective = load_objective()
    return {
        "objective_id": objective["objective_id"],
        "primary_mission": objective["primary_mission"],
        "current_signal_bottleneck": objective["current_bottleneck"],
        "objective": payload["objective"],
        "policy": payload["policy"],
        "roles": {
            role: {
                "branch": payload["roles"][role]["branch"],
                "next": next_task(payload, role),
            }
            for role in sorted(REQUIRED_ROLES)
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--role", choices=sorted(REQUIRED_ROLES))
    parser.add_argument("--validate", action="store_true")
    parser.add_argument("--compact", action="store_true")
    args = parser.parse_args()
    payload = load_state()
    if args.validate:
        print("specialist coordination: valid")
        return 0
    if args.role:
        objective = load_objective()
        print(json.dumps({"objective_id": objective["objective_id"], "primary_mission": objective["primary_mission"], "role": args.role, "queue": role_queue(payload, args.role), "next": next_task(payload, args.role)}, indent=2))
        return 0
    print(json.dumps(compact_snapshot(payload) if args.compact else payload, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
