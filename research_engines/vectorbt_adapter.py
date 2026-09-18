"""VectorBT adapter for an immutable frozen signal path."""
from __future__ import annotations

from .availability import require_engine
from .dataset import canonical_bars
from .evidence import evidence
from .signals import lagged_signals


def run_vectorbt(
    contract,
    bars,
    entries,
    exits,
    direction="long",
    initial_capital=100000.0,
):
    require_engine("vectorbt")
    import pandas as pd
    import vectorbt as vbt

    rows = canonical_bars(bars)
    if not (len(rows) == len(entries) == len(exits)):
        raise ValueError("bars/entries/exits length mismatch")
    if direction not in {"long", "short"}:
        raise ValueError("direction must be long or short")

    shifted_entries, shifted_exits = lagged_signals(contract, entries, exits)
    close = pd.Series([float(row["close"]) for row in rows])
    fee = float(contract.canonical()["cost_bps_round_trip"]) / 20000.0
    args = {
        "close": close,
        "fees": fee,
        "freq": contract.timeframe,
        "init_cash": initial_capital,
    }
    if direction == "short":
        args.update(
            short_entries=pd.Series(shifted_entries, dtype=bool),
            short_exits=pd.Series(shifted_exits, dtype=bool),
        )
    else:
        args.update(
            entries=pd.Series(shifted_entries, dtype=bool),
            exits=pd.Series(shifted_exits, dtype=bool),
        )

    portfolio = vbt.Portfolio.from_signals(**args)
    trades = []
    for rec in portfolio.trades.records.to_dict("records"):
        entry_i = int(rec["entry_idx"])
        exit_i = int(rec["exit_idx"])
        trades.append(
            {
                "direction": direction,
                "entry_ts": int(rows[entry_i]["ts"]),
                "exit_ts": int(rows[exit_i]["ts"]),
                "entry_price": float(rec["entry_price"]),
                "exit_price": float(rec["exit_price"]),
                "size": float(rec["size"]),
                "fees": float(rec["entry_fees"] + rec["exit_fees"]),
                "pnl": float(rec["pnl"]),
            }
        )
    out = evidence("vectorbt", contract, trades, initial_capital)
    out["decision_lag_bars"] = int(contract.canonical()["decision_lag_bars"])
    return out
