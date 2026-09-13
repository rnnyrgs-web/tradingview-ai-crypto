from __future__ import annotations

import calendar
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from agents.autonomous_cloud_runner import day_start, load_json, month_start, spend_since


def combined_spend_since(states: list[dict[str, Any]], start: datetime) -> float:
    """Sum recorded spend across every engine's runner state since ``start``."""
    return sum(spend_since(state, start) for state in states)


def load_sibling_states(paths: list[Path]) -> list[dict[str, Any]]:
    """Load whichever sibling engine state files currently exist.

    A missing sibling file (an engine that has never run, or is not yet
    enabled) contributes zero spend. An existing malformed file fails closed
    through load_json/load_state validation rather than being silently ignored.
    """
    states = []
    for path in paths:
        if path.exists():
            states.append(load_json(path))
    return states


def _next_month_start(now: datetime) -> datetime:
    current = month_start(now)
    if current.month == 12:
        return current.replace(year=current.year + 1, month=1)
    return current.replace(month=current.month + 1)


def pacing_snapshot(
    config: dict[str, Any],
    own_state: dict[str, Any],
    sibling_states: list[dict[str, Any]],
    now: datetime,
    reserve: float = 0.0,
) -> dict[str, float]:
    """Return fleet-wide monthly pacing metrics.

    The project has one shared paid-AI allowance. The pacing target advances
    continuously through the calendar month, unused allowance carries forward,
    and a small bounded burst allowance can temporarily run ahead of pace. Any
    overshoot is then repaid by throttling later work until the calendar catches
    up. This prevents spending most of the month's budget in the first few days.
    """
    all_states = [own_state, *sibling_states]
    start = month_start(now)
    end = _next_month_start(now)
    month_seconds = max(1.0, (end - start).total_seconds())
    elapsed_seconds = min(month_seconds, max(0.0, (now - start).total_seconds()))
    elapsed_fraction = elapsed_seconds / month_seconds

    ceiling = float(config["budget"]["project_monthly_ceiling_usd"])
    monthly = combined_spend_since(all_states, start)
    daily = combined_spend_since(all_states, day_start(now))
    projected = monthly + reserve
    target_to_now = ceiling * elapsed_fraction
    burst_allowance = float(config["budget"].get("fleet_pacing_burst_allowance_usd", 2.0))
    paced_limit = min(ceiling, target_to_now + burst_allowance)
    daily_burst_cap = float(config["budget"].get("fleet_daily_burst_cap_usd", 3.0))

    # Forecast is intentionally conservative early in the month. It is an
    # observability metric, not the sole gate, because a one-off important burst
    # should be allowed and then repaid by subsequent throttling.
    min_fraction = 1.0 / float(calendar.monthrange(start.year, start.month)[1])
    forecast_fraction = max(elapsed_fraction, min_fraction)
    projected_month_end = projected / forecast_fraction if forecast_fraction > 0 else ceiling

    return {
        "monthly_spend_usd": monthly,
        "daily_spend_usd": daily,
        "reserved_cost_usd": reserve,
        "projected_after_run_usd": projected,
        "target_to_now_usd": target_to_now,
        "paced_limit_usd": paced_limit,
        "daily_burst_cap_usd": daily_burst_cap,
        "projected_month_end_usd": projected_month_end,
        "elapsed_fraction": elapsed_fraction,
        "ceiling_usd": ceiling,
    }


def fleet_budget_gate(
    config: dict[str, Any],
    own_state: dict[str, Any],
    sibling_states: list[dict[str, Any]],
    role: str,
    now: datetime,
) -> tuple[bool, str, float]:
    """Fleet-wide pacing and hard-ceiling gate for every paid AI engine.

    This is additive to each engine's local safety limits. The shared gate
    enforces one combined project budget, a maximum daily burst, and a rolling
    calendar-month pace. Unused budget carries forward naturally. A bounded
    burst can run ahead of pace for important work, after which routine paid
    work is automatically deferred until the target catches up.
    """
    from agents.autonomous_cloud_runner import reserved_cost_usd  # deferred import

    raw_reserve = reserved_cost_usd(config, role)
    reserve = raw_reserve * float(config["budget"].get("provider_retry_safety_multiplier", 1.0))
    snapshot = pacing_snapshot(config, own_state, sibling_states, now, reserve)

    if snapshot["projected_after_run_usd"] > snapshot["ceiling_usd"]:
        return False, "FLEET_MONTHLY_WOULD_EXCEED_PROJECT_CEILING", reserve

    if snapshot["daily_spend_usd"] + reserve > snapshot["daily_burst_cap_usd"]:
        return False, "FLEET_DAILY_BURST_CAP", reserve

    if snapshot["projected_after_run_usd"] > snapshot["paced_limit_usd"]:
        return False, "FLEET_PACING_AHEAD_OF_SCHEDULE", reserve

    return True, "OK", reserve


def main() -> int:
    """CLI used by every engine's workflow as the fleet-wide gate before it executes."""
    import argparse

    from agents.autonomous_cloud_runner import load_config, load_state, reserved_cost_usd, utc_now

    parser = argparse.ArgumentParser()
    parser.add_argument("--config", required=True)
    parser.add_argument("--state", required=True)
    parser.add_argument("--role", required=True)
    parser.add_argument("--sibling", action="append", default=[])
    args = parser.parse_args()

    config = load_config(Path(args.config))
    own_state = load_state(Path(args.state))
    sibling_states = load_sibling_states([Path(p) for p in args.sibling])
    now = utc_now()
    raw_reserve = reserved_cost_usd(config, args.role)
    reserve = raw_reserve * float(config["budget"].get("provider_retry_safety_multiplier", 1.0))
    ok, reason, _ = fleet_budget_gate(config, own_state, sibling_states, args.role, now)
    metrics = pacing_snapshot(config, own_state, sibling_states, now, reserve)
    print(json.dumps({"ok": ok, "reason": reason, **{k: round(v, 8) for k, v in metrics.items()}}))
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
