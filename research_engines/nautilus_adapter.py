"""NautilusTrader event-driven validation adapter.

Only actually executed event-driven trades count as evidence. A generated
configuration/specification is never treated as a successful engine run.
"""
from __future__ import annotations

from .availability import require_engine
from .dataset import verified_bars
from .evidence import evidence
from .nautilus_runtime import run_event_driven_frozen_path
from .signals import lagged_signals


def run_nautilus(
    contract,
    bars,
    entries,
    exits,
    engine_runner=None,
):
    require_engine("nautilus")
    rows = verified_bars(contract, bars)
    if not (len(rows) == len(entries) == len(exits)):
        raise ValueError("bars/entries/exits length mismatch")

    shifted_entries, shifted_exits = lagged_signals(contract, entries, exits)
    runner = engine_runner or run_event_driven_frozen_path
    if not callable(runner):
        raise ValueError("a Nautilus event-driven engine runner is required")

    result = runner(
        contract=contract,
        bars=rows,
        shifted_entries=shifted_entries,
        shifted_exits=shifted_exits,
    )
    if not isinstance(result, dict) or result.get("executed") is not True:
        raise RuntimeError("Nautilus did not prove event-driven execution")
    if not isinstance(result.get("trades"), list):
        raise RuntimeError("Nautilus did not return normalized trade evidence")
    if int(result.get("bars_processed", -1)) != len(rows):
        raise RuntimeError("Nautilus did not process the complete frozen dataset")

    frozen = contract.canonical()
    capital = float(frozen["validation_initial_capital"])
    out = evidence("nautilus", contract, result["trades"], capital)
    out["execution_mode"] = str(
        result.get("runtime") or "nautilus_event_driven"
    )
    out["decision_lag_bars"] = int(frozen["decision_lag_bars"])
    out["validation_quantity"] = float(frozen["validation_quantity"])
    return out
