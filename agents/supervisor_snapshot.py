from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "AI_STATE.md"
BACKLOG_PATH = ROOT / "orchestration" / "priority_backlog.json"


def _section(text: str, heading: str) -> str:
    marker = f"## {heading}"
    start = text.find(marker)
    if start < 0:
        return ""
    tail = text[start:]
    next_pos = tail.find("\n## ", len(marker))
    return tail if next_pos < 0 else tail[:next_pos]


def _safety_section(state: str) -> str:
    """Preserve safety context even when the canonical state uses a compact heading."""
    explicit = _section(state, "SAFETY INVARIANTS")
    if explicit:
        return explicit
    live_safety = _section(state, "LIVE SIGNAL SAFETY — ENFORCED")
    if not live_safety:
        return ""
    return "## SAFETY INVARIANTS\n" + live_safety


def load_backlog() -> dict:
    payload = json.loads(BACKLOG_PATH.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or not isinstance(payload.get("items"), list):
        raise RuntimeError("invalid priority backlog")
    return payload


def ready_items(backlog: dict) -> list[dict]:
    items = [item for item in backlog["items"] if item.get("status") == "READY"]
    return sorted(items, key=lambda item: (int(item.get("priority", 9999)), str(item.get("id", ""))))


def build_snapshot() -> dict:
    state = STATE_PATH.read_text(encoding="utf-8")
    backlog = load_backlog()
    ready = ready_items(backlog)
    event = {
        "name": os.getenv("GITHUB_EVENT_NAME", "unknown"),
        "workflow": os.getenv("GITHUB_WORKFLOW", "unknown"),
        "run_id": os.getenv("GITHUB_RUN_ID", "unknown"),
        "sha": os.getenv("GITHUB_SHA", "unknown"),
    }
    return {
        "event": event,
        "safety_invariants": _safety_section(state)[-6000:],
        "exact_next_step": _section(state, "EXACT NEXT STEP")[-6000:],
        "priority_backlog": [
            {
                "id": item.get("id"),
                "priority": item.get("priority"),
                "owner": item.get("owner"),
                "title": item.get("title"),
                "goal": item.get("goal"),
            }
            for item in ready[:12]
        ],
        "highest_ready": ready[0].get("id") if ready else None,
        "rule": "Prefer the highest-priority READY backlog item whose owner and allowed paths can safely address it, unless a higher-priority production/security verification in EXACT NEXT STEP is currently blocking. Exactly one CHANGE task; all other specialists AUDIT.",
    }


def main() -> int:
    print(json.dumps(build_snapshot(), separators=(",", ":"), ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
