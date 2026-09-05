import os
import json
from datetime import datetime, timezone
from typing import Any, Dict, List

import httpx
from fastapi import FastAPI, HTTPException
from openai import OpenAI

app = FastAPI(title="Crypto 15m AI Scanner")

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")
SCAN_SECRET = os.getenv("SCAN_SECRET", "")

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is required")

client = OpenAI(api_key=OPENAI_API_KEY)

SYMBOLS = ["BTC-USDT","ETH-USDT","SOL-USDT","XRP-USDT","DOGE-USDT","LINK-USDT"]
OKX_BASE = "https://www.okx.com"

SYSTEM_PROMPT = """
You are a conservative, profitability-first crypto trading decision-support engine.
Analyze ONLY the supplied market data. Never invent missing data.
Focus on the next few hours using 15m trend/structure, 1h context, EMA9/EMA20,
momentum, range expansion/contraction, volume, local highs/lows, and entry quality.
Return concise JSON with market_regime, best_long, best_short, action, and summary.
Do not force a trade. Use WAIT or NO TRADE when entry quality is poor.
Evidence score is not a calibrated probability.
"""

def ema(values: List[float], period: int) -> float:
    if len(values) < period:
        return values[-1]
    k = 2 / (period + 1)
    result = sum(values[:period]) / period
    for value in values[period:]:
        result = value * k + result * (1 - k)
    return result

def pct(a: float, b: float) -> float:
    return 0.0 if a == 0 else (b / a - 1.0) * 100.0

async def okx_candles(http: httpx.AsyncClient, symbol: str, bar: str, limit: int = 100):
    r = await http.get(
        f"{OKX_BASE}/api/v5/market/candles",
        params={"instId": symbol, "bar": bar, "limit": str(limit)},
        timeout=15,
    )
    r.raise_for_status()
    body = r.json()
    if body.get("code") != "0" or not body.get("data"):
        raise RuntimeError(f"OKX candle error for {symbol}: {body}")
    return list(reversed(body["data"]))

def summarize(rows: List[List[str]]) -> Dict[str, Any]:
    closes = [float(r[4]) for r in rows]
    highs = [float(r[2]) for r in rows]
    lows = [float(r[3]) for r in rows]
    vols = [float(r[5]) for r in rows]
    last = closes[-1]
    hi = max(highs[-20:])
    lo = min(lows[-20:])
    avgvol = sum(vols[-20:]) / min(20, len(vols))
    return {
        "last": last,
        "ema9": ema(closes, 9),
        "ema20": ema(closes, 20),
        "change_1bar_pct": pct(closes[-2], closes[-1]) if len(closes) >= 2 else 0,
        "change_4bar_pct": pct(closes[-5], closes[-1]) if len(closes) >= 5 else 0,
        "change_12bar_pct": pct(closes[-13], closes[-1]) if len(closes) >= 13 else 0,
        "recent20_high": hi,
        "recent20_low": lo,
        "position_in_20bar_range_pct": 100*(last-lo)/(hi-lo) if hi > lo else 50,
        "last_volume": vols[-1],
        "avg20_volume": avgvol,
        "volume_ratio_vs_avg20": vols[-1]/avgvol if avgvol else 0,
    }

async def build_snapshot() -> Dict[str, Any]:
    snap = {"timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "source": "OKX public market API", "assets": {}}
    async with httpx.AsyncClient(headers={"User-Agent":"crypto-ai-scanner/1.0"}) as http:
        for symbol in SYMBOLS:
            try:
                snap["assets"][symbol] = {
                    "15m": summarize(await okx_candles(http, symbol, "15m")),
                    "1h": summarize(await okx_candles(http, symbol, "1H")),
                }
            except Exception as exc:
                snap["assets"][symbol] = {"error": str(exc)}
    return snap

def analyze_snapshot(snapshot: Dict[str, Any]) -> str:
    response = client.responses.create(
        model=OPENAI_MODEL,
        instructions=SYSTEM_PROMPT,
        input=json.dumps(snapshot, separators=(",", ":")),
    )
    return response.output_text.strip()

@app.get("/")
async def root():
    return {"ok": True, "service": "crypto-15m-ai-scanner", "endpoints": ["/health", "/scan"]}

@app.get("/health")
async def health():
    return {"ok": True}

@app.get("/scan")
async def scan(secret: str = ""):
    if SCAN_SECRET and secret != SCAN_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")
    snapshot = await build_snapshot()
    analysis = analyze_snapshot(snapshot)
    print("\n===== AI DECISION =====")
    print(analysis)
    print("=======================\n")
    return {"ok": True, "timestamp_utc": snapshot["timestamp_utc"], "analysis": analysis}
