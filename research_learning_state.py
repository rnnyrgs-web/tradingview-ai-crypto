"""Bounded advisory research memory for continuous learning."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

DEFAULT_PATH = Path(os.getenv("RESEARCH_LEARNING_STATE_PATH", str(Path(tempfile.gettempdir()) / "tradingview-ai-research-learning.json")))
MAX_LESSONS = 200


def _now():
    return datetime.now(timezone.utc).isoformat()


def load_state(path=DEFAULT_PATH):
    try:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {"lessons": [], "updated_at": None}
    lessons = raw.get("lessons") if isinstance(raw, dict) else []
    return {
        "lessons": lessons[-MAX_LESSONS:] if isinstance(lessons, list) else [],
        "updated_at": raw.get("updated_at") if isinstance(raw, dict) else None,
    }


def append_lesson(lesson, path=DEFAULT_PATH):
    if not isinstance(lesson, dict):
        raise TypeError("lesson must be a dict")
    allowed = {"fingerprint", "hypothesis", "outcome", "evidence_summary", "recommended_next_test", "reason_not_to_repeat"}
    compact = {k: lesson.get(k) for k in allowed if lesson.get(k) is not None}
    compact.update({"recorded_at": _now(), "research_only": True, "trade_authority": False, "promotion_authority": False})
    state = load_state(path)
    fingerprint = compact.get("fingerprint")
    if fingerprint:
        state["lessons"] = [x for x in state["lessons"] if x.get("fingerprint") != fingerprint]
    state["lessons"].append(compact)
    state["lessons"] = state["lessons"][-MAX_LESSONS:]
    state["updated_at"] = _now()
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix="research-learning-", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, sort_keys=True, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, target)
    finally:
        try:
            Path(tmp).unlink()
        except FileNotFoundError:
            pass
    return compact
