"""VectorBT adapter for an immutable frozen signal path."""
from __future__ import annotations
from .availability import require_engine
from .evidence import evidence

def run_vectorbt(contract,bars,entries,exits,direction="long",initial_capital=100000.0):
    require_engine("vectorbt")
    import pandas as pd
    import vectorbt as vbt
    if not (len(bars)==len(entries)==len(exits)):
        raise ValueError("bars/entries/exits length mismatch")
    close=pd.Series([float(x["close"]) for x in bars])
    fee=float(contract.canonical()["cost_bps_round_trip"])/20000.0
    args={"close":close,"fees":fee,"freq":contract.timeframe,"init_cash":initial_capital}
    if direction=="short":
        args.update(short_entries=pd.Series(entries,dtype=bool),short_exits=pd.Series(exits,dtype=bool))
    else:
        args.update(entries=pd.Series(entries,dtype=bool),exits=pd.Series(exits,dtype=bool))
    portfolio=vbt.Portfolio.from_signals(**args)
    rows=[]
    for rec in portfolio.trades.records.to_dict("records"):
        entry_i=int(rec["entry_idx"]); exit_i=int(rec["exit_idx"])
        rows.append({"direction":direction,"entry_ts":int(bars[entry_i]["ts"]),"exit_ts":int(bars[exit_i]["ts"]),
          "entry_price":float(rec["entry_price"]),"exit_price":float(rec["exit_price"]),"size":float(rec["size"]),
          "fees":float(rec["entry_fees"]+rec["exit_fees"]),"pnl":float(rec["pnl"])})
    return evidence("vectorbt",contract,rows,initial_capital)
