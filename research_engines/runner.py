"""CLI preflight for the three-engine research lane."""
from __future__ import annotations

import json
from .availability import engine_availability

def preflight() -> dict:
    state = engine_availability()
    ready = all(state[name]["available"] for name in ("vectorbt", "nautilus", "lean"))
    blockers = []
    if not state["vectorbt"]["available"]:
        blockers.append("install vectorbt in the research runtime")
    if not state["nautilus"]["available"]:
        blockers.append("install nautilus_trader in the research runtime")
    if not state["lean"]["available"]:
        blockers.append("install/configure LEAN CLI and Docker in the research runtime")
    return {
        "ok": ready,
        "status": "READY" if ready else "WAIT_RESEARCH_ONLY",
        "engines": state,
        "blockers": blockers,
        "research_only": True,
        "trade_authority": False,
        "promotion_authority": False,
    }

if __name__ == "__main__":
    print(json.dumps(preflight(), indent=2))
