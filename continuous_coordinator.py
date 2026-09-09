"""Always-on token-free coordinator plus bounded Python research worker army.

The coordinator observes production/state while the worker army continuously
runs research/backtest jobs. Neither component has live trade, promotion,
broker, deployment, rollback, or repository-write authority.
"""

from __future__ import annotations

import asyncio
import logging
import os
import time
from collections import Counter
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from threading import Lock

import httpx
from fastapi import FastAPI

from continuous_worker_army import run_army, snapshot as worker_army_snapshot
from cross_asset_runner import MIN_LIQUIDITY_SUBSET_COVERAGE
from deployment_canary import evaluate_canary


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

log = logging.getLogger("uvicorn.error")
_lock = Lock()
_started_monotonic = time.monotonic()
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
    supervisor = army.get("supervisor") if isinstance(army.get("supervisor"), dict) else {}

    def compact_acc(name: str) -> dict:
        row = acc002.get(name) if isinstance(acc002.get(name), dict) else {}
        evidence = row.get("latest_evidence") if isinstance(row.get("latest_evidence"), dict) else {}
        selected = evidence.get("selected_oos") if isinstance(evidence.get("selected_oos"), dict) else {}
        supported_subsets = evidence.get("supported_liquidity_subsets")
        if not isinstance(supported_subsets, list):
            supported_subsets = None
        failures = evidence.get("failed_symbols") if isinstance(evidence.get("failed_symbols"), list) else []
        failure_types = Counter(
            str(item.get("error_type"))
            for item in failures
            if isinstance(item, dict) and item.get("error_type")
        )
        failed_symbol_count = evidence.get("failed_symbol_count")
        if not isinstance(failed_symbol_count, int) or isinstance(failed_symbol_count, bool):
            failed_symbol_count = len(failures)
        return {
            "exit": row.get("last_exit_code"),
            "elapsed_s": row.get("elapsed_seconds"),
            "updated_at_ms": row.get("updated_at_ms"),
            "research_blocked": evidence.get("research_blocked"),
            "research_blocked_reason": evidence.get("research_blocked_reason"),
            "untouched_oos_opened": evidence.get("untouched_oos_opened"),
            "acc002_pass": selected.get("acc002_research_pass"),
            "survivorship_pass": selected.get("acc011_survivorship_pass"),
            "promotion_review": selected.get("eligible_for_promotion_review"),
            "universe_requested": evidence.get("universe_requested"),
            "universe_resolved": evidence.get("universe_resolved"),
            "supported_liquidity_subsets": supported_subsets,
            "minimum_subset_coverage": MIN_LIQUIDITY_SUBSET_COVERAGE if supported_subsets is not None else None,
            "failed_symbol_count": failed_symbol_count,
            "failure_type_counts": dict(sorted(failure_types.items())),
        }

    cache_latency = cache.get("read_latency_ms") if isinstance(cache.get("read_latency_ms"), dict) else {}
    network_latency = network.get("network_latency_ms") if isinstance(network.get("network_latency_ms"), dict) else {}
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
        "supervisor_healthy": supervisor.get("healthy"),
        "stale_workers": supervisor.get("stale_workers"),
        "crashed_workers": supervisor.get("crashed_workers"),
        "task_restarts": supervisor.get("task_restarts"),
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
        result["state_ok"] = bool(result["state_last_updated"] and "## EXACT NEXT STEP" in state.text)
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


def canary_snapshot(army: dict | None = None) -> dict:
    with _lock:
        coordinator = dict(_status)
    if army is None:
        army = worker_army_snapshot() if WORKER_ARMY_ENABLED else {"enabled": False, "supervisor": {"healthy": True}}
    return evaluate_canary(
        coordinator,
        army,
        uptime_seconds=time.monotonic() - _started_monotonic,
    )


async def coordinator_loop() -> None:
    timeout = httpx.Timeout(REQUEST_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        while True:
            apply_check(await check_once(client))
            if WORKER_ARMY_ENABLED:
                army = worker_army_snapshot()
                log.info("research_observability %s", observability_log_payload(army))
                canary = canary_snapshot(army)
                log.info(
                    "deployment_canary status=%s rollback_recommended=%s reasons=%s worker_samples=%s",
                    canary.get("status"),
                    canary.get("rollback_recommended"),
                    canary.get("reasons"),
                    canary.get("worker_samples"),
                )
            await asyncio.sleep(POLL_SECONDS)


@asynccontextmanager
async def lifespan(_: FastAPI):
    global _started_monotonic
    _started_monotonic = time.monotonic()
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
    army = worker_army_snapshot() if WORKER_ARMY_ENABLED else {"enabled": False, "supervisor": {"healthy": True}}
    supervisor = army.get("supervisor") if isinstance(army.get("supervisor"), dict) else {}
    supervisor_ok = supervisor.get("healthy") is True if WORKER_ARMY_ENABLED else True
    canary = canary_snapshot(army)
    healthy = (
        snapshot["production_ok"]
        and snapshot["state_ok"]
        and snapshot["consecutive_failures"] < 3
        and supervisor_ok
        and canary.get("rollback_recommended") is not True
    )
    return {
        "ok": healthy,
        "service": "crypto-continuous-coordinator",
        "mode": "observe_research_and_canary_only",
        "ai_calls_normal_operation": 0,
        "trade_authority": False,
        "write_authority": False,
        "promotion_authority": False,
        "deployment_authority": False,
        "automatic_rollback_authority": False,
        "broker_connected": False,
        "research_only": True,
        "deployment_canary": canary,
        "worker_army": army,
        **snapshot,
    }
