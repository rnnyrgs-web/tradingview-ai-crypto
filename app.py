import os
import json
from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx
from fastapi import FastAPI, HTTPException
from openai import OpenAI


app = FastAPI(title="Crypto 15m AI Scanner")


# =========================================================
# ENVIRONMENT VARIABLES
# =========================================================

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")
SCAN_SECRET = os.getenv("SCAN_SECRET", "")

SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY", "")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is required")

client = OpenAI(api_key=OPENAI_API_KEY)


# =========================================================
# MARKET CONFIGURATION
# =========================================================

SYMBOLS = [
    x.strip()
    for x in os.getenv(
        "SYMBOLS",
        "BTC-USDT,ETH-USDT,SOL-USDT,XRP-USDT,DOGE-USDT,ADA-USDT,"
        "LINK-USDT,AVAX-USDT,AAVE-USDT,UNI-USDT",
    ).split(",")
    if x.strip()
]

OKX_BASE = "https://www.okx.com"


SYSTEM_PROMPT = """
You are a conservative, profitability-first crypto trading decision-support engine.

Analyze ONLY the supplied market data. Never invent missing information.

Your job is to identify the best LONG candidate, best SHORT candidate,
or determine that there is NO TRADE.

Focus on:
- 15 minute trend and structure
- 1 hour context
- 4 hour context
- EMA9 / EMA20
- momentum
- breakout / breakdown quality
- volume expansion
- relative strength
- local highs and lows
- entry quality
- risk/reward

Do not force trades.

Return ONLY valid JSON in exactly this general structure:

{
  "market_regime": "text",
  "action": "LONG | SHORT | WAIT | NO TRADE",
  "best_long": {
    "symbol": "SOL-USDT",
    "setup": "text",
    "entry_price": 100.0,
    "stop_loss": 98.0,
    "target_1": 103.0,
    "target_2": 106.0,
    "risk_reward": 2.5,
    "evidence_score": 80,
    "trigger": "text",
    "invalidation": "text"
  },
  "best_short": {
    "symbol": "XRP-USDT",
    "setup": "text",
    "entry_price": 1.40,
    "stop_loss": 1.43,
    "target_1": 1.36,
    "target_2": 1.32,
    "risk_reward": 2.2,
    "evidence_score": 78,
    "trigger": "text",
    "invalidation": "text"
  },
  "summary": "text"
}

If exact numerical entry, stop, or target values cannot reasonably be
determined from the supplied data, use null.

Evidence score is a setup-quality score from 0-100.
It is NOT a calibrated probability of winning.
"""


# =========================================================
# INDICATORS
# =========================================================

def ema(values: List[float], period: int) -> float:
    if not values:
        return 0.0

    multiplier = 2 / (period + 1)
    result = values[0]

    for value in values[1:]:
        result = (value * multiplier) + (result * (1 - multiplier))

    return result


def rsi(values: List[float], period: int = 14) -> float:
    if len(values) < period + 1:
        return 50.0

    gains = []
    losses = []

    for i in range(1, len(values)):
        change = values[i] - values[i - 1]

        if change >= 0:
            gains.append(change)
            losses.append(0.0)
        else:
            gains.append(0.0)
            losses.append(abs(change))

    avg_gain = sum(gains[-period:]) / period
    avg_loss = sum(losses[-period:]) / period

    if avg_loss == 0:
        return 100.0

    rs = avg_gain / avg_loss
    return 100 - (100 / (1 + rs))


# =========================================================
# OKX DATA
# =========================================================

def fetch_candles(symbol: str) -> List[List[Any]]:
    url = f"{OKX_BASE}/api/v5/market/candles"

    params = {
        "instId": symbol,
        "bar": "15m",
        "limit": "100",
    }

    with httpx.Client(timeout=20) as http:
        response = http.get(url, params=params)
        response.raise_for_status()

        payload = response.json()

    if payload.get("code") != "0":
        raise RuntimeError(f"OKX error for {symbol}: {payload}")

    rows = payload.get("data", [])

    # OKX returns newest first.
    rows.reverse()

    return rows


def build_symbol_snapshot(symbol: str) -> Dict[str, Any]:
    candles = fetch_candles(symbol)

    if len(candles) < 30:
        raise RuntimeError(f"Not enough candles for {symbol}")

    closes = [float(row[4]) for row in candles]
    highs = [float(row[2]) for row in candles]
    lows = [float(row[3]) for row in candles]
    volumes = [float(row[5]) for row in candles]

    latest = closes[-1]

    ema9_value = ema(closes[-50:], 9)
    ema20_value = ema(closes[-50:], 20)
    rsi14_value = rsi(closes, 14)

    high_20 = max(highs[-20:])
    low_20 = min(lows[-20:])

    avg_volume_20 = sum(volumes[-20:]) / 20
    volume_ratio = (
        volumes[-1] / avg_volume_20
        if avg_volume_20 > 0
        else 0
    )

    return_15m = (
        ((closes[-1] / closes[-2]) - 1) * 100
        if closes[-2]
        else 0
    )

    return_1h = (
        ((closes[-1] / closes[-5]) - 1) * 100
        if len(closes) >= 5
        else 0
    )

    return_4h = (
        ((closes[-1] / closes[-17]) - 1) * 100
        if len(closes) >= 17
        else 0
    )

    range_size = high_20 - low_20

    range_position = (
        (latest - low_20) / range_size
        if range_size > 0
        else 0.5
    )

    return {
        "symbol": symbol,
        "price": round(latest, 8),
        "ema9": round(ema9_value, 8),
        "ema20": round(ema20_value, 8),
        "rsi14": round(rsi14_value, 2),
        "high_20": round(high_20, 8),
        "low_20": round(low_20, 8),
        "volume_ratio_vs_avg20": round(volume_ratio, 2),
        "return_15m_pct": round(return_15m, 3),
        "return_1h_pct": round(return_1h, 3),
        "return_4h_pct": round(return_4h, 3),
        "range_position_20": round(range_position, 3),
    }


def build_market_snapshot() -> Dict[str, Any]:
    data = []

    for symbol in SYMBOLS:
        try:
            data.append(build_symbol_snapshot(symbol))
        except Exception as exc:
            data.append(
                {
                    "symbol": symbol,
                    "error": str(exc),
                }
            )

    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "timeframe": "15m",
        "symbols": data,
    }


# =========================================================
# OPENAI ANALYSIS
# =========================================================

def extract_json(text: str) -> Dict[str, Any]:
    clean = text.strip()

    if clean.startswith("```"):
        clean = clean.replace("```json", "", 1)
        clean = clean.replace("```", "")

    return json.loads(clean.strip())


def analyze_snapshot(snapshot: Dict[str, Any]) -> Dict[str, Any]:
    response = client.responses.create(
        model=OPENAI_MODEL,
        instructions=SYSTEM_PROMPT,
        input=json.dumps(snapshot, separators=(",", ":")),
    )

    text = response.output_text

    return extract_json(text)


# =========================================================
# SUPABASE PREDICTION LEDGER
# =========================================================

def safe_number(value: Any):
    try:
        if value is None or value == "":
            return None

        return float(value)

    except (TypeError, ValueError):
        return None


def save_signal(
    candidate: Dict[str, Any],
    direction: str,
    analysis: Dict[str, Any],
) -> bool:

    if not SUPABASE_URL or not SUPABASE_SECRET_KEY:
        print("Supabase credentials are missing")
        return False

    if not isinstance(candidate, dict):
        return False

    symbol = candidate.get("symbol")

    if not symbol:
        return False

    reasoning_parts = [
        candidate.get("setup"),
        candidate.get("trigger"),
        candidate.get("invalidation"),
        analysis.get("summary"),
    ]

    reasoning = " | ".join(
        str(x)
        for x in reasoning_parts
        if x
    )

    row = {
        "symbol": symbol,
        "timeframe": "15m",
        "direction": direction,
        "action": analysis.get("action"),
        "entry_price": safe_number(candidate.get("entry_price")),
        "stop_loss": safe_number(candidate.get("stop_loss")),
        "target_1": safe_number(candidate.get("target_1")),
        "target_2": safe_number(candidate.get("target_2")),
        "risk_reward": safe_number(candidate.get("risk_reward")),
        "evidence_score": safe_number(candidate.get("evidence_score")),
        "market_regime": analysis.get("market_regime"),
        "reasoning": reasoning,
        "status": "OPEN",
        "raw_analysis": analysis,
    }

    url = f"{SUPABASE_URL}/rest/v1/trading_signals"

    headers = {
        "apikey": SUPABASE_SECRET_KEY,
        "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
        "Content-Type": "application/json",
        "Prefer": "return=minimal",
    }

    with httpx.Client(timeout=20) as http:
        response = http.post(
            url,
            headers=headers,
            json=row,
        )

    if response.status_code not in (200, 201, 204):
        print(
            "Supabase insert failed:",
            response.status_code,
            response.text,
        )
        return False

    return True


def save_analysis(analysis: Dict[str, Any]) -> Dict[str, bool]:
    long_saved = save_signal(
        analysis.get("best_long", {}),
        "LONG",
        analysis,
    )

    short_saved = save_signal(
        analysis.get("best_short", {}),
        "SHORT",
        analysis,
    )

    return {
        "long_saved": long_saved,
        "short_saved": short_saved,
    }


# =========================================================
# SCANNER
# =========================================================

def run_scan() -> Dict[str, Any]:
    snapshot = build_market_snapshot()
    analysis = analyze_snapshot(snapshot)

    database = save_analysis(analysis)

    return {
        "ok": True,
        "timestamp_utc": snapshot["timestamp_utc"],
        "symbols_scanned": len(SYMBOLS),
        "analysis": analysis,
        "database": database,
    }


# =========================================================
# API ROUTES
# =========================================================

@app.get("/")
def root():
    return {
        "ok": True,
        "service": "crypto-15m-ai-scanner",
        "endpoints": [
            "/health",
            "/scan",
        ],
    }


@app.get("/health")
def health():
    return {
        "ok": True,
        "supabase_configured": bool(
            SUPABASE_URL and SUPABASE_SECRET_KEY
        ),
    }


@app.get("/scan")
def scan(secret: str = ""):
    if SCAN_SECRET and secret != SCAN_SECRET:
        raise HTTPException(
            status_code=401,
            detail="Invalid scan secret",
        )

    return run_scan()
