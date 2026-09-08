"""Always-on token-free coordinator plus bounded Python research worker army.

The coordinator observes production/state while the worker army continuously
runs research/backtest jobs. Neither component has live trade, promotion,
broker, or repository-write authority.
"""

from __future__ import annotations

import asyncio
import logging
import os
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from threading import Lock

import httpx
from fastapi import FastAPI

from continuous_worker_army import run_army, snapshot as worker_army_snapshot


PRODUCTION_HEALTH_URL = os.getenv(
    "PRODUCTION_HEALTH_URL",
    "https://tradingview-ai-crypto.onrender.com/health",
)
STATE_URL = os.getenv(
    "AI_STATE_URL",
    "https://raw.githubusercontent.com/rnnyrgs-web/tradingview-ai-crypto/main/AI_STATE.md",
)
POLL_SECONDS = max(30, int(os.getenv("COORDINATOR_POLL_SECONDS", "60")))
REQUEST_TIMEOUT_SECONDS = 15.0
WORKER_ARMY_ENABLED = os.getenv("WORKER_ARMY_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}

log = logging.getLogger(__name__)
_lock = Lock()
_status = {
    "started_at": None,
    "last_check_at": None,
    "production_ok": False,
    "state_ok": False,
    "state_last_updated": None,
    "consecutive_failures": 0,
    "last_error_type": None,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def validate_production_health(payload: object) -> bool:
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        return False
    operations = payload.get("operations")
    if not isinstance(operations, dict):
        return False
    return int(operations.get("recent_error_count") or 0) == 0


def parse_state_last_updated(content: str) -> str | None:
    prefix = "Last updated:"
    for line in content.splitlines()[:10]:
        if line.startswith(prefix):
            value = line.removeprefix(prefix).strip()
            return value or None
    return None


def observability_log_payload(army: object) -> dict:
    """Return a bounded, non-sensitive subset for private Render logs only."""
    if not isinstance(army, dict):
        army = {}
    observed = army.get("observability") if isinstance(army.get("observability"), dict) else {}
    cache = observed.get("cache") if isinstance(observed.get("cache"), dict) else {}
    network = observed.get("history_network") if isinstance(observed.get("history_network"), dict) else {}
    workers = observed.get("workers") if isinstance(observed.get("workers"), dict) else {}
    acc002 = observed.get("acc002") if isinstance(observed.get("acc002"), dict) else {}

    def compact_acc(name: str) -> dict:
        row = acc002.get(name) if isinstance(acc002.get(name), dict) else {}
        evidence = row.get("latest_evidence") if isinstance(row.get("latest_evidence"), dict) else {}
        selected = evidence.get("selected_evaluation") if isinstance(evidence.get("selected_evaluation"), dict) else {}
        return {
            "exit": row.get("last_exit_code"),
            "elapsed_s": row.get("elapsed_seconds"),
            "updated_at_ms": row.get("updated_at_ms"),
            "acc002_pass": selected.get("acc002_research_pass"),
            "survivorship_pass": selected.get("acc011_survivorship_pass"),
            "promotion_review": selected.get("eligible_for_promotion_review"),
        }

    cache_latency = cache.get("read_latency_ms") if isinstance(cache.get("read_latency_ms"), dict) else {}
    network_latency = network.get("latency_ms") if isinstance(network.get("latency_ms"), dict) else {}
    return {
        "cache_reads": cache.get("reads_observed"),
        "cache_hit_rate": cache.get("hit_rate"),
        "cache_rejection_rate": cache.get("rejection_rate"),
        "cache_p50_ms": cache_latency.get("p50"),
        "cache_p95_ms": cache_latency.get("p95"),
        "history_fetches": network.get("fetches"),
        "history_failures": network.get("failures"),
        "network_p50_ms": network_latency.get("p50"),
        "network_p95_ms": network_latency.get("p95"),
        "avg_requests_per_fetch": network.get("avg_requests_per_fetch"),
        "worker_completed": workers.get("completed"),
        "worker_failed": workers.get("failed"),
        "worker_timeouts": workers.get("timeouts"),
        "worker_failure_rate": workers.get("failure_rate"),
        "acc002_24h": compact_acc("cross-asset-rank-24h"),
        "acc002_7d": compact_acc("cross-asset-rank-7d"),
        "trade_authority": False,
        "promotion_authority": False,
        "signal_authority": False,
    }


async def check_once(client: httpx.AsyncClient) -> dict:
    result = {
        "last_check_at": _now(),
        "production_ok": False,
        "state_ok": False,
        "state_last_updated": None,
        "last_error_type": None,
    }
    try:
        production, state = await asyncio.gather(
            client.get(PRODUCTION_HEALTH_URL),
            client.get(STATE_URL),
        )
        production.raise_for_status()
        state.raise_for_status()
        result["production_ok"] = validate_production_health(production.json())
        result["state_last_updated"] = parse_state_last_updated(state.text)
        result["state_ok"] = bool(
            result["state_last_updated"] and "## EXACT NEXT STEP" in state.text
        )
    except (httpx.HTTPError, ValueError, TypeError) as exc:
        result["last_error_type"] = type(exc).__name__
        log.warning("coordinator check failed: %s", type(exc).__name__)
    return result


def apply_check(result: dict) -> None:
    with _lock:
        _status.update(result)
        if result["production_ok"] and result["state_ok"]:
            _status["consecutive_failures"] = 0
        else:
            _status["consecutive_failures"] += 1


async def coordinator_loop() -> None:
    timeout = httpx.Timeout(REQUEST_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        while True:
            apply_check(await check_once(client))
            if WORKER_ARMY_ENABLED:
                log.info("research_observability %s", observability_log_payload(worker_army_snapshot()))
            await asyncio.sleep(POLL_SECONDS)


@asynccontextmanager
async def lifespan(_: FastAPI):
    with _lock:
        _status["started_at"] = _now()
    tasks = [asyncio.create_task(coordinator_loop(), name="coordinator-watchdog")]
    if WORKER_ARMY_ENABLED:
        tasks.append(asyncio.create_task(run_army(), name="python-worker-army"))
    try:
        yield
    finally:
        for task in tasks:
            task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


app = FastAPI(title="Crypto Continuous Coordinator", lifespan=lifespan)


@app.get("/")
@app.get("/health")
def health() -> dict:
    with _lock:
        snapshot = dict(_status)
    army = worker_army_snapshot() if WORKER_ARMY_ENABLED else {"enabled": False}
    healthy = (
        snapshot["production_ok"]
        and snapshot["state_ok"]
        and snapshot["consecutive_failures"] < 3
    )
    return {
        "ok": healthy,
        "service": "crypto-continuous-coordinator",
        "mode": "observe_and_research_only",
        "ai_calls_normal_operation": 0,
        "trade_authority": False,
        "write_authority": False,
        "promotion_authority": False,
        "broker_connected": False,
        "research_only": True,
        "worker_army": army,
        **snapshot,
    }


@app.get("/workers")
def workers() -> dict:
    return worker_army_snapshot() if WORKER_ARMY_ENABLED else {"enabled": False}
