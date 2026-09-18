"""NautilusTrader event-driven validation adapter.

Only actually executed event-driven trades count as evidence. A generated
configuration/specification is never treated as a successful engine run.
"""
from __future__ import annotations
from .availability import require_engine
from .evidence import evidence

def run_nautilus(contract, bars, engine_runner, initial_capital=100000.0):
    require_engine("nautilus")
    if not callable(engine_runner):
        raise ValueError("a Nautilus event-driven engine runner is required")
    result=engine_runner(contract=contract,bars=bars,initial_capital=initial_capital)
    if not isinstance(result,dict) or result.get("executed") is not True:
        raise RuntimeError("Nautilus did not prove event-driven execution")
    if not isinstance(result.get("trades"),list):
        raise RuntimeError("Nautilus did not return normalized trade evidence")
    out=evidence("nautilus",contract,result["trades"],initial_capital)
    out["execution_mode"]="nautilus_event_driven"
    return out
