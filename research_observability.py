"""Read-only research/cache observability with cross-process safe counters.

Metrics are operational evidence only. They cannot authorize, promote, rank, or
change trading decisions. Counters live beside the shared cache so subprocesses
see the same state on one worker host.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
import time
from pathlib import Path
from typing import Any

try:
    import fcntl
except ImportError:  # pragma: no cover - production is Linux; tests can still import.
    fcntl = None


DEFAULT_METRICS_DIR = Path(os.getenv("RESEARCH_OBSERVABILITY_DIR", str(Path(tempfile.gettempdir()) / "tradingview-ai-observability")))
METRICS_FILE = "metrics.json"
LOCK_FILE = "metrics.lock"
MAX_LATENCY_SAMPLES = 200


def _default_state() -> dict[str, Any]:
    return {
        "cache": {
            "memory_hits": 0,
            "shared_hits": 0,
            "misses": 0,
            "rejections": 0,
            "network_fetches": 0,
            "network_failures": 0,
            "latency_ms_samples": [],
            "last_event_at_ms": None,
        },
        "workers": {
            "completed": 0,
            "failed": 0,
            "timeouts": 0,
            "last_event_at_ms": None,
            "by_name": {},
        },
        "authority": {
            "trade_authority": False,
            "promotion_authority": False,
            "signal_authority": False,
            "research_only": True,
        },
    }


def _safe_state(value: Any) -> dict[str, Any]:
    base = _default_state()
    if not isinstance(value, dict):
        return base
    for section in ("cache", "workers"):
        incoming = value.get(section)
        if isinstance(incoming, dict):
            base[section].update(incoming)
    return base


def _paths(metrics_dir=None):
    root = Path(metrics_dir or DEFAULT_METRICS_DIR)
    return root, root / METRICS_FILE, root / LOCK_FILE


def _with_lock(metrics_dir=None):
    root, _, lock_path = _paths(metrics_dir)
    root.mkdir(parents=True, exist_ok=True)
    handle = lock_path.open("a+", encoding="utf-8")
    if fcntl is not None:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
    return handle


def _unlock(handle):
    try:
        if fcntl is not None:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        handle.close()


def _read_unlocked(metrics_dir=None) -> dict[str, Any]:
    _, path, _ = _paths(metrics_dir)
    try:
        return _safe_state(json.loads(path.read_text(encoding="utf-8")))
    except (OSError, ValueError, TypeError):
        return _default_state()


def _write_unlocked(state, metrics_dir=None) -> None:
    root, path, _ = _paths(metrics_dir)
    root.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix="metrics-", suffix=".tmp", dir=root)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, sort_keys=True, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, path)
    finally:
        try:
            Path(temp_name).unlink()
        except FileNotFoundError:
            pass


def record_cache_event(kind: str, latency_ms: float | None = None, *, metrics_dir=None) -> None:
    allowed = {"memory_hit", "shared_hit", "miss", "rejection", "network_fetch", "network_failure"}
    if kind not in allowed:
        return
    handle = _with_lock(metrics_dir)
    try:
        state = _read_unlocked(metrics_dir)
        cache = state["cache"]
        key = {
            "memory_hit": "memory_hits",
            "shared_hit": "shared_hits",
            "miss": "misses",
            "rejection": "rejections",
            "network_fetch": "network_fetches",
            "network_failure": "network_failures",
        }[kind]
        cache[key] = max(0, int(cache.get(key) or 0)) + 1
        if latency_ms is not None:
            try:
                value = float(latency_ms)
            except (TypeError, ValueError):
                value = -1.0
            if math.isfinite(value) and value >= 0:
                samples = [float(v) for v in (cache.get("latency_ms_samples") or []) if isinstance(v, (int, float)) and math.isfinite(float(v)) and float(v) >= 0]
                samples.append(round(value, 3))
                cache["latency_ms_samples"] = samples[-MAX_LATENCY_SAMPLES:]
        cache["last_event_at_ms"] = int(time.time() * 1000)
        _write_unlocked(state, metrics_dir)
    finally:
        _unlock(handle)


def record_worker_result(name: str, exit_code: int, elapsed_seconds: float, evidence=None, *, metrics_dir=None) -> None:
    handle = _with_lock(metrics_dir)
    try:
        state = _read_unlocked(metrics_dir)
        workers = state["workers"]
        workers["completed"] = max(0, int(workers.get("completed") or 0)) + 1
        failed = int(exit_code) != 0
        if failed:
            workers["failed"] = max(0, int(workers.get("failed") or 0)) + 1
        if int(exit_code) == -9:
            workers["timeouts"] = max(0, int(workers.get("timeouts") or 0)) + 1
        by_name = workers.setdefault("by_name", {})
        by_name[str(name)] = {
            "last_exit_code": int(exit_code),
            "elapsed_seconds": round(max(0.0, float(elapsed_seconds)), 3),
            "latest_evidence": evidence if isinstance(evidence, dict) else None,
            "updated_at_ms": int(time.time() * 1000),
        }
        workers["last_event_at_ms"] = int(time.time() * 1000)
        _write_unlocked(state, metrics_dir)
    finally:
        _unlock(handle)


def _percentile(values: list[float], q: float):
    if not values:
        return None
    ordered = sorted(values)
    idx = int(round((len(ordered) - 1) * q))
    return round(ordered[max(0, min(idx, len(ordered) - 1))], 3)


def snapshot(*, metrics_dir=None) -> dict[str, Any]:
    handle = _with_lock(metrics_dir)
    try:
        state = _read_unlocked(metrics_dir)
    finally:
        _unlock(handle)
    cache = state["cache"]
    memory_hits = max(0, int(cache.get("memory_hits") or 0))
    shared_hits = max(0, int(cache.get("shared_hits") or 0))
    misses = max(0, int(cache.get("misses") or 0))
    rejections = max(0, int(cache.get("rejections") or 0))
    network_fetches = max(0, int(cache.get("network_fetches") or 0))
    requests = memory_hits + shared_hits + misses + rejections
    reusable = memory_hits + shared_hits
    samples = [float(v) for v in (cache.get("latency_ms_samples") or []) if isinstance(v, (int, float)) and math.isfinite(float(v)) and float(v) >= 0]
    workers = state["workers"]
    by_name = workers.get("by_name") if isinstance(workers.get("by_name"), dict) else {}
    acc002 = {}
    for name in ("cross-asset-rank-24h", "cross-asset-rank-7d"):
        row = by_name.get(name) if isinstance(by_name.get(name), dict) else {}
        acc002[name] = {
            "last_exit_code": row.get("last_exit_code"),
            "elapsed_seconds": row.get("elapsed_seconds"),
            "updated_at_ms": row.get("updated_at_ms"),
            "latest_evidence": row.get("latest_evidence") if isinstance(row.get("latest_evidence"), dict) else None,
        }
    completed = max(0, int(workers.get("completed") or 0))
    failed = max(0, int(workers.get("failed") or 0))
    return {
        "research_only": True,
        "trade_authority": False,
        "promotion_authority": False,
        "signal_authority": False,
        "cache": {
            "requests_observed": requests,
            "memory_hits": memory_hits,
            "shared_hits": shared_hits,
            "misses": misses,
            "rejections": rejections,
            "network_fetches": network_fetches,
            "network_failures": max(0, int(cache.get("network_failures") or 0)),
            "reuse_rate": round(reusable / requests, 4) if requests else None,
            "shared_hit_rate": round(shared_hits / requests, 4) if requests else None,
            "rejection_rate": round(rejections / requests, 4) if requests else None,
            "latency_ms": {
                "samples": len(samples),
                "mean": round(sum(samples) / len(samples), 3) if samples else None,
                "p50": _percentile(samples, 0.50),
                "p95": _percentile(samples, 0.95),
            },
            "last_event_at_ms": cache.get("last_event_at_ms"),
        },
        "workers": {
            "completed": completed,
            "failed": failed,
            "timeouts": max(0, int(workers.get("timeouts") or 0)),
            "failure_rate": round(failed / completed, 4) if completed else None,
            "last_event_at_ms": workers.get("last_event_at_ms"),
        },
        "acc002": acc002,
    }
