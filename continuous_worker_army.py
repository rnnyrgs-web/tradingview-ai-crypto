"""Bounded always-on Python worker army for continuous crypto research.

The army runs persistent logical worker loops on one Render service while
strictly limiting simultaneous heavy subprocesses. Workers are research-only:
they have no broker, promotion, GitHub-write, or live-trade authority.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import tempfile
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from research_observability import record_worker_result, snapshot as research_metrics_snapshot
from worker_supervisor import record_incident, supervisor_summary


PROJECT_ROOT = Path(__file__).resolve().parent
MAX_CONCURRENT = max(1, min(int(os.getenv("WORKER_ARMY_MAX_CONCURRENT", "2")), 4))
JOB_TIMEOUT_SECONDS = max(300, min(int(os.getenv("WORKER_ARMY_JOB_TIMEOUT_SECONDS", "2700")), 3600))
REST_SECONDS = max(5, min(int(os.getenv("WORKER_ARMY_REST_SECONDS", "5")), 300))
MAX_ERROR_BACKOFF_SECONDS = max(30, min(int(os.getenv("WORKER_ARMY_MAX_ERROR_BACKOFF_SECONDS", "300")), 900))
HEARTBEAT_SECONDS = max(15, min(int(os.getenv("WORKER_ARMY_HEARTBEAT_SECONDS", "30")), 120))
SUPERVISOR_INTERVAL_SECONDS = max(10, min(int(os.getenv("WORKER_ARMY_SUPERVISOR_INTERVAL_SECONDS", "30")), 120))
TASK_RESTART_DELAY_SECONDS = max(5, min(int(os.getenv("WORKER_ARMY_TASK_RESTART_DELAY_SECONDS", "15")), 300))


@dataclass(frozen=True)
class WorkerSpec:
    name: str
    env: dict[str, str]
    script: str = "research_runner.py"


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
        {
            "CROSS_ASSET_HORIZON": "24h",
            "CROSS_ASSET_UNIVERSE_SIZE": "30",
            "CROSS_ASSET_BARS": "3000",
            "CROSS_ASSET_ROUND_TRIP_COST_BPS": "12",
        },
        script="cross_asset_runner.py",
    ),
    WorkerSpec(
        "cross-asset-rank-7d",
        {
            "CROSS_ASSET_HORIZON": "7d",
            "CROSS_ASSET_UNIVERSE_SIZE": "30",
            "CROSS_ASSET_BARS": "5000",
            "CROSS_ASSET_ROUND_TRIP_COST_BPS": "12",
        },
        script="cross_asset_runner.py",
    ),
)

_lock = Lock()
_status: dict[str, object] = {
    "enabled": True,
    "started_at": None,
    "max_concurrent": MAX_CONCURRENT,
    "accuracy_reserved_slots": 1 if MAX_CONCURRENT >= 2 else 0,
    "job_timeout_seconds": JOB_TIMEOUT_SECONDS,
    "heartbeat_seconds": HEARTBEAT_SECONDS,
    "supervisor_interval_seconds": SUPERVISOR_INTERVAL_SECONDS,
    "max_error_backoff_seconds": MAX_ERROR_BACKOFF_SECONDS,
    "worker_count": len(WORKERS),
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
    if summary_path and spec.script == "cross_asset_runner.py":
        env["CROSS_ASSET_SUMMARY_PATH"] = summary_path
    if "RESEARCH_SYMBOLS" in spec.env:
        env["RESEARCH_SHARD_INDEX"] = "0"
        env["RESEARCH_SHARD_COUNT"] = "1"
        env["RESEARCH_FORCE_SYMBOLS"] = ""
    return env


def _is_accuracy_worker(spec: WorkerSpec) -> bool:
    return spec.script == "cross_asset_runner.py"


def _retry_delay_seconds(consecutive_failures: int) -> int:
    failures = max(0, int(consecutive_failures))
    if failures <= 0:
        return REST_SECONDS
    multiplier = 2 ** min(failures, 6)
    return min(MAX_ERROR_BACKOFF_SECONDS, max(REST_SECONDS, REST_SECONDS * multiplier))


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
    async with semaphore:
        with _lock:
            _status["active_jobs"] = int(_status["active_jobs"]) + 1
            workers = _status["workers"]
            previous = workers.get(spec.name, {})
            now_mono = time.monotonic()
            workers[spec.name] = {
                "state": "running",
                "script": spec.script,
                "last_started_at": _now(),
                "last_finished_at": previous.get("last_finished_at"),
                "last_exit_code": previous.get("last_exit_code"),
                "last_error_type": None,
                "last_incident": previous.get("last_incident"),
                "consecutive_failures": int(previous.get("consecutive_failures") or 0),
                "next_retry_delay_seconds": 0,
                "heartbeat_at": _now(),
                "heartbeat_monotonic": now_mono,
            }

        started = time.monotonic()
        exit_code = None
        error_type = None
        evidence = None
        try:
            with tempfile.TemporaryDirectory(prefix=f"crypto-{spec.name}-") as tmpdir:
                summary_path = str(Path(tmpdir) / "evidence-summary.json")
                process = await asyncio.create_subprocess_exec(
                    sys.executable,
                    str(PROJECT_ROOT / spec.script),
                    cwd=tmpdir,
                    env=_worker_env(spec, summary_path),
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                exit_code, error_type = await _wait_for_process(process, spec)
                if exit_code == 0 and spec.script == "cross_asset_runner.py":
                    try:
                        evidence = json.loads(Path(summary_path).read_text(encoding="utf-8"))
                    except (OSError, ValueError, TypeError):
                        exit_code = -1
                        error_type = "EvidenceSummaryError"
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            exit_code = -1
            error_type = type(exc).__name__

        exit_code = int(exit_code if exit_code is not None else -1)
        elapsed = round(time.monotonic() - started, 2)
        incident = None
        if exit_code != 0:
            error_type = error_type or "ProcessExitError"
            incident = record_incident(spec.name, exit_code, error_type)
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


async def run_army() -> None:
    with _lock:
        _status["started_at"] = _now()
        _status["workers"] = {spec.name: _initial_worker_state(spec) for spec in WORKERS}
    if MAX_CONCURRENT == 1:
        shared = asyncio.Semaphore(1)
        lanes = {spec.name: shared for spec in WORKERS}
    else:
        accuracy_lane = asyncio.Semaphore(1)
        general_lane = asyncio.Semaphore(MAX_CONCURRENT - 1)
        lanes = {spec.name: accuracy_lane if _is_accuracy_worker(spec) else general_lane for spec in WORKERS}

    specs = {spec.name: spec for spec in WORKERS}
    tasks = {name: asyncio.create_task(_worker_loop(spec, lanes[name]), name=name) for name, spec in specs.items()}
    shutting_down = False
    try:
        while True:
            done, _ = await asyncio.wait(
                list(tasks.values()),
                timeout=SUPERVISOR_INTERVAL_SECONDS,
                return_when=asyncio.FIRST_COMPLETED,
            )
            with _lock:
                _status["last_supervisor_check_at"] = _now()
            for task in done:
                name = task.get_name()
                if shutting_down:
                    continue
                error_type = "WorkerLoopExit"
                try:
                    exc = task.exception()
                    if exc is not None:
                        error_type = type(exc).__name__
                except asyncio.CancelledError:
                    error_type = "CancelledError"
                incident = record_incident(name, -1, error_type)
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
                await asyncio.sleep(TASK_RESTART_DELAY_SECONDS)
                spec = specs[name]
                tasks[name] = asyncio.create_task(_worker_loop(spec, lanes[name]), name=name)
    finally:
        shutting_down = True
        for task in tasks.values():
            task.cancel()
        await asyncio.gather(*tasks.values(), return_exceptions=True)
