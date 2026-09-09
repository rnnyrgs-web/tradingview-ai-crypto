"""Bounded advisory research memory for continuous learning."""

from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path

import research_learning_persistent as persistent_store

DEFAULT_PATH = Path(os.getenv("RESEARCH_LEARNING_STATE_PATH", str(Path(tempfile.gettempdir()) / "tradingview-ai-research-learning.json")))
MAX_LESSONS = 200
CONCLUSIVE_OUTCOMES = {"validation_failed", "oos_evaluated"}


def _now():
    return datetime.now(timezone.utc).isoformat()


def _resolve_path(path):
    return Path(DEFAULT_PATH if path is None else path)


def _nonnegative_int(value):
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        return 0
    return max(0, parsed)


def _file_load_state(path):
    target = _resolve_path(path)
    try:
        raw = json.loads(target.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {"lessons": [], "updated_at": None, "conclusive_trial_count": 0}
    lessons = raw.get("lessons") if isinstance(raw, dict) else []
    return {
        "lessons": lessons[-MAX_LESSONS:] if isinstance(lessons, list) else [],
        "updated_at": raw.get("updated_at") if isinstance(raw, dict) else None,
        "conclusive_trial_count": _nonnegative_int(raw.get("conclusive_trial_count")) if isinstance(raw, dict) else 0,
    }


def load_state(path=None):
    # Production is already Supabase-backed. Prefer durable memory whenever the
    # service-role connection exists. A configured persistent-store error is
    # intentionally not hidden by an empty /tmp fallback: adaptive research must
    # fail closed rather than forget prior trials after a transient outage.
    if path is None and persistent_store.configured():
        return persistent_store.load_state()
    return _file_load_state(path)


def append_lesson(lesson, path=None):
    if not isinstance(lesson, dict):
        raise TypeError("lesson must be a dict")
    allowed = {"fingerprint", "hypothesis", "outcome", "evidence_summary", "recommended_next_test", "reason_not_to_repeat"}
    compact = {k: lesson.get(k) for k in allowed if lesson.get(k) is not None}
    compact.update({"recorded_at": _now(), "research_only": True, "trade_authority": False, "promotion_authority": False})

    if path is None and persistent_store.configured():
        persistent_store.append_lesson(compact)
        return compact

    target = _resolve_path(path)
    state = _file_load_state(target)
    fingerprint = compact.get("fingerprint")
    if fingerprint:
        state["lessons"] = [x for x in state["lessons"] if x.get("fingerprint") != fingerprint]
    state["lessons"].append(compact)
    state["lessons"] = state["lessons"][-MAX_LESSONS:]
    if str(compact.get("outcome") or "") in CONCLUSIVE_OUTCOMES:
        state["conclusive_trial_count"] = _nonnegative_int(state.get("conclusive_trial_count")) + 1
    state["updated_at"] = _now()
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
