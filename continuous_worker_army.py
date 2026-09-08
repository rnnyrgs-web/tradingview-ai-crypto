"""Bounded always-on Python worker army for continuous crypto research.

The army runs persistent logical worker loops on one Render service while
strictly limiting simultaneous heavy subprocesses. Workers are research-only:
they have no broker, promotion, GitHub-write, or live-trade authority.
"""

from __future__ import annotations

import asyncio
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


@dataclass(frozen=True)
class WorkerSpec:
    name: str
    env: dict[str, str]
    script: str = "research_runner.py"


# Persistent logical workers keep cycling 24/7. A bounded semaphore prevents
# one inexpensive machine from being overloaded. ACC-002 gets a dedicated loop.
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
        "cross-asset-rank",
        {
            "CROSS_ASSET_UNIVERSE_SIZE": "30",
            "CROSS_ASSET_BARS": "1200",
            "CROSS_ASSET_BAR": "1H",
            "CROSS_ASSET_FORWARD_BARS": "24",
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
    "job_timeout_seconds": JOB_TIMEOUT_SECONDS,
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


def _worker_env(spec: WorkerSpec) -> dict[str, str]:
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
    if "RESEARCH_SYMBOLS" in spec.env:
        env["RESEARCH_SHARD_INDEX"] = "0"
        env["RESEARCH_SHARD_COUNT"] = "1"
        env["RESEARCH_FORCE_SYMBOLS"] = ""
    return env


async def _run_once(spec: WorkerSpec, semaphore: asyncio.Semaphore) -> None:
    async with semaphore:
        with _lock:
            _status["active_jobs"] = int(_status["active_jobs"]) + 1
            workers = _status["workers"]
            workers[spec.name] = {
                "state": "running",
                "script": spec.script,
                "last_started_at": _now(),
                "last_finished_at": workers.get(spec.name, {}).get("last_finished_at"),
                "last_exit_code": workers.get(spec.name, {}).get("last_exit_code"),
                "last_error_type": None,
            }

        started = time.monotonic()
        exit_code = None
        error_type = None
        try:
            with tempfile.TemporaryDirectory(prefix=f"crypto-{spec.name}-") as tmpdir:
                process = await asyncio.create_subprocess_exec(
                    sys.executable,
                    str(PROJECT_ROOT / spec.script),
                    cwd=tmpdir,
                    env=_worker_env(spec),
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
        except Exception as exc:
            exit_code = -1
            error_type = type(exc).__name__

        elapsed = round(time.monotonic() - started, 2)
        with _lock:
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
                "elapsed_seconds": elapsed,
            }


async def _worker_loop(spec: WorkerSpec, semaphore: asyncio.Semaphore) -> None:
    await asyncio.sleep((sum(spec.name.encode("utf-8")) % 17) + 1)
    while True:
        await _run_once(spec, semaphore)
        await asyncio.sleep(REST_SECONDS)


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
            }
            for spec in WORKERS
        }
    semaphore = asyncio.Semaphore(MAX_CONCURRENT)
    tasks = [asyncio.create_task(_worker_loop(spec, semaphore), name=spec.name) for spec in WORKERS]
    try:
        await asyncio.gather(*tasks)
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)
