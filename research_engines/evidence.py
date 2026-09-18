"""Deterministic canonical execution-path evidence shared by engine adapters.

This module deliberately owns only frozen-path accounting. Engines must still
execute independently; this gives reconciliation a common evidence schema.
"""
from __future__ import annotations
import math


def finite_number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value)
    except OverflowError:
        return False


def validate_trades(trades):
    """Require finite, chronological, closed single-position round trips."""
    if not isinstance(trades, list):
        raise ValueError("normalized trades must be a list")
    previous_exit = None
    for trade in trades:
        if not isinstance(trade, dict) or trade.get("direction") not in ("long", "short"):
            raise ValueError("invalid normalized trade direction")
        for key in ("entry_ts", "exit_ts"):
            if type(trade.get(key)) is not int or trade[key] <= 0:
                raise ValueError("trade timestamps must be positive integer nanoseconds")
        if trade["exit_ts"] <= trade["entry_ts"]:
            raise ValueError("trade exit must follow entry")
        if previous_exit is not None and trade["entry_ts"] <= previous_exit:
            raise ValueError("normalized trades must be chronological and nonoverlapping")
        for key in ("entry_price", "exit_price", "size", "fees", "pnl"):
            if not finite_number(trade.get(key)):
                raise ValueError(f"trade requires finite {key}")
        if min(trade[k] for k in ("entry_price", "exit_price", "size")) <= 0 or trade["fees"] < 0:
            raise ValueError("trade prices/size must be positive and fees nonnegative")
        previous_exit = trade["exit_ts"]

def summarize_trades(trades, initial_capital=100000.0):
    validate_trades(trades)
    if not finite_number(initial_capital) or initial_capital <= 0:
        raise ValueError("initial capital must be finite and positive")
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
