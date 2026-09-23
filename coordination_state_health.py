"""Fail-closed freshness evaluation for the canonical AI_STATE handoff.

This module only classifies coordination-state freshness. It has no deployment,
repository-write, strategy-promotion, broker, or trading authority.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any


def _bounded_int_env(name: str, default: int, lower: int, upper: int) -> int:
    raw = os.getenv(name)
    if raw is None:
        return default
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default
    return max(lower, min(value, upper))


# A continuously coordinated repository should refresh its canonical handoff at
# least daily. Operators may tighten these tolerances without code changes, but
# cannot loosen them beyond the fail-closed defaults.
AI_STATE_MAX_AGE_SECONDS = _bounded_int_env(
    "AI_STATE_MAX_AGE_SECONDS",
    24 * 60 * 60,
    5 * 60,
    24 * 60 * 60,
)
AI_STATE_MAX_FUTURE_SKEW_SECONDS = _bounded_int_env(
    "AI_STATE_MAX_FUTURE_SKEW_SECONDS",
    60,
    0,
    60,
)


def _parse_aware_timestamp(value: str | None) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def evaluate_state_handoff_timestamp(
    last_updated: str | None,
    *,
    has_exact_next_step: bool,
    now: datetime | None = None,
    max_age_seconds: int = AI_STATE_MAX_AGE_SECONDS,
    max_future_skew_seconds: int = AI_STATE_MAX_FUTURE_SKEW_SECONDS,
) -> dict[str, Any]:
    """Classify AI_STATE chronology and structure without guessing freshness.

    Missing, malformed, stale, or materially future-dated timestamps fail
    closed. ``state_fresh`` concerns timestamp freshness only;
    ``state_structure_ok`` separately records the required handoff structure.
    """
    if max_age_seconds <= 0:
        raise ValueError("max_age_seconds must be positive")
    if max_future_skew_seconds < 0:
        raise ValueError("max_future_skew_seconds must be non-negative")

    result: dict[str, Any] = {
        "state_age_seconds": None,
        "state_fresh": False,
        "state_structure_ok": bool(has_exact_next_step),
        "state_failure_reason": None,
    }
    if not isinstance(last_updated, str) or not last_updated.strip():
        result["state_failure_reason"] = "missing_timestamp"
        return result

    parsed = _parse_aware_timestamp(last_updated)
    if parsed is None:
        result["state_failure_reason"] = "malformed_timestamp"
        return result

    current = now if now is not None else datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    current = current.astimezone(timezone.utc)
    age_seconds = (current - parsed).total_seconds()
    result["state_age_seconds"] = round(age_seconds, 3)

    if age_seconds < -float(max_future_skew_seconds):
        result["state_failure_reason"] = "future_timestamp"
        return result
    if age_seconds > float(max_age_seconds):
        result["state_failure_reason"] = "stale_timestamp"
        return result

    result["state_fresh"] = True
    if not has_exact_next_step:
        result["state_failure_reason"] = "missing_exact_next_step"
        return result
    return result
