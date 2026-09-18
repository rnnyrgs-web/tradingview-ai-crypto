"""VectorBT adapter for an immutable frozen signal path."""
from __future__ import annotations

from .availability import require_engine
from .dataset import verified_bars
from .evidence import evidence
from .signals import lagged_signals


def run_vectorbt(
    contract,
    bars,
    entries,
    exits,
    direction=None,
    initial_capital=None,
):
    require_engine("vectorbt")
    import pandas as pd
    import vectorbt as vbt

    rows = verified_bars(contract, bars)
    if not (len(rows) == len(entries) == len(exits)):
        raise ValueError("bars/entries/exits length mismatch")

    frozen = contract.canonical()
    contract_direction = frozen["direction"]
    if direction is not None and str(direction).lower() != contract_direction:
        raise ValueError("adapter direction disagrees with frozen contract")
    if (
        initial_capital is not None
        and abs(float(initial_capital) - frozen["validation_initial_capital"]) > 1e-9
    ):
        raise ValueError("adapter capital disagrees with frozen contract")

    shifted_entries, shifted_exits = lagged_signals(contract, entries, exits)
    close = pd.Series([float(row["close"]) for row in rows])
    fee = float(frozen["cost_bps_round_trip"]) / 20000.0
    capital = float(frozen["validation_initial_capital"])
    quantity = float(frozen["validation_quantity"])

    args = {
        "close": close,
        "fees": fee,
        "freq": frozen["timeframe"],
        "init_cash": capital,
        "size": quantity,
    }
    if contract_direction == "short":
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
                "direction": contract_direction,
                "entry_ts": int(rows[entry_i]["ts"]),
                "exit_ts": int(rows[exit_i]["ts"]),
                "entry_price": float(rec["entry_price"]),
                "exit_price": float(rec["exit_price"]),
                "size": float(rec["size"]),
                "fees": float(rec["entry_fees"] + rec["exit_fees"]),
                "pnl": float(rec["pnl"]),
            }
        )

    out = evidence("vectorbt", contract, trades, capital)
    out["decision_lag_bars"] = int(frozen["decision_lag_bars"])
    out["validation_quantity"] = quantity
    return out
