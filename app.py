import os
import json
import hmac
import hashlib
import asyncio
from datetime import datetime, timezone
from typing import Any, Dict

import httpx
from fastapi import FastAPI, Request, HTTPException, BackgroundTasks
from fastapi.responses import JSONResponse
from openai import OpenAI

app = FastAPI(title="TradingView → OpenAI Crypto Advisor")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")
TELEGRAM_BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.getenv("TELEGRAM_CHAT_ID", "")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is required")

client = OpenAI(api_key=OPENAI_API_KEY)

SYSTEM_PROMPT = """
You are a profitability-first crypto trading decision-support engine.

PRIMARY OBJECTIVE:
Maximize long-run simulated/decision-support net P&L after realistic fees/slippage,
while preserving capital and controlling drawdowns. Prediction accuracy is secondary.
Never promise profit and never force a trade. CASH / NO TRADE is valid.

For this single TradingView event:
1. Inspect market structure from the supplied 15m data and indicators.
2. Treat 5m/15m/1h context conservatively; if only 15m is available, explicitly say so.
3. Separate THESIS, TIMING, RISK, and INVALIDATION.
4. Prefer conditional entries over chasing.
5. Output exactly one of: LONG, SHORT, WAIT, NO TRADE.
6. Only use LONG when the setup appears meaningfully positive-EV after costs.
7. If LONG/SHORT, give:
   - entry trigger/zone
   - stop/invalidation
   - target 1 / target 2
   - approximate R:R
   - time stop
   - evidence score 0-100
   - entry quality 0-100
   - key supporting factors
   - strongest opposing thesis
8. If the move is already extended, say MISSED / DO NOT CHASE.
9. Do not fabricate order-book, funding, OI, liquidation, news, on-chain, or cross-exchange
   data that is not supplied.
10. Keep the response concise and actionable.

Important: Evidence scores are not calibrated probabilities.
"""

def verify_secret(request: Request) -> None:
    if not WEBHOOK_SECRET:
        return
    supplied = request.headers.get("x-webhook-secret", "")
    if not hmac.compare_digest(supplied, WEBHOOK_SECRET):
        raise HTTPException(status_code=401, detail="Invalid webhook secret")

async def send_telegram(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    async with httpx.AsyncClient(timeout=10) as http:
        await http.post(
            url,
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "disable_web_page_preview": True,
            },
        )

def should_alert(text: str) -> bool:
    upper = text.upper()
    # Alert on actual actionable trade calls. You can change this to LONG-only.
    return (
        "LONG" in upper
        and "NO TRADE" not in upper
        and "WAIT" not in upper
        and "MISSED / DO NOT CHASE" not in upper
    )

async def analyze_event(payload: Dict[str, Any]):
    event = {
        "received_at_utc": datetime.now(timezone.utc).isoformat(),
        "tradingview": payload,
    }

    user_input = (
        "Analyze this TradingView 15-minute event.\n"
        "Only use supplied facts. Decide LONG / SHORT / WAIT / NO TRADE.\n\n"
        + json.dumps(event, indent=2)
    )

    try:
        response = await asyncio.to_thread(
            client.responses.create,
            model=OPENAI_MODEL,
            instructions=SYSTEM_PROMPT,
            input=user_input,
        )
        text = response.output_text.strip()

        print("\n===== AI DECISION =====")
        print(text)
        print("=======================\n")

        if should_alert(text):
            symbol = payload.get("symbol", "CRYPTO")
            await send_telegram(f"🚨 LONG ENTRY WATCH — {symbol}\n\n{text}")

    except Exception as exc:
        print(f"Analysis failed: {exc}")

@app.get("/health")
async def health():
    return {"ok": True}

@app.post("/webhook/tradingview")
async def tradingview_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
):
    verify_secret(request)

    try:
        payload = await request.json()
    except Exception:
        raw = (await request.body()).decode("utf-8", errors="replace")
        payload = {"raw_message": raw}

    # Acknowledge immediately so TradingView is not waiting on the OpenAI call.
    background_tasks.add_task(analyze_event, payload)
    return JSONResponse({"accepted": True}, status_code=202)
