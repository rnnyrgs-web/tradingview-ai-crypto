from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

from agents.autonomous_cloud_runner import (
    day_start,
    load_config,
    load_state,
    month_start,
    reserved_cost_usd,
    spend_since,
)


def check_budget(state_path: Path, role: str, now: datetime | None = None) -> tuple[bool, str, dict[str, float]]:
    now = now or datetime.now(timezone.utc)
    config = load_config()
    state = load_state(state_path)
    budget = config["budget"]

    raw_reserve = reserved_cost_usd(config, role)
    multiplier = float(budget["provider_retry_safety_multiplier"])
    protected_reserve = raw_reserve * multiplier
    daily = spend_since(state, day_start(now))
    monthly = spend_since(state, month_start(now))

    metrics = {
        "daily_spend_usd": daily,
        "monthly_spend_usd": monthly,
        "raw_reserved_call_usd": raw_reserve,
        "protected_reserved_call_usd": protected_reserve,
        "retry_safety_multiplier": multiplier,
    }

    if daily + protected_reserve > float(budget["runner_daily_api_budget_usd"]):
        return False, "DAILY_API_BUDGET", metrics
    if monthly + protected_reserve > float(budget["runner_monthly_api_budget_usd"]):
        return False, "MONTHLY_API_BUDGET", metrics

    projected = (
        float(budget["baseline_infrastructure_reserve_usd"])
        + monthly
        + protected_reserve
        + float(budget["pause_buffer_usd"])
    )
    if projected > float(budget["project_monthly_ceiling_usd"]):
        return False, "PROJECT_MONTHLY_CEILING", metrics

    return True, "OK", metrics


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state", required=True)
    parser.add_argument("--role", required=True)
    args = parser.parse_args()

    ok, reason, metrics = check_budget(Path(args.state), args.role)
    print(json.dumps({"ok": ok, "reason": reason, **metrics}, sort_keys=True))
    return 0 if ok else 2


if __name__ == "__main__":
    raise SystemExit(main())
