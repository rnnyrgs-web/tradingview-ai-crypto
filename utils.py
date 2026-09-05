from datetime import datetime, timezone
import statistics

def now_utc():
    return datetime.now(timezone.utc)

def iso(dt):
    return dt.astimezone(timezone.utc).isoformat()

def f(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default

def clamp(x, lo, hi):
    return max(lo, min(hi, x))

def mean(xs):
    return sum(xs) / len(xs) if xs else 0.0

def safe_stdev(xs):
    try:
        return statistics.stdev(xs) if len(xs) >= 2 else 0.0
    except Exception:
        return 0.0

def pct_change(a, b):
    return 0.0 if not a else (b / a - 1.0) * 100.0

def parse_dt(s):
    d = datetime.fromisoformat(str(s).replace("Z","+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return d.astimezone(timezone.utc)
