"""NautilusTrader integration boundary.

Nautilus requires instrument/venue objects and a BacktestEngine configuration.
This adapter validates installation and emits the frozen execution specification
used by the dedicated event-driven runner; it never silently substitutes a
vectorized result.
"""

from __future__ import annotations

from .availability import require_engine


def build_nautilus_spec(contract, bars) -> dict:
    require_engine("nautilus")
    frozen = contract.canonical()
    return {
        "ok": True,
        "engine": "nautilus",
        "contract_fingerprint": contract.fingerprint(),
        "research_only": True,
        "trade_authority": False,
        "execution_spec": {
            "symbol": frozen["symbol"],
            "timeframe": frozen["timeframe"],
            "decision_lag_bars": frozen["decision_lag_bars"],
            "cost_bps_round_trip": frozen["cost_bps_round_trip"],
            "bars": len(bars),
            "mode": "event_driven_backtest_required",
        },
        "status": "READY_FOR_EVENT_DRIVEN_REPRODUCTION",
    }
