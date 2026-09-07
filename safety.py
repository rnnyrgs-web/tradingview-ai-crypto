import math
from datetime import datetime, timezone
from config import STALE_CANDLE_MINUTES
from utils import now_utc

class SafetyError(RuntimeError):
    pass

def _finite_positive(value, label, symbol, bar):
    if not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
        raise SafetyError(f"{symbol} {bar}: invalid {label}")

def validate_candles(candles, symbol, bar):
    if not candles or len(candles) < 35:
        raise SafetyError(f"{symbol} {bar}: insufficient candles")

    prev_ts = None
    seen = set()
    for c in candles:
        for key in ("open", "high", "low", "close"):
            _finite_positive(c.get(key), key, symbol, bar)
        vol = c.get("volume", 0)
        if not isinstance(vol, (int, float)) or not math.isfinite(vol) or vol < 0:
            raise SafetyError(f"{symbol} {bar}: invalid volume")
        ts = c.get("ts")
        if not isinstance(ts, int) or ts <= 0:
            raise SafetyError(f"{symbol} {bar}: invalid timestamp")
        if ts in seen:
            raise SafetyError(f"{symbol} {bar}: duplicate timestamp")
        seen.add(ts)
        if c["high"] < c["low"]:
            raise SafetyError(f"{symbol} {bar}: high < low")
        if not (c["low"] <= c["open"] <= c["high"]):
            raise SafetyError(f"{symbol} {bar}: open outside range")
        if not (c["low"] <= c["close"] <= c["high"]):
            raise SafetyError(f"{symbol} {bar}: close outside range")
        if prev_ts is not None and ts <= prev_ts:
            raise SafetyError(f"{symbol} {bar}: non-monotonic timestamps")
        prev_ts = ts

    last_dt = datetime.fromtimestamp(candles[-1]["ts"]/1000, tz=timezone.utc)
    if last_dt > now_utc():
        raise SafetyError(f"{symbol} {bar}: future-dated candle")
    if bar in {"5m","15m"}:
        age_minutes = (now_utc()-last_dt).total_seconds()/60
        if age_minutes > STALE_CANDLE_MINUTES:
            raise SafetyError(f"{symbol} {bar}: stale data ({age_minutes:.1f}m)")

def validate_risk(direction, entry, stop, t1, t2):
    vals = (entry, stop, t1, t2)
    if any(not isinstance(x, (int, float)) or not math.isfinite(x) or x <= 0 for x in vals):
        raise SafetyError("Risk plan contains invalid price")
    if direction == "LONG":
        if not (t2 > t1 > entry > stop):
            raise SafetyError("LONG invariant failed: t2 > t1 > entry > stop")
    elif direction == "SHORT":
        if not (t2 < t1 < entry < stop):
            raise SafetyError("SHORT invariant failed: t2 < t1 < entry < stop")
    else:
        raise SafetyError("Unknown direction")
