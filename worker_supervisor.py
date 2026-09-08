"""Fail-closed supervision helpers for the continuous research worker army.

This module classifies runtime failures, fingerprints incidents, and evaluates
worker freshness. It has no broker, trade, signal, promotion, repository-write,
or deployment authority.
"""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
import time
from pathlib import Path
from typing import Any


DEFAULT_LEDGER = Path(
    os.getenv(
        "WORKER_INCIDENT_LEDGER_PATH",
        str(Path(tempfile.gettempdir()) / "tradingview-ai-worker-incidents.jsonl"),
    )
)
MAX_LEDGER_BYTES = max(64_000, min(int(os.getenv("WORKER_INCIDENT_LEDGER_MAX_BYTES", "1000000")), 5_000_000))


def classify_failure(exit_code: int | None, error_type: str | None) -> str:
    name = str(error_type or "").lower()
    code = int(exit_code if exit_code is not None else -1)
    if code == -9 or "timeout" in name:
        return "timeout"
    if any(token in name for token in ("network", "connect", "http", "remote", "readtimeout")):
        return "network_or_exchange"
    if any(token in name for token in ("evidence", "json", "schema", "valueerror", "typeerror")):
        return "malformed_or_invalid_evidence"
    if any(token in name for token in ("memory", "resource", "oserror")):
        return "resource_or_runtime"
    if code != 0:
        return "process_failure"
    return "none"


def incident_fingerprint(worker: str, classification: str, error_type: str | None, exit_code: int | None) -> str:
    payload = {
        "worker": str(worker),
        "classification": str(classification),
        "error_type": str(error_type or ""),
        "exit_code": int(exit_code if exit_code is not None else -1),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:20]


def record_incident(worker: str, exit_code: int, error_type: str | None, *, ledger_path: Path | str | None = None) -> dict[str, Any]:
    classification = classify_failure(exit_code, error_type)
    incident = {
        "at_ms": int(time.time() * 1000),
        "worker": str(worker),
        "classification": classification,
        "error_type": str(error_type or "ProcessExitError"),
        "exit_code": int(exit_code),
        "fingerprint": incident_fingerprint(worker, classification, error_type, exit_code),
        "research_only": True,
        "trade_authority": False,
        "promotion_authority": False,
        "write_authority": False,
    }
    path = Path(ledger_path or DEFAULT_LEDGER)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists() and path.stat().st_size > MAX_LEDGER_BYTES:
            rotated = path.with_suffix(path.suffix + ".previous")
            try:
                os.replace(path, rotated)
            except OSError:
                pass
        with path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(incident, sort_keys=True, separators=(",", ":")) + "\n")
    except OSError:
        pass
    return incident


def worker_health(worker: dict[str, Any], *, now_monotonic: float, job_timeout_seconds: int, grace_seconds: int = 120) -> dict[str, Any]:
    state = str(worker.get("state") or "unknown")
    heartbeat = worker.get("heartbeat_monotonic")
    stale = False
    age = None
    if isinstance(heartbeat, (int, float)):
        age = max(0.0, float(now_monotonic) - float(heartbeat))
        stale = age > max(60, int(job_timeout_seconds) + int(grace_seconds))
    elif state not in {"starting", "unknown"}:
        stale = True
    crashed = state == "crashed"
    unhealthy = stale or crashed
    return {
        "healthy": not unhealthy,
        "stale": stale,
        "crashed": crashed,
        "heartbeat_age_seconds": round(age, 2) if age is not None else None,
    }


def supervisor_summary(workers: dict[str, Any], *, now_monotonic: float, job_timeout_seconds: int) -> dict[str, Any]:
    rows = {}
    stale = []
    crashed = []
    for name, worker in (workers or {}).items():
        if not isinstance(worker, dict):
            worker = {}
        health = worker_health(worker, now_monotonic=now_monotonic, job_timeout_seconds=job_timeout_seconds)
        rows[str(name)] = health
        if health["stale"]:
            stale.append(str(name))
        if health["crashed"]:
            crashed.append(str(name))
    return {
        "healthy": not stale and not crashed,
        "stale_workers": stale,
        "crashed_workers": crashed,
        "worker_health": rows,
        "research_only": True,
        "trade_authority": False,
        "promotion_authority": False,
        "write_authority": False,
    }
