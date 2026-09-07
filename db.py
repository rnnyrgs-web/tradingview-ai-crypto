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
    r=http.post(f"{SUPABASE_URL}/rest/v1/trading_signals",headers=headers("return=minimal"),json=row)
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
    r=http.get(f"{SUPABASE_URL}/rest/v1/trading_signals",headers=headers(),params={"select":"id","order":"id.desc","limit":"1"})
    if r.status_code>=300:
        raise RuntimeError(f"Supabase cursor fetch failed: {r.status_code} {r.text}")
    rows=r.json()
    return int(rows[0]["id"]) if rows else 0

def fetch_actionable_after(after_id=0, limit=20):
    if not configured():
        return []
    params={
        "select":"id,created_at,symbol,timeframe,direction,action,entry_price,stop_loss,target_1,target_2,risk_reward,evidence_score,market_regime,status,strategy_version",
        "id":f"gt.{max(0,int(after_id))}","action":"eq.TRADE","order":"id.asc","limit":str(max(1,min(int(limit),100))),
    }
    r=http.get(f"{SUPABASE_URL}/rest/v1/trading_signals",headers=headers(),params=params)
    if r.status_code>=300:
        raise RuntimeError(f"Supabase signal feed failed: {r.status_code} {r.text}")
    return r.json()

def replace_opportunities(scan_id, horizon, rows):
    if not configured():
        return
    if horizon not in {"24h","7d"}:
        raise ValueError("invalid opportunity horizon")
    if not rows:
        return
    payload=[]
    for row in rows[:20]:
        payload.append({k:v for k,v in row.items() if k in {
            "scan_id","horizon","rank","symbol","direction","action","entry_price","entry_low","entry_high",
            "stop_loss","target_1","target_2","risk_reward","quant_score","evidence_score","market_regime",
            "reasoning","strategy_version"
        }})
    r=http.post(f"{SUPABASE_URL}/rest/v1/crypto_opportunities",headers=headers("return=minimal"),json=payload)
    if r.status_code>=300:
        raise RuntimeError(f"Supabase opportunity insert failed: {r.status_code} {r.text}")

def fetch_ranked_opportunities(horizon="24h", hours=None, limit=20):
    if not configured():
        return []
    if horizon not in {"24h","7d"}:
        raise ValueError("horizon must be 24h or 7d")
    lookback=int(hours if hours is not None else (6 if horizon=="24h" else 12))
    cutoff=iso(now_utc()-timedelta(hours=max(1,lookback)))
    latest_resp=http.get(
        f"{SUPABASE_URL}/rest/v1/crypto_opportunities",headers=headers(),
        params={"select":"scan_id,generated_at","horizon":f"eq.{horizon}","generated_at":f"gte.{cutoff}","order":"generated_at.desc","limit":"1"}
    )
    if latest_resp.status_code>=300:
        raise RuntimeError(f"Supabase latest opportunity fetch failed: {latest_resp.status_code} {latest_resp.text}")
    latest=latest_resp.json()
    if not latest:
        return []
    scan_id=latest[0]["scan_id"]
    r=http.get(
        f"{SUPABASE_URL}/rest/v1/crypto_opportunities",headers=headers(),
        params={"select":"*","scan_id":f"eq.{scan_id}","horizon":f"eq.{horizon}","order":"rank.asc","limit":str(max(1,min(int(limit),20)))}
    )
    if r.status_code>=300:
        raise RuntimeError(f"Supabase opportunities fetch failed: {r.status_code} {r.text}")
    return r.json()

def fetch_signal_by_id(signal_id):
    if not configured():
        return None
    # Dashboard IDs refer to opportunity rows first; legacy signal detail remains a fallback.
    r=http.get(f"{SUPABASE_URL}/rest/v1/crypto_opportunities",headers=headers(),params={"select":"*","id":f"eq.{int(signal_id)}","limit":"1"})
    if r.status_code<300 and r.json():
        row=r.json()[0]
        row["timeframe"]=row.get("horizon")
        return row
    r=http.get(f"{SUPABASE_URL}/rest/v1/trading_signals",headers=headers(),params={"select":"*","id":f"eq.{int(signal_id)}","limit":"1"})
    if r.status_code>=300:
        raise RuntimeError(f"Supabase signal fetch failed: {r.status_code} {r.text}")
    rows=r.json()
    return rows[0] if rows else None

def patch_signal(signal_id, fields):
    if not fields:
        return
    r=http.patch(f"{SUPABASE_URL}/rest/v1/trading_signals",headers=headers("return=minimal"),params={"id":f"eq.{signal_id}"},json=fields)
    if r.status_code>=300:
        raise RuntimeError(f"Supabase update failed: {r.status_code} {r.text}")
