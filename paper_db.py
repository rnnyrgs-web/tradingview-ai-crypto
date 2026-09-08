import httpx

from config import SUPABASE_URL, SUPABASE_SECRET_KEY
from db import fetch_ranked_opportunities, headers

http = httpx.Client(timeout=25.0, follow_redirects=True)


def _configured():
    return bool(SUPABASE_URL and SUPABASE_SECRET_KEY)


def fetch_paper_account(account_id="default"):
    if not _configured():
        return None
    r = http.get(f"{SUPABASE_URL}/rest/v1/paper_account", headers=headers(), params={"select":"*","id":f"eq.{account_id}","limit":"1"})
    if r.status_code >= 300:
        raise RuntimeError(f"Paper account fetch failed: {r.status_code} {r.text}")
    rows = r.json()
    return rows[0] if rows else None


def update_paper_account(account_id, fields, create=False):
    if not _configured():
        return
    payload = {k: v for k, v in fields.items() if k in {
        "initial_cash","cash","equity","realized_pnl","peak_equity","max_drawdown_pct","profitable_alert"
    }}
    if create:
        payload = {"id": account_id, **payload}
        r = http.post(f"{SUPABASE_URL}/rest/v1/paper_account", headers=headers("resolution=ignore-duplicates,return=minimal"), json=payload)
    else:
        r = http.patch(f"{SUPABASE_URL}/rest/v1/paper_account", headers=headers("return=minimal"), params={"id":f"eq.{account_id}"}, json=payload)
    if r.status_code >= 300:
        raise RuntimeError(f"Paper account update failed: {r.status_code} {r.text}")


def fetch_open_paper_trades(account_id="default"):
    if not _configured():
        return []
    r = http.get(f"{SUPABASE_URL}/rest/v1/paper_trades", headers=headers(), params={
        "select":"*","account_id":f"eq.{account_id}","status":"eq.OPEN","order":"opened_at.asc","limit":"100"
    })
    if r.status_code >= 300:
        raise RuntimeError(f"Open paper trade fetch failed: {r.status_code} {r.text}")
    return r.json()


def insert_paper_trade(row):
    if not _configured():
        return False
    r = http.post(f"{SUPABASE_URL}/rest/v1/paper_trades", headers=headers("resolution=ignore-duplicates,return=representation"), json=row)
    if r.status_code >= 300:
        raise RuntimeError(f"Paper trade insert failed: {r.status_code} {r.text}")
    return bool(r.json())


def close_paper_trade(trade_id, exit_price, exit_reason, pnl_usd, fees_usd):
    if not _configured():
        return
    payload = {
        "status":"CLOSED","closed_at":"now()","exit_price":exit_price,"exit_reason":exit_reason,
        "pnl_usd":pnl_usd,"pnl_pct":0.0,"updated_at":"now()"
    }
    r = http.patch(f"{SUPABASE_URL}/rest/v1/paper_trades", headers=headers("return=minimal"), params={"id":f"eq.{int(trade_id)}","status":"eq.OPEN"}, json=payload)
    if r.status_code >= 300:
        # Retry without SQL-like timestamp literals; PostgREST expects actual timestamps, not functions.
        from utils import iso, now_utc
        payload["closed_at"] = iso(now_utc())
        payload["updated_at"] = iso(now_utc())
        r = http.patch(f"{SUPABASE_URL}/rest/v1/paper_trades", headers=headers("return=minimal"), params={"id":f"eq.{int(trade_id)}","status":"eq.OPEN"}, json=payload)
    if r.status_code >= 300:
        raise RuntimeError(f"Paper trade close failed: {r.status_code} {r.text}")


def insert_paper_equity_snapshot(account_id, equity, cash, open_positions, realized_pnl):
    if not _configured():
        return
    r = http.post(f"{SUPABASE_URL}/rest/v1/paper_equity_snapshots", headers=headers("return=minimal"), json={
        "account_id":account_id,"equity":equity,"cash":cash,"open_positions":open_positions,"realized_pnl":realized_pnl
    })
    if r.status_code >= 300:
        raise RuntimeError(f"Paper equity snapshot insert failed: {r.status_code} {r.text}")


def fetch_paper_trade_stats(account_id="default", initial_cash=100000.0):
    if not _configured():
        return {"closed_trades":0,"wins":0,"losses":0,"net_pnl_usd":0.0,"profit_factor":0.0,"last_20_pnl_usd":0.0,"max_drawdown_pct":0.0}
    r = http.get(f"{SUPABASE_URL}/rest/v1/paper_trades", headers=headers(), params={
        "select":"pnl_usd,closed_at","account_id":f"eq.{account_id}","status":"eq.CLOSED","order":"closed_at.asc","limit":"10000"
    })
    if r.status_code >= 300:
        raise RuntimeError(f"Paper stats fetch failed: {r.status_code} {r.text}")
    pnl = [float(x.get("pnl_usd") or 0) for x in r.json()]
    wins = [x for x in pnl if x > 0]
    losses = [x for x in pnl if x < 0]
    gross_profit = sum(wins)
    gross_loss = abs(sum(losses))
    pf = gross_profit / gross_loss if gross_loss > 0 else (999.0 if gross_profit > 0 else 0.0)
    equity = float(initial_cash)
    peak = equity
    max_dd = 0.0
    for x in pnl:
        equity += x
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak * 100.0)
    return {
        "closed_trades":len(pnl),"wins":len(wins),"losses":len(losses),"net_pnl_usd":sum(pnl),
        "profit_factor":pf,"last_20_pnl_usd":sum(pnl[-20:]),"max_drawdown_pct":max_dd
    }


__all__ = [
    "fetch_ranked_opportunities","fetch_paper_account","update_paper_account","fetch_open_paper_trades",
    "insert_paper_trade","close_paper_trade","insert_paper_equity_snapshot","fetch_paper_trade_stats"
]
