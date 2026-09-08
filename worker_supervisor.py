"""Fail-closed supervision helpers for the continuous research worker army.

This module classifies runtime failures, fingerprints incidents, sanitizes bounded
diagnostics, and evaluates worker freshness. It has no broker, trade, signal,
promotion, repository-write, or deployment authority.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
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
MAX_DIAGNOSTIC_CHARS = max(512, min(int(os.getenv("WORKER_DIAGNOSTIC_MAX_CHARS", "2000")), 8000))
_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(authorization|api[_-]?key|access[_-]?token|refresh[_-]?token|token|secret|password)\b\s*[:=]\s*([^\s,;]+)"
)
_BEARER = re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._~+\-/=]{8,}")
_OPENAI_KEY = re.compile(r"\bsk-[A-Za-z0-9_-]{12,}\b")
_JWT = re.compile(r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b")
_ERROR_LINE = re.compile(r"(?:^|\s)([A-Za-z_][A-Za-z0-9_.]{0,100}(?:Error|Exception|Timeout))(?::|$)")


def sanitize_diagnostic(value: object, *, max_chars: int = MAX_DIAGNOSTIC_CHARS) -> str:
    """Return a bounded traceback tail with common credential forms redacted."""
    text = str(value or "").replace("\r\n", "\n").replace("\r", "\n")
    text = "".join(ch if ch == "\n" or ch == "\t" or ord(ch) >= 32 else "?" for ch in text)
    text = _SECRET_ASSIGNMENT.sub(lambda match: f"{match.group(1)}=<redacted>", text)
    text = _BEARER.sub("Bearer <redacted>", text)
    text = _OPENAI_KEY.sub("<redacted-key>", text)
    text = _JWT.sub("<redacted-jwt>", text)
    limit = max(128, min(int(max_chars), 8000))
    if len(text) > limit:
        text = "...<tail>...\n" + text[-limit:]
    return text.strip()


def diagnostic_fingerprint(diagnostic: object) -> str | None:
    sanitized = sanitize_diagnostic(diagnostic)
    if not sanitized:
        return None
    return hashlib.sha256(sanitized.encode("utf-8")).hexdigest()[:20]


def infer_error_type(diagnostic: object, fallback: str | None = None) -> str:
    """Prefer the final traceback exception class over a generic process exit."""
    sanitized = sanitize_diagnostic(diagnostic)
    for line in reversed(sanitized.splitlines()):
        match = _ERROR_LINE.search(line.strip())
        if match:
            return match.group(1).split(".")[-1]
    return str(fallback or "ProcessExitError")


def classify_failure(exit_code: int | None, error_type: str | None, diagnostic: object = None) -> str:
    name = f"{error_type or ''} {sanitize_diagnostic(diagnostic, max_chars=1000)}".lower()
    code = int(exit_code if exit_code is not None else -1)
    if code == -9 or "timeout" in name:
        return "timeout"
    if any(token in name for token in ("network", "connect", "http", "remote", "readtimeout", "dns")):
        return "network_or_exchange"
    if any(token in name for token in ("evidence", "json", "schema", "valueerror", "typeerror", "decode")):
        return "malformed_or_invalid_evidence"
    if any(token in name for token in ("memory", "resource", "oserror", "no space left")):
        return "resource_or_runtime"
    if code != 0:
        return "process_failure"
    return "none"


def incident_fingerprint(
    worker: str,
    classification: str,
    error_type: str | None,
    exit_code: int | None,
    diagnostic: object = None,
) -> str:
    payload = {
        "worker": str(worker),
        "classification": str(classification),
        "error_type": str(error_type or ""),
        "exit_code": int(exit_code if exit_code is not None else -1),
        "diagnostic_fingerprint": diagnostic_fingerprint(diagnostic),
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()[:20]


def record_incident(
    worker: str,
    exit_code: int,
    error_type: str | None,
    *,
    diagnostic: object = None,
    ledger_path: Path | str | None = None,
) -> dict[str, Any]:
    sanitized = sanitize_diagnostic(diagnostic)
    classification = classify_failure(exit_code, error_type, sanitized)
    incident = {
        "at_ms": int(time.time() * 1000),
        "worker": str(worker),
        "classification": classification,
        "error_type": str(error_type or "ProcessExitError"),
        "exit_code": int(exit_code),
        "diagnostic_fingerprint": diagnostic_fingerprint(sanitized),
        "fingerprint": incident_fingerprint(worker, classification, error_type, exit_code, sanitized),
        "research_only": True,
        "trade_authority": False,
        "promotion_authority": False,
        "write_authority": False,
    }
    persistent = dict(incident)
    if sanitized:
        persistent["diagnostic_excerpt"] = sanitized
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
            handle.write(json.dumps(persistent, sort_keys=True, separators=(",", ":")) + "\n")
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
