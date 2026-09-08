"""Cross-process, read-only observability for research infrastructure.

Metrics are operational evidence only. They never authorize signals, strategy
promotion, or trading. State is stored beside the worker runtime so subprocesses
on the same host can contribute without sharing mutable research state.
"""

from __future__ import annotations

import json
import math
import os
import tempfile
import time
from pathlib import Path
from typing import Any

import fcntl


DEFAULT_METRICS_DIR = Path(
    os.getenv(
        "RESEARCH_OBSERVABILITY_DIR",
        str(Path(tempfile.gettempdir()) / "tradingview-ai-observability"),
    )
)
MAX_LATENCY_SAMPLES = 256


def _default_state() -> dict[str, Any]:
    return {
        "cache": {
            "hits": 0,
            "misses": 0,
            "rejections": 0,
            "read_latency_ms": [],
            "last_event_at_ms": None,
        },
        "history_network": {
            "fetches": 0,
            "failures": 0,
            "request_count": 0,
            "rows_received": 0,
            "network_latency_ms": [],
            "requests_per_fetch": [],
            "last_event_at_ms": None,
            "last_fetch": None,
        },
        "workers": {
            "completed": 0,
            "failed": 0,
            "timeouts": 0,
            "last_event_at_ms": None,
            "by_name": {},
        },
    }


def _paths(metrics_dir=None):
    root = Path(metrics_dir or DEFAULT_METRICS_DIR)
    return root, root / "metrics.json", root / "metrics.lock"


def _read_state(path: Path) -> dict[str, Any]:
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return _default_state()
    if not isinstance(raw, dict):
        return _default_state()
    state = _default_state()
    for section in ("cache", "history_network", "workers"):
        if isinstance(raw.get(section), dict):
            state[section].update(raw[section])
    return state


def _write_state(root: Path, path: Path, state: dict[str, Any]) -> None:
    root.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix="metrics-", suffix=".tmp", dir=root)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(state, handle, sort_keys=True, separators=(",", ":"))
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    finally:
        try:
            Path(tmp_name).unlink()
        except FileNotFoundError:
            pass


def _mutate(mutator, *, metrics_dir=None) -> None:
    root, state_path, lock_path = _paths(metrics_dir)
    root.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_EX)
        try:
            state = _read_state(state_path)
            mutator(state)
            _write_state(root, state_path, state)
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)


def _bounded_samples(existing, value: float) -> list[float]:
    samples = [
        float(v)
        for v in (existing or [])
        if isinstance(v, (int, float)) and math.isfinite(float(v)) and float(v) >= 0
    ]
    if math.isfinite(value) and value >= 0:
        samples.append(round(value, 3))
    return samples[-MAX_LATENCY_SAMPLES:]


def record_cache_read(result: str, latency_ms: float, *, metrics_dir=None) -> None:
    if result not in {"hit", "miss", "rejection"}:
        return

    def mutate(state):
        cache = state["cache"]
        key = {"hit": "hits", "miss": "misses", "rejection": "rejections"}[result]
        cache[key] = max(0, int(cache.get(key) or 0)) + 1
        try:
            latency = float(latency_ms)
        except (TypeError, ValueError):
            latency = -1.0
        cache["read_latency_ms"] = _bounded_samples(cache.get("read_latency_ms"), latency)
        cache["last_event_at_ms"] = int(time.time() * 1000)

    _mutate(mutate, metrics_dir=metrics_dir)


def record_history_network_fetch(
    symbol: str,
    bar: str,
    *,
    request_count: int,
    rows_received: int,
    network_latency_ms: float,
    success: bool,
    error_type: str | None = None,
    metrics_dir=None,
) -> None:
    """Record only deep-history network time; never strategy/trading evidence."""
    try:
        requests = max(0, int(request_count))
        rows = max(0, int(rows_received))
        latency = float(network_latency_ms)
    except (TypeError, ValueError):
        return
    if not math.isfinite(latency) or latency < 0:
        return

    def mutate(state):
        network = state["history_network"]
        network["fetches"] = max(0, int(network.get("fetches") or 0)) + 1
        if not success:
            network["failures"] = max(0, int(network.get("failures") or 0)) + 1
        network["request_count"] = max(0, int(network.get("request_count") or 0)) + requests
        network["rows_received"] = max(0, int(network.get("rows_received") or 0)) + rows
        network["network_latency_ms"] = _bounded_samples(network.get("network_latency_ms"), latency)
        network["requests_per_fetch"] = _bounded_samples(network.get("requests_per_fetch"), float(requests))
        now_ms = int(time.time() * 1000)
        network["last_event_at_ms"] = now_ms
        network["last_fetch"] = {
            "symbol": str(symbol),
            "bar": str(bar),
            "request_count": requests,
            "rows_received": rows,
            "network_latency_ms": round(latency, 3),
            "success": bool(success),
            "error_type": str(error_type) if error_type else None,
            "updated_at_ms": now_ms,
        }

    _mutate(mutate, metrics_dir=metrics_dir)


def record_worker_result(name: str, exit_code: int, elapsed_seconds: float, evidence=None, *, metrics_dir=None) -> None:
    def mutate(state):
        workers = state["workers"]
        workers["completed"] = max(0, int(workers.get("completed") or 0)) + 1
        if int(exit_code) != 0:
            workers["failed"] = max(0, int(workers.get("failed") or 0)) + 1
        if int(exit_code) == -9:
            workers["timeouts"] = max(0, int(workers.get("timeouts") or 0)) + 1
        rows = workers.setdefault("by_name", {})
        rows[str(name)] = {
            "last_exit_code": int(exit_code),
            "elapsed_seconds": round(max(0.0, float(elapsed_seconds)), 3),
            "latest_evidence": evidence if isinstance(evidence, dict) else None,
            "updated_at_ms": int(time.time() * 1000),
        }
        workers["last_event_at_ms"] = int(time.time() * 1000)

    _mutate(mutate, metrics_dir=metrics_dir)


def _percentile(values: list[float], q: float):
    if not values:
        return None
    ordered = sorted(values)
    idx = int(round((len(ordered) - 1) * q))
    return round(ordered[max(0, min(idx, len(ordered) - 1))], 3)


def _latency_summary(values) -> dict[str, Any]:
    samples = [
        float(v)
        for v in (values or [])
        if isinstance(v, (int, float)) and math.isfinite(float(v)) and float(v) >= 0
    ]
    return {
        "samples": len(samples),
        "mean": round(sum(samples) / len(samples), 3) if samples else None,
        "p50": _percentile(samples, 0.50),
        "p95": _percentile(samples, 0.95),
    }


def snapshot(*, metrics_dir=None) -> dict[str, Any]:
    root, state_path, lock_path = _paths(metrics_dir)
    root.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as lock_handle:
        fcntl.flock(lock_handle.fileno(), fcntl.LOCK_SH)
        try:
            state = _read_state(state_path)
        finally:
            fcntl.flock(lock_handle.fileno(), fcntl.LOCK_UN)

    cache = state["cache"]
    hits = max(0, int(cache.get("hits") or 0))
    misses = max(0, int(cache.get("misses") or 0))
    rejections = max(0, int(cache.get("rejections") or 0))
    total_reads = hits + misses + rejections

    network = state["history_network"]
    fetches = max(0, int(network.get("fetches") or 0))
    network_failures = max(0, int(network.get("failures") or 0))
    request_count = max(0, int(network.get("request_count") or 0))
    rows_received = max(0, int(network.get("rows_received") or 0))

    workers = state["workers"]
    completed = max(0, int(workers.get("completed") or 0))
    failed = max(0, int(workers.get("failed") or 0))
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

    return {
        "research_only": True,
        "trade_authority": False,
        "promotion_authority": False,
        "signal_authority": False,
        "cache": {
            "reads_observed": total_reads,
            "hits": hits,
            "misses": misses,
            "rejections": rejections,
            "hit_rate": round(hits / total_reads, 4) if total_reads else None,
            "rejection_rate": round(rejections / total_reads, 4) if total_reads else None,
            "read_latency_ms": _latency_summary(cache.get("read_latency_ms")),
            "last_event_at_ms": cache.get("last_event_at_ms"),
        },
        "history_network": {
            "fetches": fetches,
            "failures": network_failures,
            "failure_rate": round(network_failures / fetches, 4) if fetches else None,
            "request_count": request_count,
            "rows_received": rows_received,
            "avg_requests_per_fetch": round(request_count / fetches, 3) if fetches else None,
            "avg_rows_per_fetch": round(rows_received / fetches, 3) if fetches else None,
            "network_latency_ms": _latency_summary(network.get("network_latency_ms")),
            "requests_per_fetch": _latency_summary(network.get("requests_per_fetch")),
            "last_event_at_ms": network.get("last_event_at_ms"),
            "last_fetch": network.get("last_fetch") if isinstance(network.get("last_fetch"), dict) else None,
            "scope": "sum_of_actual_OKX_history_candle_request_durations_only; excludes cache, normalization and pagination sleep",
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
