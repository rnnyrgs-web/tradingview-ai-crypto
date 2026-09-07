"""Always-on production watchdog plus bounded continuous AI research observer.

The process stays alive 24/7. The deterministic watchdog checks production and
AI_STATE every minute. A separate AI loop continuously reviews that evidence on
a bounded cadence and records a compact research/operations assessment.

The AI observer is intentionally read-only: it cannot scan markets, write code,
publish branches, approve promotions, or authorize trades. Development changes
continue through the existing specialist -> security -> lead integration gates.
"""

from __future__ import annotations

import asyncio
import json
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
AI_INTERVAL_SECONDS = max(60, int(os.getenv("CONTINUOUS_AI_INTERVAL_SECONDS", "300")))
AI_MODEL = os.getenv("CONTINUOUS_AI_MODEL", os.getenv("OPENAI_AGENT_MODEL", "gpt-5.6-luna")).strip()
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
REQUEST_TIMEOUT_SECONDS = 15.0
AI_TIMEOUT_SECONDS = 120.0
MAX_STATE_CHARS = 24000
MAX_AI_SUMMARY_CHARS = 1600

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
    "ai_agent_configured": bool(OPENAI_API_KEY and AI_MODEL),
    "ai_model": AI_MODEL or None,
    "ai_interval_seconds": AI_INTERVAL_SECONDS,
    "ai_cycle_count": 0,
    "last_ai_cycle_at": None,
    "last_ai_status": None,
    "last_ai_priority": None,
    "last_ai_summary": None,
    "last_ai_next_action": None,
    "last_ai_error_type": None,
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


def _response_text(payload: dict) -> str:
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    parts = []
    for item in payload.get("output", []):
        if item.get("type") != "message":
            continue
        for block in item.get("content", []):
            text = block.get("text")
            if isinstance(text, str):
                parts.append(text)
    return "\n".join(parts)


def parse_ai_assessment(text: str) -> dict:
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()
        lines = lines[1:] if lines else lines
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    payload = json.loads(stripped)
    if not isinstance(payload, dict):
        raise ValueError("AI assessment must be an object")
    status = str(payload.get("status", "")).upper()
    priority = str(payload.get("priority", "")).upper()
    if status not in {"HEALTHY", "INVESTIGATE", "DEGRADED"}:
        raise ValueError("invalid AI assessment status")
    if priority not in {"LOW", "MEDIUM", "HIGH"}:
        raise ValueError("invalid AI assessment priority")
    return {
        "status": status,
        "priority": priority,
        "summary": str(payload.get("summary", ""))[:MAX_AI_SUMMARY_CHARS],
        "next_action": str(payload.get("next_action", ""))[:MAX_AI_SUMMARY_CHARS],
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


async def run_ai_cycle(client: httpx.AsyncClient) -> dict:
    if not OPENAI_API_KEY or not AI_MODEL:
        return {"configured": False, "error_type": "MissingAIConfiguration"}

    production, state = await asyncio.gather(
        client.get(PRODUCTION_HEALTH_URL),
        client.get(STATE_URL),
    )
    production.raise_for_status()
    state.raise_for_status()
    state_text = state.text[-MAX_STATE_CHARS:]
    production_payload = production.json()

    prompt = f"""You are the always-on read-only AI research/operations observer for a crypto quantitative trading/signalling system.
You run continuously 24/7, but you have NO code-write, branch, promotion, signing, or trade authority.
Use the canonical AI_STATE and production health below to identify the single most important evidence-backed issue or next investigation.
Never invent evidence. Never weaken validation. Never treat AI judgment as permission for BUY/SELL.
If evidence is insufficient, say so. Insufficient evidence must remain WAIT / RESEARCH_ONLY.

PRODUCTION HEALTH:
{json.dumps(production_payload, separators=(',', ':'))[:8000]}

CANONICAL AI_STATE (tail, including current handoff):
{state_text}

Return JSON only:
{{"status":"HEALTHY|INVESTIGATE|DEGRADED","priority":"LOW|MEDIUM|HIGH","summary":"brief evidence-based assessment","next_action":"one bounded next action for the scheduled specialist/lead pipeline"}}
"""
    response = await client.post(
        "https://api.openai.com/v1/responses",
        headers={
            "Authorization": f"Bearer {OPENAI_API_KEY}",
            "Content-Type": "application/json",
        },
        json={
            "model": AI_MODEL,
            "input": prompt,
            "max_output_tokens": 500,
        },
        timeout=AI_TIMEOUT_SECONDS,
    )
    response.raise_for_status()
    assessment = parse_ai_assessment(_response_text(response.json()))
    return {"configured": True, "assessment": assessment}


def apply_ai_cycle(result: dict) -> None:
    with _lock:
        _status["last_ai_cycle_at"] = _now()
        if not result.get("configured"):
            _status["ai_agent_configured"] = False
            _status["last_ai_error_type"] = result.get("error_type") or "MissingAIConfiguration"
            return
        assessment = result["assessment"]
        _status["ai_agent_configured"] = True
        _status["ai_cycle_count"] += 1
        _status["last_ai_status"] = assessment["status"]
        _status["last_ai_priority"] = assessment["priority"]
        _status["last_ai_summary"] = assessment["summary"]
        _status["last_ai_next_action"] = assessment["next_action"]
        _status["last_ai_error_type"] = None


async def coordinator_loop() -> None:
    timeout = httpx.Timeout(REQUEST_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        while True:
            apply_check(await check_once(client))
            await asyncio.sleep(POLL_SECONDS)


async def continuous_ai_loop() -> None:
    timeout = httpx.Timeout(AI_TIMEOUT_SECONDS)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        while True:
            try:
                apply_ai_cycle(await run_ai_cycle(client))
            except (httpx.HTTPError, ValueError, TypeError, json.JSONDecodeError) as exc:
                with _lock:
                    _status["last_ai_cycle_at"] = _now()
                    _status["last_ai_error_type"] = type(exc).__name__
                log.warning("continuous AI cycle failed: %s", type(exc).__name__)
            await asyncio.sleep(AI_INTERVAL_SECONDS)


@asynccontextmanager
async def lifespan(_: FastAPI):
    with _lock:
        _status["started_at"] = _now()
    watchdog_task = asyncio.create_task(coordinator_loop())
    ai_task = asyncio.create_task(continuous_ai_loop())
    try:
        yield
    finally:
        for task in (watchdog_task, ai_task):
            task.cancel()
        for task in (watchdog_task, ai_task):
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
        "mode": "continuous_ai_observer",
        "trade_authority": False,
        "write_authority": False,
        "promotion_authority": False,
        **snapshot,
    }
