"""Always-on, token-free coordinator watchdog.

This process observes production and the canonical repository handoff.  It is
deliberately unable to scan markets, publish branches, or approve trades.
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
            await asyncio.sleep(POLL_SECONDS)


@asynccontextmanager
async def lifespan(_: FastAPI):
    with _lock:
        _status["started_at"] = _now()
    task = asyncio.create_task(coordinator_loop())
    try:
        yield
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass


app = FastAPI(title="Crypto Continuous Coordinator", lifespan=lifespan)


@app.get("/")
@app.get("/health")
def health() -> dict:
    with _lock:
        snapshot = dict(_status)
    healthy = (
        snapshot["production_ok"]
        and snapshot["state_ok"]
        and snapshot["consecutive_failures"] < 3
    )
    return {
        "ok": healthy,
        "service": "crypto-continuous-coordinator",
        "mode": "observe_only",
        "ai_calls_normal_operation": 0,
        "trade_authority": False,
        **snapshot,
    }
