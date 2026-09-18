"""VectorBT research adapter.

The adapter consumes an already-frozen position path. Strategy discovery and
parameter selection must happen before this layer.
"""

from __future__ import annotations

from .availability import require_engine


def run_vectorbt(contract, bars, entries, exits, direction="long") -> dict:
    require_engine("vectorbt")
    import pandas as pd
    import vectorbt as vbt

    if len(bars) != len(entries) or len(bars) != len(exits):
        raise ValueError("bars/entries/exits length mismatch")
    close = pd.Series([float(row["close"]) for row in bars])
    fees = float(contract.canonical()["cost_bps_round_trip"]) / 20000.0
    kwargs = dict(close=close, entries=pd.Series(entries, dtype=bool), exits=pd.Series(exits, dtype=bool), fees=fees, freq=contract.timeframe)
    if direction == "short":
        kwargs = dict(close=close, short_entries=pd.Series(entries, dtype=bool), short_exits=pd.Series(exits, dtype=bool), fees=fees, freq=contract.timeframe)
    portfolio = vbt.Portfolio.from_signals(**kwargs)
    trades = portfolio.trades.records_readable
    returns = trades["Return"].astype(float) * 100.0 if len(trades) else []
    avg = float(returns.mean()) if len(trades) else 0.0
    return {
        "ok": True,
        "engine": "vectorbt",
        "contract_fingerprint": contract.fingerprint(),
        "research_only": True,
        "trade_authority": False,
        "metrics": {
            "trades": int(len(trades)),
            "avg_trade_pct": avg,
            "max_drawdown_pct": float(portfolio.max_drawdown()) * 100.0,
        },
    }
