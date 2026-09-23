"""Fail-closed deployment canary and rollback recommendation logic.

This module evaluates only runtime health evidence. It cannot deploy, roll back,
write the repository, promote strategies, connect a broker, or authorize trades.
"""

from __future__ import annotations

import os
import time
from datetime import datetime, timezone
from typing import Any

CANARY_GRACE_SECONDS = max(60, min(int(os.getenv("DEPLOY_CANARY_GRACE_SECONDS", "180")), 900))
MIN_WORKER_SAMPLES = max(2, min(int(os.getenv("DEPLOY_CANARY_MIN_WORKER_SAMPLES", "4")), 50))
MAX_WORKER_FAILURE_RATE = max(0.05, min(float(os.getenv("DEPLOY_CANARY_MAX_WORKER_FAILURE_RATE", "0.50")), 1.0))
FACTORY_MAX_CONSECUTIVE_FAILURES = 2
FACTORY_MAX_FUTURE_SKEW_SECONDS = 60

_COORDINATION_STATE_REASON_MAP = {
    "missing_timestamp": "canonical_state_missing_timestamp",
    "malformed_timestamp": "canonical_state_malformed_timestamp",
    "future_timestamp": "canonical_state_future_timestamp",
    "stale_timestamp": "canonical_state_stale",
    "missing_exact_next_step": "canonical_state_missing_exact_next_step",
}
_COORDINATION_ONLY_REASONS = frozenset(_COORDINATION_STATE_REASON_MAP.values())


def _specialist_factory_enabled() -> bool:
    return os.getenv("SPECIALIST_FACTORY_ENABLED", "1").strip().lower() not in {"0", "false", "no", "off"}


def _aware_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    normalized = value.strip()
    if normalized.endswith("Z"):
        normalized = normalized[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError:
        return None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        return None
    return parsed.astimezone(timezone.utc)


def evaluate_specialist_factory_health(
    factory: dict[str, Any] | None,
    *,
    uptime_seconds: float,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Classify the deterministic specialist lane without reacting to one transient failure.

    A factory refresh is normally 5-60 minutes. Two consecutive refresh failures
    or a refresh gap beyond two scheduled intervals plus a small scheduling
    allowance is enough to fail the research-capacity check closed. One isolated
    failure stays visible but does not create restart/rollback churn.
    """
    if not _specialist_factory_enabled():
        return {
            "healthy": True,
            "status": "disabled",
            "reason": None,
            "last_refresh_age_seconds": None,
            "stale_after_seconds": None,
            "consecutive_failures": 0,
        }

    factory = factory if isinstance(factory, dict) else {}
    try:
        refresh_seconds = int(factory.get("refresh_seconds") or 900)
    except (TypeError, ValueError):
        refresh_seconds = 900
    refresh_seconds = max(300, min(refresh_seconds, 3600))
    stale_after_seconds = min(2 * refresh_seconds + 120, 7320)
    try:
        failures = int(factory.get("consecutive_failures") or 0)
    except (TypeError, ValueError):
        failures = FACTORY_MAX_CONSECUTIVE_FAILURES
    failures = max(0, failures)

    result = {
        "healthy": True,
        "status": "healthy",
        "reason": None,
        "last_refresh_age_seconds": None,
        "stale_after_seconds": stale_after_seconds,
        "consecutive_failures": failures,
        "last_error_type": factory.get("last_error_type"),
        "last_success_at": factory.get("last_success_at"),
    }

    if failures >= FACTORY_MAX_CONSECUTIVE_FAILURES:
        result.update(
            healthy=False,
            status="unhealthy",
            reason="specialist_factory_repeated_failures",
        )
        return result

    last_refresh_raw = factory.get("last_refresh_at")
    last_refresh = _aware_timestamp(last_refresh_raw)
    if last_refresh is None:
        if last_refresh_raw not in {None, ""}:
            result.update(
                healthy=False,
                status="unhealthy",
                reason="specialist_factory_invalid_refresh_timestamp",
            )
            return result
        if float(uptime_seconds) > stale_after_seconds:
            result.update(
                healthy=False,
                status="unhealthy",
                reason="specialist_factory_never_refreshed",
            )
            return result
        result["status"] = "warming"
        return result

    current = now if now is not None else datetime.now(timezone.utc)
    if current.tzinfo is None or current.utcoffset() is None:
        raise ValueError("now must be timezone-aware")
    age_seconds = (current.astimezone(timezone.utc) - last_refresh).total_seconds()
    result["last_refresh_age_seconds"] = round(age_seconds, 3)
    if age_seconds < -FACTORY_MAX_FUTURE_SKEW_SECONDS:
        result.update(
            healthy=False,
            status="unhealthy",
            reason="specialist_factory_future_refresh_timestamp",
        )
        return result
    if age_seconds > stale_after_seconds:
        result.update(
            healthy=False,
            status="unhealthy",
            reason="specialist_factory_stale_refresh",
        )
        return result

    last_error = factory.get("last_error_type")
    if last_error and failures == 1:
        result["status"] = "transient_failure"
        return result
    if last_error and failures == 0:
        result.update(
            healthy=False,
            status="unhealthy",
            reason="specialist_factory_inconsistent_failure_state",
        )
        return result

    cycles_completed = int(factory.get("cycles_completed") or 0)
    if cycles_completed > 0 and _aware_timestamp(factory.get("last_success_at")) is None:
        result.update(
            healthy=False,
            status="unhealthy",
            reason="specialist_factory_missing_success_timestamp",
        )
    return result


def evaluate_canary(
    coordinator: dict[str, Any] | None,
    army: dict[str, Any] | None,
    *,
    uptime_seconds: float,
    specialist_factory: dict[str, Any] | None = None,
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

    if specialist_factory is None and _specialist_factory_enabled():
        from continuous_specialist_factory import snapshot as specialist_factory_snapshot

        specialist_factory = specialist_factory_snapshot()
    factory_health = evaluate_specialist_factory_health(
        specialist_factory,
        uptime_seconds=uptime_seconds,
    )

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
    if factory_health.get("healthy") is not True and factory_health.get("reason"):
        reasons.append(str(factory_health["reason"]))

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
        "specialist_factory_health": factory_health,
        "rollback_recommended": rollback_recommended,
        "automatic_rollback_authority": False,
        "deployment_authority": False,
        "repository_write_authority": False,
        "trade_authority": False,
        "promotion_authority": False,
        "broker_connected": False,
        "research_only": True,
    }
