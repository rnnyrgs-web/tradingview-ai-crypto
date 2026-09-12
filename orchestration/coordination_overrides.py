from __future__ import annotations

import copy
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OVERRIDE_PATH = ROOT / "orchestration" / "specialist_coordination_overrides.json"


def apply_coordination_overrides(payload: dict, path: Path = DEFAULT_OVERRIDE_PATH) -> dict:
    """Apply explicit append-only coordination corrections before validation.

    The base coordination ledger remains readable as historical evidence. Overrides
    are deliberately narrow: they may update named tasks and append new tasks, but
    they may not replace policy/roles or silently delete prior tasks.
    """
    if not path.exists():
        return payload
    override = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(override, dict):
        raise RuntimeError("coordination override must be an object")
    updates = override.get("task_updates") or {}
    additions = override.get("append_tasks") or []
    if not isinstance(updates, dict) or not isinstance(additions, list):
        raise RuntimeError("coordination override task_updates/append_tasks malformed")

    out = copy.deepcopy(payload)
    tasks = out.get("tasks")
    if not isinstance(tasks, list):
        raise RuntimeError("coordination state tasks missing before override")
    by_id = {str(task.get("id") or ""): task for task in tasks if isinstance(task, dict)}

    for task_id, patch in updates.items():
        if task_id not in by_id:
            raise RuntimeError(f"coordination override references unknown task: {task_id}")
        if not isinstance(patch, dict):
            raise RuntimeError(f"coordination override patch malformed: {task_id}")
        forbidden = {"id", "owner", "branch"}.intersection(patch)
        if forbidden:
            raise RuntimeError(f"coordination override cannot rewrite task identity: {task_id}")
        by_id[task_id].update(copy.deepcopy(patch))

    for task in additions:
        if not isinstance(task, dict):
            raise RuntimeError("coordination override appended task must be an object")
        task_id = str(task.get("id") or "").strip()
        if not task_id or task_id in by_id:
            raise RuntimeError(f"coordination override duplicate/missing task id: {task_id}")
        copied = copy.deepcopy(task)
        tasks.append(copied)
        by_id[task_id] = copied

    return out
