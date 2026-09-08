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


PROJECT_ROOT = Path(__file__).resolve().parent
MAX_CONCURRENT = max(1, min(int(os.getenv("WORKER_ARMY_MAX_CONCURRENT", "2")), 4))
JOB_TIMEOUT_SECONDS = max(300, min(int(os.getenv("WORKER_ARMY_JOB_TIMEOUT_SECONDS", "2700")), 3600))
REST_SECONDS = max(5, min(int(os.getenv("WORKER_ARMY_REST_SECONDS", "5")), 300))
MAX_ERROR_BACKOFF_SECONDS = max(30, min(int(os.getenv("WORKER_ARMY_MAX_ERROR_BACKOFF_SECONDS", "300")), 900))


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
    "max_error_backoff_seconds": MAX_ERROR_BACKOFF_SECONDS,
    "worker_count": len(WORKERS),
    "active_jobs": 0,
    "completed_jobs": 0,
    "failed_jobs": 0,
    "last_completion_at": None,
    "workers": {},
    "trade_authority": False,
    "write_authority": False,
    "promotion_authority": False,
    "broker_connected": False,
    "research_only": True,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def snapshot() -> dict:
    with _lock:
        data = dict(_status)
        data["workers"] = {k: dict(v) for k, v in (_status["workers"] or {}).items()}
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
    """Bound retries so unhealthy workers cannot monopolize scarce heavy slots."""
    failures = max(0, int(consecutive_failures))
    if failures <= 0:
        return REST_SECONDS
    multiplier = 2 ** min(failures, 6)
    return min(MAX_ERROR_BACKOFF_SECONDS, max(REST_SECONDS, REST_SECONDS * multiplier))


async def _run_once(spec: WorkerSpec, semaphore: asyncio.Semaphore) -> int:
    async with semaphore:
        with _lock:
            _status["active_jobs"] = int(_status["active_jobs"]) + 1
            workers = _status["workers"]
            previous = workers.get(spec.name, {})
            workers[spec.name] = {
                "state": "running",
                "script": spec.script,
                "last_started_at": _now(),
                "last_finished_at": previous.get("last_finished_at"),
                "last_exit_code": previous.get("last_exit_code"),
                "last_error_type": None,
                "consecutive_failures": int(previous.get("consecutive_failures") or 0),
                "next_retry_delay_seconds": 0,
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
                try:
                    exit_code = await asyncio.wait_for(process.wait(), timeout=JOB_TIMEOUT_SECONDS)
                except asyncio.TimeoutError:
                    process.kill()
                    await process.wait()
                    exit_code = -9
                    error_type = "TimeoutError"
                if exit_code == 0 and spec.script == "cross_asset_runner.py":
                    try:
                        evidence = json.loads(Path(summary_path).read_text(encoding="utf-8"))
                    except (OSError, ValueError, TypeError):
                        exit_code = -1
                        error_type = "EvidenceSummaryError"
        except Exception as exc:
            exit_code = -1
            error_type = type(exc).__name__

        exit_code = int(exit_code if exit_code is not None else -1)
        elapsed = round(time.monotonic() - started, 2)
        with _lock:
            previous_failures = int(_status["workers"][spec.name].get("consecutive_failures") or 0)
            consecutive_failures = 0 if exit_code == 0 else previous_failures + 1
            retry_delay = _retry_delay_seconds(consecutive_failures)
            _status["active_jobs"] = max(0, int(_status["active_jobs"]) - 1)
            _status["completed_jobs"] = int(_status["completed_jobs"]) + 1
            if exit_code != 0:
                _status["failed_jobs"] = int(_status["failed_jobs"]) + 1
                error_type = error_type or "ProcessExitError"
            _status["last_completion_at"] = _now()
            _status["workers"][spec.name] = {
                "state": "resting" if exit_code == 0 else "error_backoff",
                "script": spec.script,
                "last_started_at": _status["workers"][spec.name].get("last_started_at"),
                "last_finished_at": _now(),
                "last_exit_code": exit_code,
                "last_error_type": error_type,
                "elapsed_seconds": elapsed,
                "latest_evidence": evidence,
                "consecutive_failures": consecutive_failures,
                "next_retry_delay_seconds": retry_delay,
            }
        return exit_code


async def _worker_loop(spec: WorkerSpec, semaphore: asyncio.Semaphore) -> None:
    await asyncio.sleep((sum(spec.name.encode("utf-8")) % 17) + 1)
    consecutive_failures = 0
    while True:
        exit_code = await _run_once(spec, semaphore)
        consecutive_failures = 0 if exit_code == 0 else consecutive_failures + 1
        await asyncio.sleep(_retry_delay_seconds(consecutive_failures))


async def run_army() -> None:
    with _lock:
        _status["started_at"] = _now()
        _status["workers"] = {
            spec.name: {
                "state": "starting",
                "script": spec.script,
                "last_started_at": None,
                "last_finished_at": None,
                "last_exit_code": None,
                "last_error_type": None,
                "consecutive_failures": 0,
                "next_retry_delay_seconds": 0,
            }
            for spec in WORKERS
        }
    if MAX_CONCURRENT == 1:
        shared = asyncio.Semaphore(1)
        lanes = {spec.name: shared for spec in WORKERS}
    else:
        accuracy_lane = asyncio.Semaphore(1)
        general_lane = asyncio.Semaphore(MAX_CONCURRENT - 1)
        lanes = {
            spec.name: accuracy_lane if _is_accuracy_worker(spec) else general_lane
            for spec in WORKERS
        }
    tasks = [asyncio.create_task(_worker_loop(spec, lanes[spec.name]), name=spec.name) for spec in WORKERS]
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
