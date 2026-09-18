"""CLI preflight for the three-engine research lane."""

from __future__ import annotations

import json

from .availability import engine_availability
from .lean_adapter import lean_available


def preflight() -> dict:
    state = engine_availability()
    state["lean"]["available"] = lean_available()
    ready = all(state[name]["available"] for name in ("vectorbt", "nautilus", "lean"))
    return {
        "ok": ready,
        "status": "READY" if ready else "WAIT_RESEARCH_ONLY",
        "engines": state,
        "research_only": True,
        "trade_authority": False,
    }


if __name__ == "__main__":
    print(json.dumps(preflight(), indent=2))
