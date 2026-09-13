from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_PATH = ROOT / "orchestration" / "architecture_review_backlog.json"

REQUIRED_FIELDS = ("id", "severity", "summary", "evidence", "status")
VALID_SEVERITIES = {"LOW", "MEDIUM", "HIGH"}
VALID_STATUSES = {"OPEN", "FIXED"}


def load_backlog(path: Path = DEFAULT_PATH) -> list[dict[str, Any]]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    items = payload.get("items")
    if not isinstance(items, list):
        raise RuntimeError("architecture review backlog must contain a list of items")
    seen: set[str] = set()
    for item in items:
        if not isinstance(item, dict):
            raise RuntimeError("backlog item must be an object")
        missing = [field for field in REQUIRED_FIELDS if field not in item]
        if missing:
            raise RuntimeError(f"backlog item missing required fields: {missing}")
        item_id = str(item["id"])
        if item_id in seen:
            raise RuntimeError(f"duplicate backlog item id: {item_id}")
        seen.add(item_id)
        if item["severity"] not in VALID_SEVERITIES:
            raise RuntimeError(f"invalid severity for {item_id}: {item['severity']}")
        if item["status"] not in VALID_STATUSES:
            raise RuntimeError(f"invalid status for {item_id}: {item['status']}")
        if item["status"] == "FIXED" and "fixed_in" not in item:
            raise RuntimeError(f"FIXED backlog item missing fixed_in reference: {item_id}")
    return items


def open_items(items: list[dict[str, Any]] | None = None) -> list[dict[str, Any]]:
    active = items if items is not None else load_backlog()
    return [item for item in active if item["status"] == "OPEN"]
