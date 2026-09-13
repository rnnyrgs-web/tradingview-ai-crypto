from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from agents.autonomous_cloud_runner import day_start, load_json, month_start, spend_since


def combined_spend_since(states: list[dict[str, Any]], start: datetime) -> float:
    """Sum recorded spend across every engine's runner state since ``start``."""
    return sum(spend_since(state, start) for state in states)


def load_sibling_states(paths: list[Path]) -> list[dict[str, Any]]:
    """Load whichever sibling engine state files currently exist.

    A missing sibling file (an engine that has never run, or is not yet
    enabled) contributes zero spend rather than failing closed, since a
    not-yet-enabled or never-run engine cannot have spent anything.
    """
    states = []
    for path in paths:
        if path.exists():
            states.append(load_json(path))
    return states


def fleet_budget_gate(
    config: dict[str, Any],
    own_state: dict[str, Any],
    sibling_states: list[dict[str, Any]],
    role: str,
    now: datetime,
) -> tuple[bool, str, float]:
    """Fleet-wide backstop on top of (never a replacement for) each engine's own budget_gate.

    orchestration/autonomous_specialist_runner.json, orchestration/autonomous_specialist_runner_claude.json,
    and orchestration/autonomous_specialist_runner_claude_code.json each declare their own
    per-engine daily/monthly reserved-spend ceilings and are individually
    enforced by agents.autonomous_cloud_runner.budget_gate(), unchanged. Those
    per-engine ceilings were each sized against the single shared
    monthly_infrastructure_ceiling_usd in isolation, so summing three
    independently-configured engines' ceilings could exceed that one shared
    ceiling. This function is the additional, fleet-wide check every engine's
    workflow must also pass: it sums this engine's own recorded spend plus
    every sibling engine's recorded spend (loaded from their state files on
    the shared non-main state branch) against the single project-wide
    monthly ceiling, so no combination of per-engine budgets can push
    combined spend past it.
    """
    from agents.autonomous_cloud_runner import reserved_cost_usd  # deferred: avoids importing openai-agents-adjacent code paths at module import time

    raw_reserve = reserved_cost_usd(config, role)
    reserve = raw_reserve * float(config["budget"].get("provider_retry_safety_multiplier", 1.0))
    all_states = [own_state, *sibling_states]
    monthly = combined_spend_since(all_states, month_start(now))
    ceiling = float(config["budget"]["project_monthly_ceiling_usd"])
    projected = monthly + reserve
    if projected > ceiling:
        return False, "FLEET_MONTHLY_WOULD_EXCEED_PROJECT_CEILING", reserve
    return True, "OK", reserve


def main() -> int:
    """CLI used by every engine's workflow as the fleet-wide gate before it executes.

    Exits 0 (and prints the gate result as JSON) when combined fleet spend
    would stay within the shared project ceiling, 1 otherwise. A missing
    ``--sibling`` path (an engine that has never run) is treated as zero
    spend for that engine, never as a failure.
    """
    import argparse

    from agents.autonomous_cloud_runner import load_config, load_state, utc_now

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--role", required=True)
    parser.add_argument("--sibling", action="append", default=[])
    args = parser.parse_args()

    config = load_config(Path(args.config))
    own_state = load_state(Path(args.state))
    sibling_states = load_sibling_states([Path(p) for p in args.sibling])
    ok, reason, reserve = fleet_budget_gate(config, own_state, sibling_states, args.role, utc_now())
    print(json.dumps({"ok": ok, "reason": reason, "reserved_cost_usd": round(reserve, 8)}))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
