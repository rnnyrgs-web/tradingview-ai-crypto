import os
import re
import json
import math
import uuid
import time
import statistics
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import httpx
from fastapi import FastAPI, HTTPException, Header
from openai import OpenAI

app = FastAPI(title="Crypto Signal Engine V2")

# ============================================================
# ENVIRONMENT
# ============================================================
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-5")
SCAN_SECRET = os.getenv("SCAN_SECRET", "")
SUPABASE_URL = os.getenv("SUPABASE_URL", "").rstrip("/")
SUPABASE_SECRET_KEY = os.getenv("SUPABASE_SECRET_KEY", "")

OKX_BASE = "https://www.okx.com"
STRATEGY_VERSION = "v2.0"

UNIVERSE_SIZE = int(os.getenv("UNIVERSE_SIZE", "180"))
DEEP_SCAN_SIZE = int(os.getenv("DEEP_SCAN_SIZE", "36"))
AI_CANDIDATES = int(os.getenv("AI_CANDIDATES", "10"))
MAX_SAVED_SIGNALS = int(os.getenv("MAX_SAVED_SIGNALS", "3"))

MIN_QUOTE_VOLUME = float(os.getenv("MIN_QUOTE_VOLUME", "1000000"))
MIN_EVIDENCE_SCORE = float(os.getenv("MIN_EVIDENCE_SCORE", "72"))
MIN_RR = float(os.getenv("MIN_RR", "1.8"))
BACKTEST_COST_BPS = float(os.getenv("BACKTEST_COST_BPS", "12"))

if not OPENAI_API_KEY:
    raise RuntimeError("OPENAI_API_KEY is required")

client = OpenAI(api_key=OPENAI_API_KEY)
http = httpx.Client(timeout=25.0, follow_redirects=True)

STABLE_BASES = {
    "USDC", "USDT", "DAI", "FDUSD", "TUSD", "USDE", "PYUSD",
    "EUR", "EURT", "USD", "USDK", "BUSD"
}

# ============================================================
# HELPERS
# ============================================================
def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat()


def f(x: Any, default: float = 0.0) -> float:
    try:
        return float(x)
    except Exception:
        return default


def clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def pct_change(a: float, b: float) -> float:
    return 0.0 if not a else (b / a - 1.0) * 100.0


def mean(xs: List[float]) -> float:
    return sum(xs) / len(xs) if xs else 0.0


def safe_stdev(xs: List[float]) -> float:
    if len(xs) < 2:
        return 0.0
    try:
        return statistics.stdev(xs)
    except Exception:
        return 0.0


def ema(values: List[float], period: int) -> float:
    if not values:
        return 0.0
    alpha = 2.0 / (period + 1.0)
    e = values[0]
    for v in values[1:]:
        e = alpha * v + (1 - alpha) * e
    return e


def rsi(values: List[float], period: int = 14) -> float:
    if len(values) <= period:
        return 50.0
    gains, losses = [], []
    for i in range(len(values) - period, len(values)):
        d = values[i] - values[i - 1]
        gains.append(max(d, 0.0))
        losses.append(max(-d, 0.0))
    ag, al = mean(gains), mean(losses)
    if al == 0:
        return 100.0
    rs = ag / al
    return 100.0 - (100.0 / (1.0 + rs))


def atr(candles: List[Dict[str, float]], period: int = 14) -> float:
    if len(candles) < 2:
        return 0.0
    trs = []
    start = max(1, len(candles) - period)
    for i in range(start, len(candles)):
        h = candles[i]["high"]
        l = candles[i]["low"]
        pc = candles[i - 1]["close"]
        trs.append(max(h - l, abs(h - pc), abs(l - pc)))
    return mean(trs)


def zscore_last(values: List[float], window: int = 30) -> float:
    vals = values[-window:]
    if len(vals) < 5:
        return 0.0
    sd = safe_stdev(vals)
    return 0.0 if sd == 0 else (vals[-1] - mean(vals)) / sd


def linear_slope_pct(values: List[float], n: int = 12) -> float:
    vals = values[-n:]
    if len(vals) < 3 or mean(vals) == 0:
        return 0.0
    xbar = (len(vals) - 1) / 2
    ybar = mean(vals)
    num = sum((i - xbar) * (v - ybar) for i, v in enumerate(vals))
    den = sum((i - xbar) ** 2 for i in range(len(vals))) or 1.0
    return (num / den) / ybar * 100.0


def parse_dt(s: str) -> datetime:
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)

# ============================================================
# OKX MARKET DATA
# ============================================================
def okx_get(path: str, params: Optional[Dict[str, Any]] = None) -> Any:
    r = http.get(f"{OKX_BASE}{path}", params=params or {})
    r.raise_for_status()
    obj = r.json()
    if str(obj.get("code", "0")) != "0":
        raise RuntimeError(f"OKX error {obj.get('code')}: {obj.get('msg')}")
    return obj.get("data", [])


def get_spot_tickers() -> List[Dict[str, Any]]:
    return okx_get("/api/v5/market/tickers", {"instType": "SPOT"})


def normalize_candles(rows: List[List[str]]) -> List[Dict[str, float]]:
    out = []
    for row in reversed(rows):
        if len(row) < 6:
            continue
        confirm = str(row[8]) if len(row) > 8 else "1"
        if confirm == "0":
            continue
        out.append({
            "ts": int(row[0]),
            "open": f(row[1]),
            "high": f(row[2]),
            "low": f(row[3]),
            "close": f(row[4]),
            "volume": f(row[5]),
            "quote_volume": f(row[7]) if len(row) > 7 else 0.0,
        })
    return out


def get_candles(symbol: str, bar: str = "15m", limit: int = 120) -> List[Dict[str, float]]:
    rows = okx_get(
        "/api/v5/market/candles",
        {"instId": symbol, "bar": bar, "limit": str(min(limit, 300))}
    )
    return normalize_candles(rows)


def get_history(symbol: str, bar: str = "15m", bars: int = 1000) -> List[Dict[str, float]]:
    wanted = max(100, min(bars, 5000))
    collected: List[List[str]] = []
    after = None

    while len(collected) < wanted:
        params = {
            "instId": symbol,
            "bar": bar,
            "limit": str(min(100, wanted - len(collected))),
        }
        if after:
            params["after"] = after

        rows = okx_get("/api/v5/market/history-candles", params)
        if not rows:
            break

        collected.extend(rows)
        after = str(min(int(r[0]) for r in rows))
        if len(rows) < int(params["limit"]):
            break
        time.sleep(0.05)

    by_ts = {int(r[0]): r for r in collected}
    rows = [by_ts[k] for k in sorted(by_ts.keys(), reverse=True)][:wanted]
    return normalize_candles(rows)


def get_derivatives(base: str) -> Dict[str, Any]:
    inst = f"{base}-USDT-SWAP"
    out = {"swap_available": False, "funding_rate": None, "open_interest": None}

    try:
        fr = okx_get("/api/v5/public/funding-rate", {"instId": inst})
        if fr:
            out["funding_rate"] = f(fr[0].get("fundingRate"), None)
            out["swap_available"] = True
    except Exception:
        pass

    try:
        oi = okx_get("/api/v5/public/open-interest", {"instType": "SWAP", "instId": inst})
        if oi:
            out["open_interest"] = f(oi[0].get("oiCcy") or oi[0].get("oi"), None)
            out["swap_available"] = True
    except Exception:
        pass

    return out

# ============================================================
# NEWS
# ============================================================
NEWS_FEEDS = [
    "https://www.coindesk.com/arc/outboundfeeds/rss/",
    "https://cointelegraph.com/rss",
]


def get_latest_news(limit: int = 30) -> List[Dict[str, str]]:
    items: List[Dict[str, str]] = []
    for url in NEWS_FEEDS:
        try:
            r = http.get(url, timeout=12.0)
            if r.status_code != 200:
                continue
            root = ET.fromstring(r.content)
            for item in root.findall(".//item"):
                title = (item.findtext("title") or "").strip()
                link = (item.findtext("link") or "").strip()
                pub = (item.findtext("pubDate") or "").strip()
                if title:
                    items.append({"title": title, "url": link, "published": pub})
        except Exception:
            continue

    seen, unique = set(), []
    for x in items:
        key = x["title"].lower()
        if key not in seen:
            seen.add(key)
            unique.append(x)
    return unique[:limit]


def news_for_base(base: str, news: List[Dict[str, str]]) -> List[Dict[str, str]]:
    pattern = re.compile(rf"\b{re.escape(base.upper())}\b", re.I)
    return [n for n in news if pattern.search(n["title"])]

# ============================================================
# FEATURE ENGINE
# ============================================================
def timeframe_features(candles: List[Dict[str, float]]) -> Dict[str, float]:
    if len(candles) < 35:
        return {}

    closes = [c["close"] for c in candles]
    vols = [c["volume"] for c in candles]
    last = closes[-1]

    e9 = ema(closes[-60:], 9)
    e20 = ema(closes[-80:], 20)
    e50 = ema(closes[-100:], 50)
    rrsi = rsi(closes)
    a = atr(candles)
    atr_pct = (a / last * 100.0) if last else 0.0
    vol_z = zscore_last(vols)
    slope = linear_slope_pct(closes, 12)

    high_20 = max(c["high"] for c in candles[-20:])
    low_20 = min(c["low"] for c in candles[-20:])
    range_pos = 0.5 if high_20 == low_20 else (last - low_20) / (high_20 - low_20)
    ret_4 = pct_change(closes[-5], closes[-1]) if len(closes) >= 5 else 0.0

    score = 0.0
    score += 1.1 if e9 > e20 else -1.1
    score += 0.8 if e20 > e50 else -0.8
    score += clamp(slope * 4.0, -1.5, 1.5)
    score += clamp(ret_4 / max(atr_pct, 0.2), -1.2, 1.2) * 0.6

    if rrsi >= 55:
        score += min((rrsi - 55) / 20, 0.8)
    elif rrsi <= 45:
        score -= min((45 - rrsi) / 20, 0.8)

    if range_pos > 0.8 and vol_z > 0.5:
        score += 0.5
    if range_pos < 0.2 and vol_z > 0.5:
        score -= 0.5

    return {
        "last": last,
        "ema9": e9,
        "ema20": e20,
        "ema50": e50,
        "rsi": rrsi,
        "atr": a,
        "atr_pct": atr_pct,
        "volume_z": vol_z,
        "slope_pct_per_bar": slope,
        "range_position": range_pos,
        "ret_4": ret_4,
        "score": score,
    }


def build_universe() -> List[Dict[str, Any]]:
    rows = []
    for t in get_spot_tickers():
        inst = str(t.get("instId", ""))
        if not inst.endswith("-USDT"):
            continue

        base = inst.split("-")[0]
        if base in STABLE_BASES:
            continue

        last = f(t.get("last"))
        open24 = f(t.get("open24h"))
        bid = f(t.get("bidPx"))
        ask = f(t.get("askPx"))
        quote_vol = f(t.get("volCcy24h"))

        if quote_vol <= 0:
            quote_vol = f(t.get("vol24h")) * max(last, 0)

        if last <= 0 or quote_vol < MIN_QUOTE_VOLUME:
            continue

        change24 = pct_change(open24, last) if open24 > 0 else 0.0
        spread_bps = ((ask - bid) / last * 10000.0) if bid > 0 and ask > 0 else 999

        activity = (
            math.log10(max(quote_vol, 1.0)) * 0.65
            + abs(change24) * 0.25
            - min(spread_bps, 50) * 0.03
        )

        rows.append({
            "symbol": inst,
            "base": base,
            "last": last,
            "quote_volume_24h": quote_vol,
            "change_24h_pct": change24,
            "spread_bps": spread_bps,
            "activity_score": activity,
        })

    rows.sort(key=lambda x: x["activity_score"], reverse=True)
    return rows[:UNIVERSE_SIZE]


def deep_quant_scan(universe: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    results = []

    for item in universe[:DEEP_SCAN_SIZE]:
        try:
            c15 = get_candles(item["symbol"], "15m", 140)
            c1h = get_candles(item["symbol"], "1H", 110)
            f15 = timeframe_features(c15)
            f1h = timeframe_features(c1h)
            if not f15 or not f1h:
                continue

            score = f15["score"] * 0.58 + f1h["score"] * 0.42
            score += clamp(item["change_24h_pct"] / 12.0, -0.55, 0.55)

            if f15["score"] > 0 and f1h["score"] > 0:
                score += 0.45
            elif f15["score"] < 0 and f1h["score"] < 0:
                score -= 0.45

            results.append({**item, "quant_score": score, "f15": f15, "f1h": f1h})
            time.sleep(0.03)
        except Exception:
            pass

    results.sort(key=lambda x: abs(x["quant_score"]), reverse=True)
    finalists = results[:AI_CANDIDATES]

    for r in finalists:
        try:
            r["f4h"] = timeframe_features(get_candles(r["symbol"], "4H", 90))
        except Exception:
            r["f4h"] = {}

        r["derivatives"] = get_derivatives(r["base"])

        if r["f4h"]:
            s4 = r["f4h"]["score"]
            if r["quant_score"] > 0 and s4 > 0:
                r["quant_score"] += 0.35
            elif r["quant_score"] < 0 and s4 < 0:
                r["quant_score"] -= 0.35

    finalists.sort(key=lambda x: abs(x["quant_score"]), reverse=True)
    return finalists

# ============================================================
# MARKET REGIME
# ============================================================
def detect_market_regime(candidates: List[Dict[str, Any]]) -> str:
    if not candidates:
        return "UNKNOWN"

    scores = [c["quant_score"] for c in candidates]
    avg = mean(scores)
    positive = sum(1 for s in scores if s > 0) / len(scores)
    btc = next((c for c in candidates if c["base"] == "BTC"), None)
    btc_score = btc["quant_score"] if btc else 0

    if avg > 1.0 and positive > 0.68 and btc_score >= 0:
        return "BULL_TREND"
    if avg < -1.0 and positive < 0.32 and btc_score <= 0:
        return "BEAR_TREND"
    if safe_stdev(scores) > 2.4:
        return "HIGH_DISPERSION_ROTATION"
    if abs(avg) < 0.45:
        return "RANGE_MIXED"
    return "TRANSITIONAL"

# ============================================================
# AI REVIEW
# ============================================================
def compact_candidate(c: Dict[str, Any], news: List[Dict[str, str]]) -> Dict[str, Any]:
    d = c.get("derivatives", {})
    return {
        "symbol": c["symbol"],
        "last": round(c["last"], 10),
        "quote_volume_24h": round(c["quote_volume_24h"], 2),
        "change_24h_pct": round(c["change_24h_pct"], 3),
        "spread_bps": round(c["spread_bps"], 3),
        "quant_score": round(c["quant_score"], 3),
        "15m": {k: round(v, 5) for k, v in c["f15"].items() if isinstance(v, (int, float))},
        "1h": {k: round(v, 5) for k, v in c["f1h"].items() if isinstance(v, (int, float))},
        "4h": {k: round(v, 5) for k, v in c.get("f4h", {}).items() if isinstance(v, (int, float))},
        "funding_rate": d.get("funding_rate"),
        "open_interest": d.get("open_interest"),
        "matching_news": [n["title"] for n in news_for_base(c["base"], news)[:4]],
    }


def extract_json(text: str) -> Dict[str, Any]:
    text = text.strip()
    text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except Exception:
        m = re.search(r"\{.*\}", text, flags=re.S)
        if not m:
            raise
        return json.loads(m.group(0))


def ai_review(candidates: List[Dict[str, Any]], regime: str, news: List[Dict[str, str]]) -> Dict[str, Any]:
    payload = [compact_candidate(c, news) for c in candidates]
    headlines = [n["title"] for n in news[:15]]

    prompt = f"""
You are one component of a quantitative crypto trading research system.
Do not invent data. Evidence scores are NOT calibrated probabilities.

Market regime: {regime}
Candidates: {json.dumps(payload, separators=(",", ":"), ensure_ascii=False)}
Latest crypto headlines: {json.dumps(headlines, ensure_ascii=False)}

Adversarially review the candidates. Penalize contradictory timeframes, extreme/chased moves,
poor liquidity, weak derivatives confirmation and irrelevant news. Do not force a trade.
Rank at most 3 opportunities total.

Return ONLY JSON:
{{
  "market_regime": "{regime}",
  "summary": "short",
  "signals": [
    {{
      "symbol": "BTC-USDT",
      "direction": "LONG",
      "action": "TRADE or WAIT",
      "evidence_score": 0,
      "reasoning": "short evidence-based reason",
      "invalidation": "short"
    }}
  ]
}}
"""

    response = client.responses.create(model=OPENAI_MODEL, input=prompt)
    return extract_json(response.output_text)

# ============================================================
# RISK ENGINE
# ============================================================
def risk_plan(candidate: Dict[str, Any], direction: str) -> Dict[str, float]:
    entry = candidate["f15"]["last"]
    a = candidate["f15"]["atr"]

    if entry <= 0 or a <= 0:
        return {"entry_price": entry, "stop_loss": 0, "target_1": 0, "target_2": 0, "risk_reward": 0}

    risk = max(a * 1.55, entry * 0.0035)

    if direction == "LONG":
        stop = entry - risk
        t1 = entry + risk * 1.9
        t2 = entry + risk * 3.0
    else:
        stop = entry + risk
        t1 = entry - risk * 1.9
        t2 = entry - risk * 3.0

    return {
        "entry_price": entry,
        "stop_loss": stop,
        "target_1": t1,
        "target_2": t2,
        "risk_reward": 1.9,
    }

# ============================================================
# SUPABASE
# ============================================================
def sb_headers(prefer: Optional[str] = None) -> Dict[str, str]:
    h = {
        "apikey": SUPABASE_SECRET_KEY,
        "Authorization": f"Bearer {SUPABASE_SECRET_KEY}",
        "Content-Type": "application/json",
    }
    if prefer:
        h["Prefer"] = prefer
    return h


def save_signal(row: Dict[str, Any]) -> None:
    if not (SUPABASE_URL and SUPABASE_SECRET_KEY):
        return
    r = http.post(
        f"{SUPABASE_URL}/rest/v1/trading_signals",
        headers=sb_headers("return=minimal"),
        json=row,
    )
    if r.status_code >= 300:
        raise RuntimeError(f"Supabase insert failed: {r.status_code} {r.text}")


def fetch_recent_signals(hours: int = 30, limit: int = 500) -> List[Dict[str, Any]]:
    cutoff = iso(now_utc() - timedelta(hours=hours))
    params = {
        "select": "*",
        "created_at": f"gte.{cutoff}",
        "order": "created_at.asc",
        "limit": str(limit),
    }
    r = http.get(
        f"{SUPABASE_URL}/rest/v1/trading_signals",
        headers=sb_headers(),
        params=params,
    )
    if r.status_code >= 300:
        raise RuntimeError(f"Supabase select failed: {r.status_code} {r.text}")
    return r.json()


def update_signal(signal_id: Any, fields: Dict[str, Any]) -> None:
    if not fields:
        return
    r = http.patch(
        f"{SUPABASE_URL}/rest/v1/trading_signals",
        headers=sb_headers("return=minimal"),
        params={"id": f"eq.{signal_id}"},
        json=fields,
    )
    if r.status_code >= 300:
        raise RuntimeError(f"Supabase update failed: {r.status_code} {r.text}")

# ============================================================
# SCAN
# ============================================================
def run_scan() -> Dict[str, Any]:
    started = now_utc()
    scan_id = str(uuid.uuid4())

    universe = build_universe()
    candidates = deep_quant_scan(universe)
    regime = detect_market_regime(candidates)
    news = get_latest_news()

    ai_error = None
    try:
        review = ai_review(candidates, regime, news)
        signals = review.get("signals") or []
    except Exception as e:
        ai_error = str(e)
        signals = []
        for c in candidates[:MAX_SAVED_SIGNALS]:
            strength = clamp(58 + abs(c["quant_score"]) * 5.2, 0, 88)
            signals.append({
                "symbol": c["symbol"],
                "direction": "LONG" if c["quant_score"] > 0 else "SHORT",
                "action": "TRADE" if strength >= MIN_EVIDENCE_SCORE else "WAIT",
                "evidence_score": round(strength, 1),
                "reasoning": "Quantitative fallback; AI review unavailable.",
                "invalidation": "Loss of multi-timeframe alignment.",
            })

    saved = []

    for s in signals[:MAX_SAVED_SIGNALS]:
        symbol = str(s.get("symbol", "")).upper()
        direction = str(s.get("direction", "")).upper()
        action = str(s.get("action", "WAIT")).upper()
        evidence = f(s.get("evidence_score"), 0)

        c = next((x for x in candidates if x["symbol"] == symbol), None)
        if not c or direction not in {"LONG", "SHORT"}:
            continue

        plan = risk_plan(c, direction)

        if evidence < MIN_EVIDENCE_SCORE or plan["risk_reward"] < MIN_RR:
            action = "WAIT"

        row = {
            "scan_id": scan_id,
            "symbol": symbol,
            "timeframe": "15m",
            "direction": direction,
            "action": action,
            "entry_price": plan["entry_price"],
            "stop_loss": plan["stop_loss"],
            "target_1": plan["target_1"],
            "target_2": plan["target_2"],
            "risk_reward": plan["risk_reward"],
            "evidence_score": evidence,
            "market_regime": regime,
            "reasoning": str(s.get("reasoning", ""))[:4000],
            "status": "OPEN",
            "model_name": OPENAI_MODEL,
            "strategy_version": STRATEGY_VERSION,
            "raw_analysis": {
                "scan_id": scan_id,
                "candidate": compact_candidate(c, news),
                "ai_signal": s,
            },
        }

        save_signal(row)
        saved.append(row)

    return {
        "ok": True,
        "version": STRATEGY_VERSION,
        "scan_id": scan_id,
        "started_at": iso(started),
        "finished_at": iso(now_utc()),
        "universe_count": len(universe),
        "deep_scanned": len(candidates),
        "market_regime": regime,
        "signals_saved": len(saved),
        "signals": saved,
        "ai_error": ai_error,
    }

# ============================================================
# OUTCOME EVALUATION
# ============================================================
def directional_return(entry: float, future: float, direction: str) -> float:
    if entry <= 0:
        return 0.0
    raw = (future / entry - 1.0) * 100.0
    return raw if direction == "LONG" else -raw


def nearest_close(candles: List[Dict[str, float]], target_ms: int) -> Optional[float]:
    for c in candles:
        if c["ts"] >= target_ms:
            return c["close"]
    return candles[-1]["close"] if candles else None


def evaluate_one_signal(sig: Dict[str, Any]) -> Dict[str, Any]:
    created = parse_dt(sig["created_at"])
    age = now_utc() - created
    entry = f(sig.get("entry_price"))
    direction = str(sig.get("direction", "")).upper()
    action = str(sig.get("action", "WAIT")).upper()

    if entry <= 0 or direction not in {"LONG", "SHORT"}:
        return {}

    c5 = get_candles(sig["symbol"], "5m", 300)
    if not c5:
        return {}

    fields: Dict[str, Any] = {"evaluated_at": iso(now_utc())}

    horizons = [
        (timedelta(minutes=15), "price_15m", "return_15m"),
        (timedelta(hours=1), "price_1h", "return_1h"),
        (timedelta(hours=4), "price_4h", "return_4h"),
        (timedelta(hours=12), "price_12h", "return_12h"),
        (timedelta(hours=24), "price_24h", "return_24h"),
    ]

    for delta, pcol, rcol in horizons:
        if age >= delta and sig.get(pcol) is None:
            p = nearest_close(c5, int((created + delta).timestamp() * 1000))
            if p is not None:
                fields[pcol] = p
                fields[rcol] = directional_return(entry, p, direction)

    path = [c for c in c5 if c["ts"] >= int(created.timestamp() * 1000)]

    if path:
        if direction == "LONG":
            fields["mfe_pct"] = (max(c["high"] for c in path) / entry - 1) * 100
            fields["mae_pct"] = (min(c["low"] for c in path) / entry - 1) * 100
        else:
            fields["mfe_pct"] = (1 - min(c["low"] for c in path) / entry) * 100
            fields["mae_pct"] = (1 - max(c["high"] for c in path) / entry) * 100

        t1 = f(sig.get("target_1"))
        t2 = f(sig.get("target_2"))
        stop = f(sig.get("stop_loss"))

        first_t1 = None
        first_t2 = None
        first_stop = None
        ambiguous = False

        for c in path:
            if direction == "LONG":
                hit_t1 = t1 > 0 and c["high"] >= t1
                hit_t2 = t2 > 0 and c["high"] >= t2
                hit_stop = stop > 0 and c["low"] <= stop
            else:
                hit_t1 = t1 > 0 and c["low"] <= t1
                hit_t2 = t2 > 0 and c["low"] <= t2
                hit_stop = stop > 0 and c["high"] >= stop

            ts_iso = datetime.fromtimestamp(c["ts"] / 1000, tz=timezone.utc).isoformat()
            if hit_t1 and first_t1 is None:
                first_t1 = ts_iso
            if hit_t2 and first_t2 is None:
                first_t2 = ts_iso
            if hit_stop and first_stop is None:
                first_stop = ts_iso
            if hit_t1 and hit_stop:
                ambiguous = True

        if first_t1 and not sig.get("target_1_hit_at"):
            fields["target_1_hit_at"] = first_t1
        if first_t2 and not sig.get("target_2_hit_at"):
            fields["target_2_hit_at"] = first_t2
        if first_stop and not sig.get("stop_hit_at"):
            fields["stop_hit_at"] = first_stop
        if ambiguous:
            fields["outcome_notes"] = "Target and stop touched in same 5m candle; exact ordering ambiguous."

    if age >= timedelta(hours=24):
        fields["resolved_at"] = iso(now_utc())
        fields["status"] = "RESOLVED"

        if action != "TRADE":
            fields["outcome"] = "NO_TRADE"
        else:
            t1t = fields.get("target_1_hit_at") or sig.get("target_1_hit_at")
            st = fields.get("stop_hit_at") or sig.get("stop_hit_at")

            if t1t and st:
                if parse_dt(t1t) < parse_dt(st):
                    fields["outcome"] = "WIN"
                elif parse_dt(st) < parse_dt(t1t):
                    fields["outcome"] = "LOSS"
                else:
                    fields["outcome"] = "AMBIGUOUS"
            elif t1t:
                fields["outcome"] = "WIN"
            elif st:
                fields["outcome"] = "LOSS"
            else:
                fields["outcome"] = "EXPIRED"

    return fields


def run_evaluation() -> Dict[str, Any]:
    signals = fetch_recent_signals()
    updated = 0
    errors = []

    for sig in signals:
        try:
            fields = evaluate_one_signal(sig)
            if fields:
                update_signal(sig["id"], fields)
                updated += 1
        except Exception as e:
            errors.append({"id": sig.get("id"), "error": str(e)})

    return {
        "ok": True,
        "checked": len(signals),
        "updated": updated,
        "errors": errors[:10],
    }

# ============================================================
# HISTORICAL BACKTEST
# ============================================================
def backtest_symbol(symbol: str, bars: int = 1200) -> Dict[str, Any]:
    history = get_history(symbol, "15m", bars)
    if len(history) < 150:
        raise RuntimeError("Not enough historical candles")

    threshold = 2.25
    max_hold = 16
    trades = []
    i = 80

    while i < len(history) - max_hold - 2:
        tf = timeframe_features(history[: i + 1])
        if not tf or abs(tf["score"]) < threshold or tf["atr"] <= 0:
            i += 1
            continue

        direction = "LONG" if tf["score"] > 0 else "SHORT"
        entry_bar = history[i + 1]
        entry = entry_bar["open"]
        risk = max(tf["atr"] * 1.55, entry * 0.0035)

        if direction == "LONG":
            stop, target = entry - risk, entry + risk * 1.9
        else:
            stop, target = entry + risk, entry - risk * 1.9

        exit_price = history[min(i + 1 + max_hold, len(history) - 1)]["close"]
        reason = "TIME"

        for j in range(i + 1, min(i + 1 + max_hold, len(history))):
            b = history[j]

            if direction == "LONG":
                hit_stop = b["low"] <= stop
                hit_target = b["high"] >= target
            else:
                hit_stop = b["high"] >= stop
                hit_target = b["low"] <= target

            if hit_stop:
                exit_price = stop
                reason = "STOP"
                break
            if hit_target:
                exit_price = target
                reason = "TARGET"
                break

        net = directional_return(entry, exit_price, direction) - BACKTEST_COST_BPS / 100.0
        trades.append({
            "direction": direction,
            "entry": entry,
            "exit": exit_price,
            "exit_reason": reason,
            "net_return_pct": net,
        })

        i += max_hold

    returns = [t["net_return_pct"] for t in trades]
    wins = [x for x in returns if x > 0]
    losses = [x for x in returns if x <= 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))

    cumulative = 0.0
    peak = 0.0
    max_dd = 0.0
    for r in returns:
        cumulative += r
        peak = max(peak, cumulative)
        max_dd = min(max_dd, cumulative - peak)

    return {
        "ok": True,
        "symbol": symbol,
        "bar": "15m",
        "candles": len(history),
        "strategy_version": STRATEGY_VERSION,
        "cost_bps_round_trip": BACKTEST_COST_BPS,
        "trades": len(trades),
        "win_rate_pct": round((len(wins) / len(trades) * 100.0), 2) if trades else 0,
        "avg_trade_pct": round(mean(returns), 4),
        "profit_factor": round(gross_profit / gross_loss, 3) if gross_loss > 0 else None,
        "sum_net_returns_pct": round(sum(returns), 3),
        "max_drawdown_pct_points": round(max_dd, 3),
        "sample_trades": trades[-20:],
        "warning": "Research backtest only; not yet a full walk-forward portfolio simulation.",
    }

# ============================================================
# AUTH
# ============================================================
def verify_secret(secret: Optional[str], x_scan_secret: Optional[str]) -> None:
    supplied = x_scan_secret or secret or ""
    if not SCAN_SECRET or supplied != SCAN_SECRET:
        raise HTTPException(status_code=401, detail="Unauthorized")

# ============================================================
# ROUTES
# ============================================================
@app.get("/")
def root():
    return {
        "ok": True,
        "service": "Crypto Signal Engine V2",
        "version": STRATEGY_VERSION,
        "endpoints": ["/health", "/scan", "/evaluate", "/backtest", "/universe"],
    }


@app.get("/health")
def health():
    return {
        "ok": True,
        "version": STRATEGY_VERSION,
        "model": OPENAI_MODEL,
        "supabase_configured": bool(SUPABASE_URL and SUPABASE_SECRET_KEY),
        "universe_size": UNIVERSE_SIZE,
        "deep_scan_size": DEEP_SCAN_SIZE,
    }


@app.get("/universe")
def universe(
    secret: Optional[str] = None,
    x_scan_secret: Optional[str] = Header(default=None),
):
    verify_secret(secret, x_scan_secret)
    u = build_universe()
    return {"ok": True, "count": len(u), "top": u[:50]}


@app.get("/scan")
def scan(
    secret: Optional[str] = None,
    x_scan_secret: Optional[str] = Header(default=None),
):
    verify_secret(secret, x_scan_secret)
    try:
        return run_scan()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/evaluate")
def evaluate(
    secret: Optional[str] = None,
    x_scan_secret: Optional[str] = Header(default=None),
):
    verify_secret(secret, x_scan_secret)
    try:
        return run_evaluation()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/backtest")
def backtest(
    symbol: str = "BTC-USDT",
    bars: int = 1200,
    secret: Optional[str] = None,
    x_scan_secret: Optional[str] = Header(default=None),
):
    verify_secret(secret, x_scan_secret)
    symbol = symbol.upper().strip()
    if not re.fullmatch(r"[A-Z0-9]+-USDT", symbol):
        raise HTTPException(status_code=400, detail="Use symbol like BTC-USDT")
    try:
        return backtest_symbol(symbol, bars)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
