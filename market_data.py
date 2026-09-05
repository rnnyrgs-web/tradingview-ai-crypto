import time
from datetime import datetime, timezone, timedelta
import httpx

from config import OKX_BASE, MIN_QUOTE_VOLUME, MAX_SPREAD_BPS, STABLE_BASES, UNIVERSE_SIZE
from utils import f, pct_change

http = httpx.Client(timeout=25.0, follow_redirects=True)

def okx_get(path, params=None):
    r = http.get(f"{OKX_BASE}{path}", params=params or {})
    r.raise_for_status()
    obj = r.json()
    if str(obj.get("code","0")) != "0":
        raise RuntimeError(f"OKX error {obj.get('code')}: {obj.get('msg')}")
    return obj.get("data", [])

def get_spot_tickers():
    return okx_get("/api/v5/market/tickers", {"instType":"SPOT"})

def normalize_candles(rows):
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

def get_candles(symbol, bar="15m", limit=120):
    rows = okx_get("/api/v5/market/candles", {
        "instId": symbol, "bar": bar, "limit": str(min(limit, 300))
    })
    return normalize_candles(rows)

def get_history(symbol, bar="15m", bars=1000):
    wanted = max(100, min(bars, 5000))
    collected = []
    after = None
    while len(collected) < wanted:
        params = {"instId":symbol, "bar":bar, "limit":str(min(100,wanted-len(collected)))}
        if after:
            params["after"] = after
        rows = okx_get("/api/v5/market/history-candles", params)
        if not rows:
            break
        collected.extend(rows)
        after = str(min(int(r[0]) for r in rows))
        if len(rows) < int(params["limit"]):
            break
        time.sleep(0.04)
    by_ts = {int(r[0]): r for r in collected}
    rows = [by_ts[k] for k in sorted(by_ts.keys(), reverse=True)][:wanted]
    return normalize_candles(rows)

def get_derivatives(base):
    inst = f"{base}-USDT-SWAP"
    out = {"swap_available":False, "funding_rate":None, "open_interest":None}
    try:
        fr = okx_get("/api/v5/public/funding-rate", {"instId":inst})
        if fr:
            out["funding_rate"] = f(fr[0].get("fundingRate"), None)
            out["swap_available"] = True
    except Exception:
        pass
    try:
        oi = okx_get("/api/v5/public/open-interest", {"instType":"SWAP","instId":inst})
        if oi:
            out["open_interest"] = f(oi[0].get("oiCcy") or oi[0].get("oi"), None)
            out["swap_available"] = True
    except Exception:
        pass
    return out

def build_universe():
    rows = []
    for t in get_spot_tickers():
        inst = str(t.get("instId",""))
        if not inst.endswith("-USDT"):
            continue
        base = inst.split("-")[0]
        if base in STABLE_BASES:
            continue
        last = f(t.get("last"))
        open24 = f(t.get("open24h"))
        bid = f(t.get("bidPx"))
        ask = f(t.get("askPx"))
        qv = f(t.get("volCcy24h"))
        if qv <= 0:
            qv = f(t.get("vol24h")) * max(last,0)
        if last <= 0 or qv < MIN_QUOTE_VOLUME:
            continue
        spread_bps = ((ask-bid)/last*10000.0) if bid>0 and ask>0 else 999
        if spread_bps > MAX_SPREAD_BPS:
            continue
        change24 = pct_change(open24,last) if open24 > 0 else 0.0
        activity = (
            __import__("math").log10(max(qv,1))*0.65
            + abs(change24)*0.25
            - min(spread_bps,50)*0.03
        )
        rows.append({
            "symbol":inst, "base":base, "last":last,
            "quote_volume_24h":qv, "change_24h_pct":change24,
            "spread_bps":spread_bps, "activity_score":activity
        })
    rows.sort(key=lambda x:x["activity_score"], reverse=True)
    return rows[:UNIVERSE_SIZE]
