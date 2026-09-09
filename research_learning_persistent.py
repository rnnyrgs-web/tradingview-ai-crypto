"""Durable service-role-only store for adaptive research memory.

Production uses Supabase so research lessons and the global conclusive-trial count
survive Render deploys. Local/tests may continue to use the file-backed adapter in
research_learning_state.py. Any configured persistent-store failure raises and
therefore fails the adaptive research lane closed rather than resetting evidence.
"""

from __future__ import annotations

from typing import Any

import db
from config import SUPABASE_URL


def configured() -> bool:
    return db.configured()


def _normalize_state(row: object) -> dict[str, Any]:
    if not isinstance(row, dict):
        raise RuntimeError("invalid persistent research learning state")
    lessons = row.get("lessons")
    if not isinstance(lessons, list):
        lessons = []
    try:
        trial_count = max(0, int(row.get("conclusive_trial_count") or 0))
    except (TypeError, ValueError) as exc:
        raise RuntimeError("invalid persistent conclusive trial count") from exc
    return {
        "lessons": lessons[-200:],
        "updated_at": row.get("updated_at"),
        "conclusive_trial_count": trial_count,
    }


def load_state() -> dict[str, Any]:
    if not configured():
        raise RuntimeError("persistent research learning store is not configured")
    response = db.http.get(
        f"{SUPABASE_URL}/rest/v1/research_learning_state",
        headers=db.headers(),
        params={
            "select": "lessons,conclusive_trial_count,updated_at",
            "singleton_id": "eq.1",
            "limit": "1",
        },
    )
    if response.status_code >= 300:
        raise RuntimeError(f"Supabase research learning read failed: {response.status_code}")
    rows = response.json()
    if not isinstance(rows, list) or len(rows) != 1:
        raise RuntimeError("persistent research learning singleton is missing")
    return _normalize_state(rows[0])


def append_lesson(compact_lesson: dict[str, Any]) -> None:
    if not configured():
        raise RuntimeError("persistent research learning store is not configured")
    if not isinstance(compact_lesson, dict):
        raise TypeError("compact_lesson must be a dict")
    response = db.http.post(
        f"{SUPABASE_URL}/rest/v1/rpc/append_research_learning_lesson",
        headers=db.headers(),
        json={"p_lesson": compact_lesson},
    )
    if response.status_code >= 300:
        raise RuntimeError(f"Supabase research learning append failed: {response.status_code}")
