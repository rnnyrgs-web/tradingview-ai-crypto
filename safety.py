from datetime import datetime, timezone
from config import STALE_CANDLE_MINUTES
from utils import now_utc

class SafetyError(RuntimeError):
    pass

def validate_candles(candles, symbol, bar):
    if not candles or len(candles) < 35:
        raise SafetyError(f"{symbol} {bar}: insufficient candles")

    prev_ts = None
    for c in candles:
        if c["close"] <= 0 or c["high"] <= 0 or c["low"] <= 0:
            raise SafetyError(f"{symbol} {bar}: non-positive price")
        if c["high"] < c["low"]:
            raise SafetyError(f"{symbol} {bar}: high < low")
        if not (c["low"] <= c["open"] <= c["high"]):
            raise SafetyError(f"{symbol} {bar}: open outside range")
        if not (c["low"] <= c["close"] <= c["high"]):
            raise SafetyError(f"{symbol} {bar}: close outside range")
        if prev_ts is not None and c["ts"] <= prev_ts:
            raise SafetyError(f"{symbol} {bar}: non-monotonic timestamps")
        prev_ts = c["ts"]

    last_dt = datetime.fromtimestamp(candles[-1]["ts"]/1000, tz=timezone.utc)
    if bar in {"5m","15m"}:
        age_minutes = (now_utc()-last_dt).total_seconds()/60
        if age_minutes > STALE_CANDLE_MINUTES:
            raise SafetyError(f"{symbol} {bar}: stale data ({age_minutes:.1f}m)")

def validate_risk(direction, entry, stop, t1, t2):
    if direction == "LONG":
        if not (t2 > t1 > entry > stop):
            raise SafetyError("LONG invariant failed: t2 > t1 > entry > stop")
    elif direction == "SHORT":
        if not (t2 < t1 < entry < stop):
            raise SafetyError("SHORT invariant failed: t2 < t1 < entry < stop")
    else:
        raise SafetyError("Unknown direction")
