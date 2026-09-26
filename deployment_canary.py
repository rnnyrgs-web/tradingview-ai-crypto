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

_COORDINATION_STATE_REASON_MAP = {
    "missing_timestamp": "canonical_state_missing_timestamp",
    "malformed_timestamp": "canonical_state_malformed_timestamp",
    "future_timestamp": "canonical_state_future_timestamp",
    "stale_timestamp": "canonical_state_stale",
    "missing_exact_next_step": "canonical_state_missing_exact_next_step",
}
_COORDINATION_ONLY_REASONS = frozenset(_COORDINATION_STATE_REASON_MAP.values())


def evaluate_canary(
    coordinator: dict[str, Any] | None,
    army: dict[str, Any] | None,
    *,
    uptime_seconds: float,
) -> dict[str, Any]:
    """Return a restrictive deployment-health decision from bounded runtime evidence.

    Canonical coordination-state defects fail health closed, but they are kept
    distinct from evidence that the deployed binary should be rolled back. A
    stale handoff requires refreshing/repairing AI_STATE, not guessing that a
    previous deployment is safer.
    """
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
    coordination_state_degraded = False
    if coordinator.get("production_ok") is not True:
        reasons.append("production_health_check_failed")
    if coordinator.get("state_ok") is not True:
        state_failure_reason = coordinator.get("state_failure_reason")
        mapped_reason = _COORDINATION_STATE_REASON_MAP.get(state_failure_reason)
        if mapped_reason is not None:
            reasons.append(mapped_reason)
            coordination_state_degraded = True
        else:
            reasons.append("canonical_state_check_failed")
    if int(coordinator.get("consecutive_failures") or 0) >= 3 and not (
        coordination_state_degraded and coordinator.get("production_ok") is True
    ):
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

    rollback_reasons = [reason for reason in reasons if reason not in _COORDINATION_ONLY_REASONS]
    within_grace = float(uptime_seconds) < CANARY_GRACE_SECONDS
    if within_grace:
        status = "warming"
        rollback_recommended = False
        recommended_action = "observe"
    elif rollback_reasons:
        status = "rollback_recommended"
        rollback_recommended = True
        recommended_action = "rollback_or_freeze"
    elif reasons:
        status = "coordination_state_degraded"
        rollback_recommended = False
        recommended_action = "refresh_or_repair_ai_state"
    else:
        status = "healthy"
        rollback_recommended = False
        recommended_action = "none"

    return {
        "status": status,
        "within_grace": within_grace,
        "grace_seconds": CANARY_GRACE_SECONDS,
        "uptime_seconds": round(max(0.0, float(uptime_seconds)), 2),
        "reasons": reasons,
        "rollback_reasons": rollback_reasons,
        "recommended_action": recommended_action,
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
