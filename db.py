import httpx
from datetime import timedelta

from config import SUPABASE_URL, SUPABASE_SECRET_KEY
from utils import iso, now_utc

http = httpx.Client(timeout=25.0, follow_redirects=True)

def headers(prefer=None):
    h={
        "apikey":SUPABASE_SECRET_KEY,
        "Authorization":f"Bearer {SUPABASE_SECRET_KEY}",
        "Content-Type":"application/json",
    }
    if prefer:
        h["Prefer"]=prefer
    return h

def configured():
    return bool(SUPABASE_URL and SUPABASE_SECRET_KEY)

def insert_signal(row):
    if not configured():
        return
    r=http.post(
        f"{SUPABASE_URL}/rest/v1/trading_signals",
        headers=headers("return=minimal"), json=row
    )
    if r.status_code>=300:
        raise RuntimeError(f"Supabase insert failed: {r.status_code} {r.text}")

def fetch_recent(hours=800, limit=1000):
    if not configured():
        return []
    cutoff=iso(now_utc()-timedelta(hours=hours))
    params={"select":"*","created_at":f"gte.{cutoff}","order":"created_at.asc","limit":str(limit)}
    r=http.get(f"{SUPABASE_URL}/rest/v1/trading_signals",headers=headers(),params=params)
    if r.status_code>=300:
        raise RuntimeError(f"Supabase select failed: {r.status_code} {r.text}")
    return r.json()

def fetch_latest_signal_id():
    if not configured():
        return 0
    params={"select":"id","order":"id.desc","limit":"1"}
    r=http.get(f"{SUPABASE_URL}/rest/v1/trading_signals",headers=headers(),params=params)
    if r.status_code>=300:
        raise RuntimeError(f"Supabase cursor fetch failed: {r.status_code} {r.text}")
    rows=r.json()
    return int(rows[0]["id"]) if rows else 0

def fetch_actionable_after(after_id=0, limit=20):
    if not configured():
        return []
    after_id=max(0,int(after_id))
    limit=max(1,min(int(limit),100))
    params={
        "select":"id,created_at,symbol,timeframe,direction,action,entry_price,stop_loss,target_1,target_2,risk_reward,evidence_score,market_regime,status,strategy_version",
        "id":f"gt.{after_id}",
        "action":"eq.TRADE",
        "order":"id.asc",
        "limit":str(limit),
    }
    r=http.get(f"{SUPABASE_URL}/rest/v1/trading_signals",headers=headers(),params=params)
    if r.status_code>=300:
        raise RuntimeError(f"Supabase signal feed failed: {r.status_code} {r.text}")
    return r.json()

def fetch_ranked_opportunities(horizon="24h", hours=None, limit=20):
    """Return the latest fresh candidate per symbol, then rank TRADE ahead of WAIT.

    This intentionally does not fabricate twenty trades. If the live engine has fewer
    than twenty actionable setups, WAIT candidates remain visibly labeled as WAIT.
    """
    if not configured():
        return []
    if horizon not in {"24h", "7d"}:
        raise ValueError("horizon must be 24h or 7d")
    lookback = int(hours if hours is not None else (48 if horizon == "24h" else 96))
    cutoff=iso(now_utc()-timedelta(hours=max(1,lookback)))
    params={
        "select":"id,created_at,symbol,timeframe,direction,action,entry_price,stop_loss,target_1,target_2,risk_reward,evidence_score,market_regime,status,strategy_version,reasoning",
        "created_at":f"gte.{cutoff}",
        "timeframe":f"eq.{horizon}",
        "order":"created_at.desc",
        "limit":"500",
    }
    r=http.get(f"{SUPABASE_URL}/rest/v1/trading_signals",headers=headers(),params=params)
    if r.status_code>=300:
        raise RuntimeError(f"Supabase opportunities fetch failed: {r.status_code} {r.text}")
    latest={}
    for row in r.json():
        symbol=str(row.get("symbol") or "")
        if symbol and symbol not in latest:
            latest[symbol]=row
    rows=list(latest.values())
    rows.sort(key=lambda x:(
        1 if str(x.get("action") or "").upper()=="TRADE" else 0,
        float(x.get("evidence_score") or 0),
        float(x.get("risk_reward") or 0),
        int(x.get("id") or 0),
    ), reverse=True)
    return rows[:max(1,min(int(limit),50))]

def fetch_signal_by_id(signal_id):
    if not configured():
        return None
    params={"select":"*","id":f"eq.{int(signal_id)}","limit":"1"}
    r=http.get(f"{SUPABASE_URL}/rest/v1/trading_signals",headers=headers(),params=params)
    if r.status_code>=300:
        raise RuntimeError(f"Supabase signal fetch failed: {r.status_code} {r.text}")
    rows=r.json()
    return rows[0] if rows else None

def patch_signal(signal_id, fields):
    if not fields:
        return
    r=http.patch(
        f"{SUPABASE_URL}/rest/v1/trading_signals",
        headers=headers("return=minimal"),
        params={"id":f"eq.{signal_id}"}, json=fields
    )
    if r.status_code>=300:
        raise RuntimeError(f"Supabase update failed: {r.status_code} {r.text}")
