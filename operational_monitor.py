"""Small, thread-safe, sanitized production health state."""

from __future__ import annotations

from collections import Counter, deque
from datetime import datetime, timezone
from threading import Lock


_lock = Lock()
_errors = deque(maxlen=50)
_counts = Counter()
_last_scan = None


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def record_error(component: str, exc: BaseException) -> None:
    event = {
        "at": _now(),
        "component": str(component)[:80],
        "error_type": type(exc).__name__,
    }
    with _lock:
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
        return {
            "last_scan": dict(_last_scan) if _last_scan else None,
            "recent_error_count": len(_errors),
            "error_counts_by_component": dict(_counts),
            "recent_errors": list(_errors)[-10:],
        }
