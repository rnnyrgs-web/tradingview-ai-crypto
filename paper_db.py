import httpx

from config import SUPABASE_URL, SUPABASE_SECRET_KEY
from db import fetch_ranked_opportunities as fetch_production_ranked_opportunities, headers
from utils import iso, now_utc

http = httpx.Client(timeout=25.0, follow_redirects=True)

# Research-only paper shadow policy. This does not mutate production opportunities,
# live signal authority, strategy fingerprints, or broker connectivity. It only
# allows the authentic paper simulator to test the strongest 7d LONG forecasts
# that production correctly keeps at WAIT while forward evidence accumulates.
PAPER_7D_LONG_SHADOW_MIN_EVIDENCE = 80.0
PAPER_7D_LONG_SHADOW_MAX_RANK = 5


def _configured():
    return bool(SUPABASE_URL and SUPABASE_SECRET_KEY)


def fetch_ranked_opportunities(horizon="24h", hours=None, limit=20):
    rows = fetch_production_ranked_opportunities(horizon=horizon, hours=hours, limit=limit)
    if horizon != "7d":
        return rows

    paper_rows = []
    for source in rows:
        row = dict(source)
        direction = str(row.get("direction") or "").upper()
        action = str(row.get("action") or "WAIT").upper()
        try:
            evidence = float(row.get("evidence_score") or 0)
            rank = int(row.get("rank") or 0)
        except (TypeError, ValueError):
            evidence = 0.0
            rank = 0
        if (
            direction == "LONG"
            and action == "WAIT"
            and 1 <= rank <= PAPER_7D_LONG_SHADOW_MAX_RANK
            and evidence >= PAPER_7D_LONG_SHADOW_MIN_EVIDENCE
        ):
            # Copy-only override for the paper simulator. The persisted production
            # opportunity remains WAIT. Existing paper risk, freshness, sizing,
            # visible-depth execution, stop, target, and 168h time-exit rules still apply.
            row["action"] = "TRADE"
            row["paper_shadow"] = True
            row["paper_source_action"] = action
        paper_rows.append(row)
    return paper_rows


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
    allowed = {
        "cash","equity","realized_pnl","peak_equity","max_drawdown_pct","profitable_alert"
    }
    if create:
        allowed.add("initial_cash")
    payload = {k: v for k, v in fields.items() if k in allowed}
    payload["updated_at"] = iso(now_utc())
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


def fetch_all_paper_trades(account_id="default", limit=10000):
    if not _configured():
        return []
    r = http.get(f"{SUPABASE_URL}/rest/v1/paper_trades", headers=headers(), params={
        "select":"*","account_id":f"eq.{account_id}","order":"opened_at.asc","limit":str(max(1, min(int(limit), 10000)))
    })
    if r.status_code >= 300:
        raise RuntimeError(f"Paper trade ledger fetch failed: {r.status_code} {r.text}")
    return r.json()


def insert_paper_trade(row):
    if not _configured():
        return False
    r = http.post(f"{SUPABASE_URL}/rest/v1/paper_trades", headers=headers("resolution=ignore-duplicates,return=representation"), json=row)
    if r.status_code >= 300:
        raise RuntimeError(f"Paper trade insert failed: {r.status_code} {r.text}")
    return bool(r.json())


def close_paper_trade(trade_id, exit_price, exit_reason, pnl_usd, pnl_pct, audit=None):
    if not _configured():
        return False
    stamp = iso(now_utc())
    payload = {
        "status":"CLOSED","closed_at":stamp,"exit_price":exit_price,"exit_reason":exit_reason,
        "pnl_usd":pnl_usd,"pnl_pct":pnl_pct,"updated_at":stamp
    }
    if isinstance(audit, dict):
        for key in (
            "exit_trigger_observed_price","exit_fill_observed_at","exit_supported_notional",
            "exit_slippage_bps","exit_source_count"
        ):
            if key in audit:
                payload[key] = audit[key]
    r = http.patch(f"{SUPABASE_URL}/rest/v1/paper_trades", headers=headers("return=representation"), params={"id":f"eq.{int(trade_id)}","status":"eq.OPEN"}, json=payload)
    if r.status_code >= 300:
        raise RuntimeError(f"Paper trade close failed: {r.status_code} {r.text}")
    return bool(r.json())


def insert_paper_signal_decision(row):
    if not _configured():
        return False
    allowed = {
        "account_id","signal_key","scan_id","symbol","horizon","direction","action",
        "evidence_score","decision","reason","signal_generated_at","decided_at"
    }
    payload = {k: v for k, v in row.items() if k in allowed}
    payload.setdefault("decided_at", iso(now_utc()))
    r = http.post(
        f"{SUPABASE_URL}/rest/v1/paper_signal_decisions",
        headers=headers("resolution=ignore-duplicates,return=representation"),
        params={"on_conflict":"signal_key"},
        json=payload,
    )
    if r.status_code >= 300:
        raise RuntimeError(f"Paper signal decision insert failed: {r.status_code} {r.text}")
    return bool(r.json())


def fetch_paper_signal_decisions(account_id="default", limit=200):
    if not _configured():
        return []
    r = http.get(f"{SUPABASE_URL}/rest/v1/paper_signal_decisions", headers=headers(), params={
        "select":"*","account_id":f"eq.{account_id}","order":"decided_at.desc","limit":str(max(1, min(int(limit), 1000)))
    })
    if r.status_code >= 300:
        raise RuntimeError(f"Paper signal decisions fetch failed: {r.status_code} {r.text}")
    return r.json()


def insert_paper_reconciliation_snapshot(account_id, reconciliation):
    if not _configured():
        return
    data = reconciliation.as_dict() if hasattr(reconciliation, "as_dict") else dict(reconciliation or {})
    payload = {
        "account_id": account_id,
        "verified": bool(data.get("verified")),
        "status": str(data.get("status") or "RECONCILIATION_FAILED"),
        "expected_cash": data.get("expected_cash"),
        "expected_equity": data.get("expected_equity"),
        "expected_realized_pnl": data.get("expected_realized_pnl"),
        "open_pnl": data.get("open_pnl"),
        "open_notional": data.get("open_notional"),
        "cash_delta": data.get("cash_delta"),
        "equity_delta": data.get("equity_delta"),
        "realized_delta": data.get("realized_delta"),
        "trade_mismatch_ids": data.get("trade_mismatch_ids") or [],
        "reasons": data.get("reasons") or [],
    }
    r = http.post(f"{SUPABASE_URL}/rest/v1/paper_reconciliation_snapshots", headers=headers("return=minimal"), json=payload)
    if r.status_code >= 300:
        raise RuntimeError(f"Paper reconciliation insert failed: {r.status_code} {r.text}")


def fetch_latest_paper_reconciliation(account_id="default"):
    if not _configured():
        return None
    r = http.get(f"{SUPABASE_URL}/rest/v1/paper_reconciliation_snapshots", headers=headers(), params={
        "select":"*","account_id":f"eq.{account_id}","order":"created_at.desc","limit":"1"
    })
    if r.status_code >= 300:
        raise RuntimeError(f"Paper reconciliation fetch failed: {r.status_code} {r.text}")
    rows = r.json()
    return rows[0] if rows else None


def insert_paper_equity_snapshot(account_id, equity, cash, open_positions, realized_pnl):
    if not _configured():
        return
    r = http.post(f"{SUPABASE_URL}/rest/v1/paper_equity_snapshots", headers=headers("return=minimal"), json={
        "account_id":account_id,"equity":equity,"cash":cash,"open_positions":open_positions,"realized_pnl":realized_pnl
    })
    if r.status_code >= 300:
        raise RuntimeError(f"Paper equity snapshot insert failed: {r.status_code} {r.text}")


def fetch_paper_trade_stats(account_id="default", initial_cash=100000.0):
    empty = {
        "closed_trades":0,"wins":0,"losses":0,"net_pnl_usd":0.0,"profit_factor":0.0,
        "last_20_pnl_usd":0.0,"max_drawdown_pct":0.0,"consecutive_losses":0,"recent_pnls":[]
    }
    if not _configured():
        return empty
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
    loss_streak = 0
    for x in reversed(pnl):
        if x < 0:
            loss_streak += 1
        else:
            break
    return {
        "closed_trades":len(pnl),"wins":len(wins),"losses":len(losses),"net_pnl_usd":sum(pnl),
        "profit_factor":pf,"last_20_pnl_usd":sum(pnl[-20:]),"max_drawdown_pct":max_dd,
        "consecutive_losses":loss_streak,"recent_pnls":pnl[-20:]
    }


__all__ = [
    "fetch_ranked_opportunities","fetch_paper_account","update_paper_account","fetch_open_paper_trades",
    "fetch_all_paper_trades","insert_paper_trade","close_paper_trade","insert_paper_signal_decision",
    "fetch_paper_signal_decisions","insert_paper_reconciliation_snapshot","fetch_latest_paper_reconciliation",
    "insert_paper_equity_snapshot","fetch_paper_trade_stats"
]
