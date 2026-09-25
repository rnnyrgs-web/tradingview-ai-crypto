"""Small, thread-safe, sanitized production health state."""

from __future__ import annotations

import os
import time
from collections import Counter, deque
from datetime import datetime, timezone
from threading import Lock


def _configured_recent_error_window_seconds() -> int:
    raw = os.getenv("OPERATIONAL_RECENT_ERROR_WINDOW_SECONDS", "900")
    try:
        seconds = int(raw)
    except (TypeError, ValueError):
        seconds = 900
    return max(60, min(seconds, 3600))


RECENT_ERROR_WINDOW_SECONDS = _configured_recent_error_window_seconds()

_lock = Lock()
_errors = deque(maxlen=50)
_counts = Counter()
_last_scan = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _prune_recent_errors(now_monotonic: float) -> None:
    cutoff = float(now_monotonic) - RECENT_ERROR_WINDOW_SECONDS
    while _errors and float(_errors[0]["recorded_monotonic"]) < cutoff:
        _errors.popleft()


def record_error(component: str, exc: BaseException) -> None:
    event = {
        "at": _now(),
        "component": str(component)[:80],
        "error_type": type(exc).__name__,
        "recorded_monotonic": time.monotonic(),
    }
    with _lock:
        _prune_recent_errors(event["recorded_monotonic"])
        _errors.append(event)
        _counts[event["component"]] += 1


def record_scan(result: dict) -> None:
    global _last_scan
    summary = {
        "at": _now(),
        "scan_id": result.get("scan_id"),
        "ok": result.get("ok") is True,
        "universe_count": int(result.get("universe_count") or 0),
        "deep_scanned": int(result.get("deep_scanned") or 0),
        "scan_error_count": int(result.get("scan_error_count") or 0),
        "signals_saved": int(result.get("signals_saved") or 0),
        "ai_ok": not bool(result.get("ai_error")),
        "opportunities_ok": not bool(result.get("opportunity_error")),
    }
    with _lock:
        _last_scan = summary


def health_snapshot() -> dict:
    with _lock:
        _prune_recent_errors(time.monotonic())
        recent_errors = [
            {key: value for key, value in event.items() if key != "recorded_monotonic"}
            for event in list(_errors)[-10:]
        ]
        return {
            "last_scan": dict(_last_scan) if _last_scan else None,
            "recent_error_window_seconds": RECENT_ERROR_WINDOW_SECONDS,
            "recent_error_count": len(_errors),
            "error_counts_by_component": dict(_counts),
            "recent_errors": recent_errors,
        }
