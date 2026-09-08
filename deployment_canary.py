"""Fail-closed deployment canary and rollback recommendation logic.

This module evaluates only runtime health evidence. It cannot deploy, roll back,
write the repository, promote strategies, connect a broker, or authorize trades.
"""

from __future__ import annotations

import os
import time
from typing import Any

CANARY_GRACE_SECONDS = max(60, min(int(os.getenv("DEPLOY_CANARY_GRACE_SECONDS", "180")), 900))
MIN_WORKER_SAMPLES = max(2, min(int(os.getenv("DEPLOY_CANARY_MIN_WORKER_SAMPLES", "4")), 50))
MAX_WORKER_FAILURE_RATE = max(0.05, min(float(os.getenv("DEPLOY_CANARY_MAX_WORKER_FAILURE_RATE", "0.50")), 1.0))


def evaluate_canary(
    coordinator: dict[str, Any] | None,
    army: dict[str, Any] | None,
    *,
    uptime_seconds: float,
) -> dict[str, Any]:
    """Return a restrictive deployment-health decision from bounded runtime evidence."""
    coordinator = coordinator if isinstance(coordinator, dict) else {}
    army = army if isinstance(army, dict) else {}
    supervisor = army.get("supervisor") if isinstance(army.get("supervisor"), dict) else {}
    observed = army.get("observability") if isinstance(army.get("observability"), dict) else {}
    workers = observed.get("workers") if isinstance(observed.get("workers"), dict) else {}

    completed = int(workers.get("completed") or 0)
    failed = int(workers.get("failed") or 0)
    timeouts = int(workers.get("timeouts") or 0)
    samples = completed + failed
    failure_rate = float(workers.get("failure_rate") or 0.0)

    reasons: list[str] = []
    if coordinator.get("production_ok") is not True:
        reasons.append("production_health_check_failed")
    if coordinator.get("state_ok") is not True:
        reasons.append("canonical_state_check_failed")
    if int(coordinator.get("consecutive_failures") or 0) >= 3:
        reasons.append("coordinator_repeated_failures")
    if supervisor.get("healthy") is not True:
        reasons.append("worker_supervisor_unhealthy")
    if supervisor.get("stale_workers"):
        reasons.append("stale_workers_detected")
    if supervisor.get("crashed_workers"):
        reasons.append("crashed_workers_detected")
    if int(supervisor.get("task_restarts") or 0) > 0:
        reasons.append("worker_restart_detected")
    if samples >= MIN_WORKER_SAMPLES and failure_rate > MAX_WORKER_FAILURE_RATE:
        reasons.append("worker_failure_rate_exceeded")
    if samples >= MIN_WORKER_SAMPLES and timeouts > 0:
        reasons.append("worker_timeout_detected")

    within_grace = float(uptime_seconds) < CANARY_GRACE_SECONDS
    if within_grace:
        status = "warming"
        rollback_recommended = False
    elif reasons:
        status = "rollback_recommended"
        rollback_recommended = True
    else:
        status = "healthy"
        rollback_recommended = False

    return {
        "status": status,
        "within_grace": within_grace,
        "grace_seconds": CANARY_GRACE_SECONDS,
        "uptime_seconds": round(max(0.0, float(uptime_seconds)), 2),
        "reasons": reasons,
        "worker_samples": samples,
        "worker_failure_rate": round(failure_rate, 4) if samples else None,
        "rollback_recommended": rollback_recommended,
        "automatic_rollback_authority": False,
        "deployment_authority": False,
        "repository_write_authority": False,
        "trade_authority": False,
        "promotion_authority": False,
        "broker_connected": False,
        "research_only": True,
    }
