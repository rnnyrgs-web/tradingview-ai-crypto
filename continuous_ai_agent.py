"""Persistent read-only AI observer for the production service.

This agent runs inside the existing production Render process so it can reuse the
same configured OpenAI credentials without creating a second secret path. It
reviews operational evidence and the canonical handoff continuously, but has no
code-write, promotion, signing, market-scan, or trade authority.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime, timezone
from threading import Lock

import httpx
from openai import OpenAI

from config import OPENAI_API_KEY, OPENAI_MODEL
from operational_monitor import health_snapshot

STATE_URL = os.getenv(
    "AI_STATE_URL",
    "https://raw.githubusercontent.com/rnnyrgs-web/tradingview-ai-crypto/main/AI_STATE.md",
)
CONTINUOUS_AI_MODEL = os.getenv("CONTINUOUS_AI_MODEL", OPENAI_MODEL).strip()
CONTINUOUS_AI_INTERVAL_SECONDS = max(
    60, int(os.getenv("CONTINUOUS_AI_INTERVAL_SECONDS", "300"))
)
MAX_STATE_CHARS = 24000
MAX_TEXT_CHARS = 1600

log = logging.getLogger(__name__)
_lock = Lock()
_status = {
    "configured": bool(OPENAI_API_KEY and CONTINUOUS_AI_MODEL),
    "model": CONTINUOUS_AI_MODEL or None,
    "interval_seconds": CONTINUOUS_AI_INTERVAL_SECONDS,
    "cycle_count": 0,
    "last_cycle_at": None,
    "last_status": None,
    "last_priority": None,
    "last_summary": None,
    "last_next_action": None,
    "last_error_type": None,
    "trade_authority": False,
    "write_authority": False,
    "promotion_authority": False,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_json(text: str) -> dict:
    """Parse one JSON object while still failing closed on malformed output."""
    stripped = text.strip()
    if stripped.startswith("```"):
        lines = stripped.splitlines()[1:]
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        stripped = "\n".join(lines).strip()
    try:
        payload = json.loads(stripped)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", stripped, flags=re.S)
        if not match:
            raise
        payload = json.loads(match.group(0))
    if not isinstance(payload, dict):
        raise ValueError("assessment must be an object")
    return payload


def validate_assessment(payload: dict) -> dict:
    status = str(payload.get("status", "")).upper()
    priority = str(payload.get("priority", "")).upper()
    if status not in {"HEALTHY", "INVESTIGATE", "DEGRADED"}:
        raise ValueError("invalid assessment status")
    if priority not in {"LOW", "MEDIUM", "HIGH"}:
        raise ValueError("invalid assessment priority")
    return {
        "status": status,
        "priority": priority,
        "summary": str(payload.get("summary", ""))[:MAX_TEXT_CHARS],
        "next_action": str(payload.get("next_action", ""))[:MAX_TEXT_CHARS],
    }


def run_ai_cycle() -> dict:
    if not OPENAI_API_KEY or not CONTINUOUS_AI_MODEL:
        return {"configured": False, "error_type": "MissingAIConfiguration"}

    state = httpx.get(STATE_URL, timeout=15.0, follow_redirects=True)
    state.raise_for_status()
    state_text = state.text[-MAX_STATE_CHARS:]
    operations = health_snapshot()
    prompt = f"""You are the always-on read-only AI research/operations observer for a crypto quantitative trading/signalling system.
You run continuously 24/7. You have NO code-write, branch, promotion, signing, market-scan, portfolio, or trade authority.
Review the deterministic operations snapshot and canonical AI_STATE below. Identify the single most important evidence-backed issue or next investigation for the scheduled specialist/Lead pipeline.
Never invent results. Never weaken no-lookahead, robustness, calibration, security, risk, or live-promotion gates. AI judgment cannot authorize BUY/SELL. Insufficient evidence must remain WAIT / RESEARCH_ONLY.

OPERATIONS SNAPSHOT:
{json.dumps(operations, separators=(',', ':'))[:8000]}

CANONICAL AI_STATE:
{state_text}

Return JSON only:
{{"status":"HEALTHY|INVESTIGATE|DEGRADED","priority":"LOW|MEDIUM|HIGH","summary":"brief evidence-based assessment","next_action":"one bounded next action for the normal specialist/Lead pipeline"}}
"""
    client = OpenAI(api_key=OPENAI_API_KEY)
    response = client.responses.create(
        model=CONTINUOUS_AI_MODEL,
        input=prompt,
        max_output_tokens=500,
    )
    assessment = validate_assessment(_extract_json(response.output_text))
    return {"configured": True, "assessment": assessment}


def apply_result(result: dict) -> None:
    with _lock:
        _status["last_cycle_at"] = _now()
        if not result.get("configured"):
            _status["configured"] = False
            _status["last_error_type"] = result.get("error_type") or "MissingAIConfiguration"
            return
        assessment = result["assessment"]
        _status["configured"] = True
        _status["cycle_count"] += 1
        _status["last_status"] = assessment["status"]
        _status["last_priority"] = assessment["priority"]
        _status["last_summary"] = assessment["summary"]
        _status["last_next_action"] = assessment["next_action"]
        _status["last_error_type"] = None
    log.info(
        "continuous AI observer cycle completed: status=%s priority=%s",
        assessment["status"],
        assessment["priority"],
    )


def status_snapshot() -> dict:
    with _lock:
        return dict(_status)


async def continuous_ai_loop() -> None:
    while True:
        try:
            result = await asyncio.to_thread(run_ai_cycle)
            apply_result(result)
        except (httpx.HTTPError, ValueError, TypeError, json.JSONDecodeError) as exc:
            with _lock:
                _status["last_cycle_at"] = _now()
                _status["last_error_type"] = type(exc).__name__
            log.warning("continuous AI observer cycle failed: %s", type(exc).__name__)
        except Exception as exc:
            # OpenAI SDK exceptions are deliberately reduced to type only in status/logs.
            with _lock:
                _status["last_cycle_at"] = _now()
                _status["last_error_type"] = type(exc).__name__
            log.warning("continuous AI observer cycle failed: %s", type(exc).__name__)
        await asyncio.sleep(CONTINUOUS_AI_INTERVAL_SECONDS)
