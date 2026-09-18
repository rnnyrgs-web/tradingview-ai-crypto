"""Deterministic canonical execution-path evidence shared by engine adapters.

This module deliberately owns only frozen-path accounting. Engines must still
execute independently; this gives reconciliation a common evidence schema.
"""
from __future__ import annotations

def summarize_trades(trades, initial_capital=100000.0):
    equity=float(initial_capital); peak=equity; max_dd=0.0; wins=0
    normalized=[]
    for t in trades:
        pnl=float(t["pnl"]); equity += pnl; peak=max(peak,equity)
        max_dd=max(max_dd,(peak-equity)/peak if peak else 0.0); wins += pnl>0
        normalized.append({k:t[k] for k in ("direction","entry_ts","exit_ts","entry_price","exit_price","size","fees","pnl")})
    n=len(normalized)
    return {"trades":n,"avg_trade_pct":(sum(t["pnl"] for t in normalized)/initial_capital/n*100 if n else 0.0),
            "max_drawdown_pct":max_dd*100,"return_pct":(equity/initial_capital-1)*100,
            "win_rate":wins/n if n else 0.0,"ending_equity":equity}, normalized

def evidence(engine, contract, trades, initial_capital=100000.0):
    metrics, rows=summarize_trades(trades, initial_capital)
    return {"ok":True,"engine":engine,"contract_fingerprint":contract.fingerprint(),
            "research_only":True,"trade_authority":False,"promotion_authority":False,
            "metrics":metrics,"trades":rows}
