"""Bounded always-on Python worker army for continuous crypto research.

Heavy research remains strictly bounded by the existing compute ceiling. Cheap
learning/diagnostic roles run in separate lightweight lanes so they can keep
analyzing resolved outcomes and preparing experiments without stealing heavy
backtest capacity. All workers remain research-only with no broker, promotion,
GitHub-write, deployment, or live-trade authority.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from research_observability import record_worker_result, snapshot as research_metrics_snapshot
from worker_supervisor import infer_error_type, record_incident, sanitize_diagnostic, supervisor_summary

PROJECT_ROOT = Path(__file__).resolve().parent
MAX_CONCURRENT = max(1, min(int(os.getenv("WORKER_ARMY_MAX_CONCURRENT", "2")), 4))
LIGHTWEIGHT_MAX_CONCURRENT = max(1, min(int(os.getenv("WORKER_ARMY_LIGHTWEIGHT_MAX_CONCURRENT", "2")), 4))
JOB_TIMEOUT_SECONDS = max(300, min(int(os.getenv("WORKER_ARMY_JOB_TIMEOUT_SECONDS", "2700")), 3600))
REST_SECONDS = max(5, min(int(os.getenv("WORKER_ARMY_REST_SECONDS", "5")), 300))
MAX_ERROR_BACKOFF_SECONDS = max(30, min(int(os.getenv("WORKER_ARMY_MAX_ERROR_BACKOFF_SECONDS", "300")), 900))
HEARTBEAT_SECONDS = max(15, min(int(os.getenv("WORKER_ARMY_HEARTBEAT_SECONDS", "30")), 120))
SUPERVISOR_INTERVAL_SECONDS = max(10, min(int(os.getenv("WORKER_ARMY_SUPERVISOR_INTERVAL_SECONDS", "30")), 120))
TASK_RESTART_DELAY_SECONDS = max(5, min(int(os.getenv("WORKER_ARMY_TASK_RESTART_DELAY_SECONDS", "15")), 300))
NATURAL_HISTORY_RECHECK_SECONDS = max(300, min(int(os.getenv("WORKER_ARMY_NATURAL_HISTORY_RECHECK_SECONDS", "21600")), 86400))
ADAPTIVE_IDLE_RECHECK_SECONDS = max(60, min(int(os.getenv("WORKER_ARMY_ADAPTIVE_IDLE_RECHECK_SECONDS", "300")), 3600))
log = logging.getLogger("uvicorn.error")


@dataclass(frozen=True)
class WorkerSpec:
    name: str
    env: dict[str, str]
    script: str = "research_runner.py"
    compute_class: str = "heavy"


WORKERS = (
    WorkerSpec("major-btc", {"RESEARCH_SYMBOLS": "BTC-USDT", "RESEARCH_TIMEFRAMES": "15m,1H"}),
    WorkerSpec("major-eth", {"RESEARCH_SYMBOLS": "ETH-USDT", "RESEARCH_TIMEFRAMES": "15m,1H"}),
    WorkerSpec("major-sol", {"RESEARCH_SYMBOLS": "SOL-USDT", "RESEARCH_TIMEFRAMES": "15m,1H"}),
    WorkerSpec("major-xrp", {"RESEARCH_SYMBOLS": "XRP-USDT", "RESEARCH_TIMEFRAMES": "15m,1H"}),
    WorkerSpec("major-link", {"RESEARCH_SYMBOLS": "LINK-USDT", "RESEARCH_TIMEFRAMES": "15m,1H"}),
    WorkerSpec("pons", {"RESEARCH_SYMBOLS": "PONS-USDT-SWAP", "RESEARCH_TIMEFRAMES": "15m,1H,4H"}),
    WorkerSpec("universe-0", {"RESEARCH_SHARD_INDEX": "0", "RESEARCH_SHARD_COUNT": "8", "RESEARCH_TIMEFRAMES": "15m,1H"}),
    WorkerSpec("universe-1", {"RESEARCH_SHARD_INDEX": "1", "RESEARCH_SHARD_COUNT": "8", "RESEARCH_TIMEFRAMES": "15m,1H"}),
    WorkerSpec("universe-2", {"RESEARCH_SHARD_INDEX": "2", "RESEARCH_SHARD_COUNT": "8", "RESEARCH_TIMEFRAMES": "15m,1H"}),
    WorkerSpec("universe-3", {"RESEARCH_SHARD_INDEX": "3", "RESEARCH_SHARD_COUNT": "8", "RESEARCH_TIMEFRAMES": "15m,1H"}),
    WorkerSpec("universe-4", {"RESEARCH_SHARD_INDEX": "4", "RESEARCH_SHARD_COUNT": "8", "RESEARCH_TIMEFRAMES": "15m,1H"}),
    WorkerSpec("universe-5", {"RESEARCH_SHARD_INDEX": "5", "RESEARCH_SHARD_COUNT": "8", "RESEARCH_TIMEFRAMES": "15m,1H"}),
    WorkerSpec("universe-6", {"RESEARCH_SHARD_INDEX": "6", "RESEARCH_SHARD_COUNT": "8", "RESEARCH_TIMEFRAMES": "15m,1H"}),
    WorkerSpec("universe-7", {"RESEARCH_SHARD_INDEX": "7", "RESEARCH_SHARD_COUNT": "8", "RESEARCH_TIMEFRAMES": "15m,1H"}),
    WorkerSpec("swing-majors", {"RESEARCH_SYMBOLS": "BTC-USDT,ETH-USDT,SOL-USDT,XRP-USDT,LINK-USDT", "RESEARCH_TIMEFRAMES": "4H,1D"}),
    WorkerSpec(
        "cross-asset-rank-24h",
        {"CROSS_ASSET_HORIZON": "24h", "CROSS_ASSET_UNIVERSE_SIZE": "30", "CROSS_ASSET_BARS": "3000", "CROSS_ASSET_ROUND_TRIP_COST_BPS": "12"},
        script="cross_asset_runner.py",
    ),
    WorkerSpec(
        "cross-asset-rank-7d",
        {"CROSS_ASSET_HORIZON": "7d", "CROSS_ASSET_UNIVERSE_SIZE": "30", "CROSS_ASSET_BARS": "5000", "CROSS_ASSET_ROUND_TRIP_COST_BPS": "12"},
        script="cross_asset_runner.py",
    ),
    WorkerSpec("adaptive-accuracy", {}, script="research_adaptive_accuracy_runner.py"),
    WorkerSpec(
        "basis-falsification-btc",
        {"BASIS_RESEARCH_BASE": "BTC", "BASIS_RESEARCH_TARGET_POINTS": "4000", "BASIS_RESEARCH_MAX_PAGES": "40"},
        script="basis_falsification_runner.py",
    ),
    WorkerSpec("learning-diagnostics", {}, script="research_learning_runner.py", compute_class="lightweight"),
    WorkerSpec("experiment-factory", {}, script="research_experiment_factory_runner.py", compute_class="lightweight"),
)

SUMMARY_ENV_BY_SCRIPT = {
    "cross_asset_runner.py": "CROSS_ASSET_SUMMARY_PATH",
    "research_adaptive_accuracy_runner.py": "RESEARCH_ADAPTIVE_ACCURACY_SUMMARY_PATH",
    "basis_falsification_runner.py": "BASIS_FALSIFICATION_SUMMARY_PATH",
    "research_learning_runner.py": "RESEARCH_LEARNING_SUMMARY_PATH",
    "research_experiment_factory_runner.py": "RESEARCH_EXPERIMENT_SUMMARY_PATH",
}

_lock = Lock()
_status: dict[str, object] = {
    "enabled": True,
    "started_at": None,
    "max_concurrent": MAX_CONCURRENT,
    "lightweight_max_concurrent": LIGHTWEIGHT_MAX_CONCURRENT,
    "accuracy_reserved_slots": 1 if MAX_CONCURRENT >= 2 else 0,
    "job_timeout_seconds": JOB_TIMEOUT_SECONDS,
    "heartbeat_seconds": HEARTBEAT_SECONDS,
    "supervisor_interval_seconds": SUPERVISOR_INTERVAL_SECONDS,
    "max_error_backoff_seconds": MAX_ERROR_BACKOFF_SECONDS,
    "natural_history_recheck_seconds": NATURAL_HISTORY_RECHECK_SECONDS,
    "adaptive_idle_recheck_seconds": ADAPTIVE_IDLE_RECHECK_SECONDS,
    "worker_count": len(WORKERS),
    "heavy_worker_count": sum(1 for spec in WORKERS if spec.compute_class == "heavy"),
    "lightweight_worker_count": sum(1 for spec in WORKERS if spec.compute_class == "lightweight"),
    "active_jobs": 0,
    "completed_jobs": 0,
    "failed_jobs": 0,
    "task_restarts": 0,
    "last_completion_at": None,
    "last_supervisor_check_at": None,
    "workers": {},
    "trade_authority": False,
    "write_authority": False,
    "promotion_authority": False,
    "broker_connected": False,
    "research_only": True,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _touch_worker(name: str) -> None:
    with _lock:
        worker = (_status.get("workers") or {}).get(name)
        if isinstance(worker, dict):
            worker["heartbeat_at"] = _now()
            worker["heartbeat_monotonic"] = time.monotonic()


def snapshot() -> dict:
    now_mono = time.monotonic()
    with _lock:
        data = dict(_status)
        raw_workers = {k: dict(v) for k, v in (_status["workers"] or {}).items()}
    supervision = supervisor_summary(raw_workers, now_monotonic=now_mono, job_timeout_seconds=JOB_TIMEOUT_SECONDS)
    safe_workers = {}
    for name, row in raw_workers.items():
        row.pop("heartbeat_monotonic", None)
        row["health"] = supervision["worker_health"].get(name, {})
        safe_workers[name] = row
    data["workers"] = safe_workers
    data["supervisor"] = {
        "healthy": supervision["healthy"],
        "stale_workers": supervision["stale_workers"],
        "crashed_workers": supervision["crashed_workers"],
        "task_restarts": data.get("task_restarts", 0),
        "last_check_at": data.get("last_supervisor_check_at"),
        "trade_authority": False,
        "promotion_authority": False,
        "write_authority": False,
        "research_only": True,
    }
    data["observability"] = research_metrics_snapshot()
    return data


def _worker_env(spec: WorkerSpec, summary_path: str | None = None) -> dict[str, str]:
    env = dict(os.environ)
    env.update(
        {
            "RESEARCH_UNIVERSE_SIZE": "80",
            "RESEARCH_FORCE_SYMBOLS": "PONS-USDT-SWAP",
            "RESEARCH_BARS": os.getenv("WORKER_ARMY_RESEARCH_BARS", "5000"),
            "RESEARCH_THRESHOLD": os.getenv("WORKER_ARMY_RESEARCH_THRESHOLD", "2.25"),
            "RESEARCH_EXECUTION_NOTIONAL": os.getenv("WORKER_ARMY_EXECUTION_NOTIONAL", "5000"),
            "PYTHONPATH": str(PROJECT_ROOT),
        }
    )
    env.update(spec.env)
    summary_env = SUMMARY_ENV_BY_SCRIPT.get(spec.script)
    if summary_path and summary_env:
        env[summary_env] = summary_path
    if "RESEARCH_SYMBOLS" in spec.env:
        env["RESEARCH_SHARD_INDEX"] = "0"
        env["RESEARCH_SHARD_COUNT"] = "1"
        env["RESEARCH_FORCE_SYMBOLS"] = ""
    return env


def _is_accuracy_worker(spec: WorkerSpec) -> bool:
    return spec.script in {"cross_asset_runner.py", "research_adaptive_accuracy_runner.py"}


def _is_lightweight_worker(spec: WorkerSpec) -> bool:
    return spec.compute_class == "lightweight"


def _retry_delay_seconds(consecutive_failures: int) -> int:
    failures = max(0, int(consecutive_failures))
    if failures <= 0:
        return REST_SECONDS
    multiplier = 2 ** min(failures, 6)
    return min(MAX_ERROR_BACKOFF_SECONDS, max(REST_SECONDS, REST_SECONDS * multiplier))


def _success_recheck_delay_seconds(spec: WorkerSpec, evidence) -> int:
    """Slow only evidence-blocked loops; never disguise software/source failures."""
    if not isinstance(evidence, dict):
        return REST_SECONDS
    if spec.script == "basis_falsification_runner.py":
        return NATURAL_HISTORY_RECHECK_SECONDS
    if spec.script == "cross_asset_runner.py":
        failure_types = evidence.get("failure_type_counts") or {}
        pure_history_block = (
            evidence.get("research_blocked") is True
            and evidence.get("research_blocked_reason") == "insufficient_supported_liquidity_subsets"
            and int(evidence.get("failed_symbol_count") or 0) > 0
            and isinstance(failure_types, dict)
            and bool(failure_types)
            and set(failure_types) == {"InsufficientHistory"}
        )
        if pure_history_block:
            return NATURAL_HISTORY_RECHECK_SECONDS
    if spec.script == "research_adaptive_accuracy_runner.py":
        conclusion = str(evidence.get("evidence_conclusion") or "")
        if conclusion in {
            "no_dispatchable_hypothesis",
            "deferred_repeat_no_material_new_evidence",
            "pending_validation",
        }:
            return ADAPTIVE_IDLE_RECHECK_SECONDS
    return REST_SECONDS


def _read_diagnostic_tail(path: Path) -> str:
    try:
        raw = path.read_bytes()
    except OSError:
        return ""
    return sanitize_diagnostic(raw[-16_384:].decode("utf-8", errors="replace"))


async def _wait_for_process(process: asyncio.subprocess.Process, spec: WorkerSpec) -> tuple[int, str | None]:
    started = time.monotonic()
    while True:
        remaining = JOB_TIMEOUT_SECONDS - (time.monotonic() - started)
        if remaining <= 0:
            process.kill()
            await process.wait()
            return -9, "TimeoutError"
        try:
            code = await asyncio.wait_for(process.wait(), timeout=min(HEARTBEAT_SECONDS, remaining))
            return int(code), None
        except asyncio.TimeoutError:
            _touch_worker(spec.name)


async def _run_once(spec: WorkerSpec, semaphore: asyncio.Semaphore) -> int:
    with _lock:
        workers = _status["workers"]
        previous = workers.get(spec.name, {})
        workers[spec.name] = {
            **(previous if isinstance(previous, dict) else {}),
            "state": "queued",
            "script": spec.script,
            "compute_class": spec.compute_class,
            "next_retry_delay_seconds": 0,
            "heartbeat_at": _now(),
            "heartbeat_monotonic": time.monotonic(),
        }
    async with semaphore:
        with _lock:
            _status["active_jobs"] = int(_status["active_jobs"]) + 1
            workers = _status["workers"]
            previous = workers.get(spec.name, {})
            workers[spec.name] = {
                "state": "running",
                "script": spec.script,
                "compute_class": spec.compute_class,
                "last_started_at": _now(),
                "last_finished_at": previous.get("last_finished_at"),
                "last_exit_code": previous.get("last_exit_code"),
                "last_error_type": None,
                "last_incident": previous.get("last_incident"),
                "consecutive_failures": int(previous.get("consecutive_failures") or 0),
                "next_retry_delay_seconds": 0,
                "heartbeat_at": _now(),
                "heartbeat_monotonic": time.monotonic(),
            }

        started = time.monotonic()
        exit_code = None
        error_type = None
        evidence = None
        diagnostic = ""
        try:
            with tempfile.TemporaryDirectory(prefix=f"crypto-{spec.name}-") as tmpdir:
                summary_path = str(Path(tmpdir) / "evidence-summary.json")
                stderr_path = Path(tmpdir) / "worker-stderr.log"
                with stderr_path.open("wb") as stderr_handle:
                    process = await asyncio.create_subprocess_exec(
                        sys.executable,
                        str(PROJECT_ROOT / spec.script),
                        cwd=tmpdir,
                        env=_worker_env(spec, summary_path),
                        stdout=asyncio.subprocess.DEVNULL,
                        stderr=stderr_handle,
                    )
                    exit_code, error_type = await _wait_for_process(process, spec)
                if exit_code != 0:
                    diagnostic = _read_diagnostic_tail(stderr_path)
                    error_type = infer_error_type(diagnostic, error_type)
                if exit_code == 0 and spec.script in SUMMARY_ENV_BY_SCRIPT:
                    try:
                        evidence = json.loads(Path(summary_path).read_text(encoding="utf-8"))
                    except (OSError, ValueError, TypeError) as exc:
                        exit_code = -1
                        error_type = "EvidenceSummaryError"
                        diagnostic = sanitize_diagnostic(f"{type(exc).__name__}: failed to read worker evidence summary")
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            exit_code = -1
            error_type = type(exc).__name__
            diagnostic = sanitize_diagnostic(f"{type(exc).__name__}: worker launcher exception")

        exit_code = int(exit_code if exit_code is not None else -1)
        elapsed = round(time.monotonic() - started, 2)
        incident = None
        if exit_code != 0:
            error_type = error_type or "ProcessExitError"
            incident = record_incident(spec.name, exit_code, error_type, diagnostic=diagnostic)
            compact = diagnostic.replace("\n", " | ") if diagnostic else "<none>"
            log.error(
                "worker_failure worker=%s exit=%s error_type=%s classification=%s incident=%s diagnostic_fp=%s diagnostic=%s",
                spec.name,
                exit_code,
                error_type,
                incident.get("classification"),
                incident.get("fingerprint"),
                incident.get("diagnostic_fingerprint"),
                compact,
            )
        with _lock:
            previous_failures = int(_status["workers"][spec.name].get("consecutive_failures") or 0)
            consecutive_failures = 0 if exit_code == 0 else previous_failures + 1
            retry_delay = _retry_delay_seconds(consecutive_failures)
            _status["active_jobs"] = max(0, int(_status["active_jobs"]) - 1)
            _status["completed_jobs"] = int(_status["completed_jobs"]) + 1
            if exit_code != 0:
                _status["failed_jobs"] = int(_status["failed_jobs"]) + 1
            _status["last_completion_at"] = _now()
            _status["workers"][spec.name] = {
                "state": "resting" if exit_code == 0 else "error_backoff",
                "script": spec.script,
                "compute_class": spec.compute_class,
                "last_started_at": _status["workers"][spec.name].get("last_started_at"),
                "last_finished_at": _now(),
                "last_exit_code": exit_code,
                "last_error_type": error_type,
                "last_incident": incident,
                "elapsed_seconds": elapsed,
                "latest_evidence": evidence,
                "consecutive_failures": consecutive_failures,
                "next_retry_delay_seconds": retry_delay,
                "heartbeat_at": _now(),
                "heartbeat_monotonic": time.monotonic(),
            }
        try:
            record_worker_result(spec.name, exit_code, elapsed, evidence)
        except OSError:
            pass
        return exit_code


async def _worker_loop(spec: WorkerSpec, semaphore: asyncio.Semaphore) -> None:
    await asyncio.sleep((sum(spec.name.encode("utf-8")) % 17) + 1)
    consecutive_failures = 0
    while True:
        _touch_worker(spec.name)
        exit_code = await _run_once(spec, semaphore)
        consecutive_failures = 0 if exit_code == 0 else consecutive_failures + 1
        delay = _retry_delay_seconds(consecutive_failures)
        if exit_code == 0:
            with _lock:
                evidence = (_status["workers"].get(spec.name) or {}).get("latest_evidence")
            delay = max(delay, _success_recheck_delay_seconds(spec, evidence))
        with _lock:
            row = _status["workers"].get(spec.name, {})
            if isinstance(row, dict):
                row["state"] = "resting" if exit_code == 0 else "error_backoff"
                row["next_retry_delay_seconds"] = delay
        slept = 0
        while slept < delay:
            chunk = min(HEARTBEAT_SECONDS, delay - slept)
            await asyncio.sleep(chunk)
            slept += chunk
            _touch_worker(spec.name)


def _initial_worker_state(spec: WorkerSpec) -> dict:
    return {
        "state": "starting",
        "script": spec.script,
        "compute_class": spec.compute_class,
        "last_started_at": None,
        "last_finished_at": None,
        "last_exit_code": None,
        "last_error_type": None,
        "last_incident": None,
        "consecutive_failures": 0,
        "next_retry_delay_seconds": 0,
        "heartbeat_at": _now(),
        "heartbeat_monotonic": time.monotonic(),
    }


def _build_lanes() -> dict[str, asyncio.Semaphore]:
    lightweight_lane = asyncio.Semaphore(LIGHTWEIGHT_MAX_CONCURRENT)
    heavy_specs = [spec for spec in WORKERS if not _is_lightweight_worker(spec)]
    if MAX_CONCURRENT == 1:
        heavy_shared = asyncio.Semaphore(1)
        return {spec.name: (lightweight_lane if _is_lightweight_worker(spec) else heavy_shared) for spec in WORKERS}
    accuracy_lane = asyncio.Semaphore(1)
    general_lane = asyncio.Semaphore(MAX_CONCURRENT - 1)
    lanes = {}
    for spec in WORKERS:
        if _is_lightweight_worker(spec):
            lanes[spec.name] = lightweight_lane
        elif _is_accuracy_worker(spec):
            lanes[spec.name] = accuracy_lane
        else:
            lanes[spec.name] = general_lane
    assert len(heavy_specs) >= 1
    return lanes


async def run_army() -> None:
    with _lock:
        _status["started_at"] = _now()
        _status["workers"] = {spec.name: _initial_worker_state(spec) for spec in WORKERS}
    lanes = _build_lanes()
    specs = {spec.name: spec for spec in WORKERS}
    tasks = {name: asyncio.create_task(_worker_loop(spec, lanes[name]), name=name) for name, spec in specs.items()}
    shutting_down = False
    try:
        while True:
            done, _ = await asyncio.wait(list(tasks.values()), timeout=SUPERVISOR_INTERVAL_SECONDS, return_when=asyncio.FIRST_COMPLETED)
            with _lock:
                _status["last_supervisor_check_at"] = _now()
            for task in done:
                name = task.get_name()
                if shutting_down:
                    continue
                error_type = "WorkerLoopExit"
                diagnostic = ""
                try:
                    exc = task.exception()
                    if exc is not None:
                        error_type = type(exc).__name__
                        diagnostic = sanitize_diagnostic(f"{type(exc).__name__}: logical worker loop exited unexpectedly")
                except asyncio.CancelledError:
                    error_type = "CancelledError"
                incident = record_incident(name, -1, error_type, diagnostic=diagnostic)
                with _lock:
                    previous = _status["workers"].get(name, {})
                    _status["task_restarts"] = int(_status["task_restarts"]) + 1
                    _status["workers"][name] = {
                        **(previous if isinstance(previous, dict) else {}),
                        "state": "crashed",
                        "last_error_type": error_type,
                        "last_incident": incident,
                        "heartbeat_at": _now(),
                        "heartbeat_monotonic": time.monotonic(),
                    }
                log.error(
                    "worker_loop_restart worker=%s error_type=%s incident=%s diagnostic_fp=%s",
                    name,
                    error_type,
                    incident.get("fingerprint"),
                    incident.get("diagnostic_fingerprint"),
                )
                await asyncio.sleep(TASK_RESTART_DELAY_SECONDS)
                spec = specs[name]
                tasks[name] = asyncio.create_task(_worker_loop(spec, lanes[name]), name=name)
    finally:
        shutting_down = True
        for task in tasks.values():
            task.cancel()
        await asyncio.gather(*tasks.values(), return_exceptions=True)
