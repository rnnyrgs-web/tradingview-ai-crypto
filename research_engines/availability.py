"""Research engine capability detection.

These adapters never grant trading, paper-ledger, promotion, or broker authority.
"""
from __future__ import annotations

import importlib.util
import shutil

ENGINE_MODULES = {"vectorbt": "vectorbt", "nautilus": "nautilus_trader"}

def _installed(module: str) -> bool:
    return importlib.util.find_spec(module) is not None

def engine_availability() -> dict:
    engines = {
        name: {"available": _installed(module), "module": module, "research_only": True,
               "trade_authority": False, "promotion_authority": False}
        for name, module in ENGINE_MODULES.items()
    }
    lean = shutil.which("lean")
    engines["lean"] = {
        "available": lean is not None,
        "module": None,
        "executable": lean,
        "research_only": True,
        "trade_authority": False,
        "promotion_authority": False,
        "configuration": "local_cli" if lean else "external_cli_or_container_required",
    }
    return engines

def require_engine(name: str) -> dict:
    key = str(name or "").strip().lower()
    state = engine_availability()
    if key not in state:
        raise ValueError(f"unsupported research engine: {key}")
    if not state[key]["available"]:
        raise RuntimeError(f"research engine unavailable: {key}")
    return state[key]
