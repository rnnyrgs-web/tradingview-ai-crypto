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
