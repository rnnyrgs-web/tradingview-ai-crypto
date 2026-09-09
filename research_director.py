from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
import hashlib
import json
from typing import Any, Iterable


DIRECTOR_VERSION = "v2"
DEFAULT_LEASE_MINUTES = 45
NATURAL_HISTORY_RECHECK_HOURS = 6


@dataclass(frozen=True)
class ResearchMission:
    mission_id: str
    lane: str
    horizon: str
    direction: str
    theme: str
    hypothesis: str
    priority: float
    expected_information_gain: float
    expected_signal_impact: float
    sample_readiness: float
    novelty: float
    falsification_value: float = 0.5
    actionable_evidence_probability: float = 0.5
    compute_cost: float = 0.5
    redundancy_risk: float = 0.0
    blocker: str | None = None
    recheck_after: str | None = None
    experiment_id: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class MissionClaim:
    mission_id: str
    owner_lane: str
    worker_id: str
    claimed_at: str
    lease_expires_at: str
    state: str = "claimed"
    experiment_id: str | None = None
    last_progress_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _utcnow(now: datetime | None = None) -> datetime:
    dt = now or datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def stable_mission_id(*parts: str) -> str:
    payload = "|".join(str(p).strip().lower() for p in parts)
    return "mission-" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:16]


def _clamp01(value: float) -> float:
    return max(0.0, min(1.0, float(value)))


def mission_priority(
    *,
    expected_information_gain: float,
    expected_signal_impact: float,
    sample_readiness: float,
    novelty: float,
    falsification_value: float = 0.5,
    actionable_evidence_probability: float = 0.5,
    compute_cost: float = 0.5,
    redundancy_risk: float = 0.0,
    blocker: str | None = None,
) -> float:
    """Score scarce research by after-cost impact and evidence value per cost.

    The multiplicative core prevents a flashy but non-falsifiable, evidence-poor,
    or very expensive hypothesis from outranking a test that can actually teach
    the system something. Readiness/novelty are small tie-breakers only.
    Blocked work is heavily discounted and never claims the heavy lane.
    """
    info = _clamp01(expected_information_gain)
    impact = _clamp01(expected_signal_impact)
    samples = _clamp01(sample_readiness)
    novel = _clamp01(novelty)
    falsify = _clamp01(falsification_value)
    actionable = _clamp01(actionable_evidence_probability)
    cost = _clamp01(compute_cost)
    redundant = _clamp01(redundancy_risk)

    evidence_value = (0.45 * info + 0.35 * falsify + 0.20 * samples)
    impact_value = (0.80 * impact + 0.20 * actionable)
    cost_efficiency = 1.0 / (0.25 + 0.75 * cost)
    score = evidence_value * impact_value * (0.35 + 0.65 * actionable) * cost_efficiency
    score += 0.04 * novel
    score *= 1.0 - 0.75 * redundant
    if blocker:
        score *= 0.08 if blocker == "InsufficientHistory" else 0.02
    return round(max(0.0, score), 6)


def build_mission(
    *,
    lane: str,
    horizon: str,
    direction: str,
    theme: str,
    hypothesis: str,
    expected_information_gain: float,
    expected_signal_impact: float,
    sample_readiness: float,
    novelty: float,
    falsification_value: float = 0.5,
    actionable_evidence_probability: float = 0.5,
    compute_cost: float = 0.5,
    redundancy_risk: float = 0.0,
    blocker: str | None = None,
    experiment_id: str | None = None,
    now: datetime | None = None,
) -> ResearchMission:
    current = _utcnow(now)
    recheck_after = None
    if blocker == "InsufficientHistory":
        recheck_after = (current + timedelta(hours=NATURAL_HISTORY_RECHECK_HOURS)).isoformat()
    mission_id = stable_mission_id(horizon, direction, lane, theme, hypothesis)
    return ResearchMission(
        mission_id=mission_id,
        lane=lane,
        horizon=horizon,
        direction=direction,
        theme=theme,
        hypothesis=hypothesis,
        priority=mission_priority(
            expected_information_gain=expected_information_gain,
            expected_signal_impact=expected_signal_impact,
            sample_readiness=sample_readiness,
            novelty=novelty,
            falsification_value=falsification_value,
            actionable_evidence_probability=actionable_evidence_probability,
            compute_cost=compute_cost,
            redundancy_risk=redundancy_risk,
            blocker=blocker,
        ),
        expected_information_gain=_clamp01(expected_information_gain),
        expected_signal_impact=_clamp01(expected_signal_impact),
        sample_readiness=_clamp01(sample_readiness),
        novelty=_clamp01(novelty),
        falsification_value=_clamp01(falsification_value),
        actionable_evidence_probability=_clamp01(actionable_evidence_probability),
        compute_cost=_clamp01(compute_cost),
        redundancy_risk=_clamp01(redundancy_risk),
        blocker=blocker,
        recheck_after=recheck_after,
        experiment_id=experiment_id,
    )


def rank_missions(missions: Iterable[ResearchMission], now: datetime | None = None) -> list[ResearchMission]:
    current = _utcnow(now)

    def eligible(mission: ResearchMission) -> bool:
        if not mission.recheck_after:
            return True
        try:
            return datetime.fromisoformat(mission.recheck_after) <= current
        except ValueError:
            return False

    return sorted(
        (m for m in missions if eligible(m)),
        key=lambda m: (
            m.priority,
            m.falsification_value,
            m.actionable_evidence_probability,
            m.expected_information_gain,
            m.expected_signal_impact,
            m.mission_id,
        ),
        reverse=True,
    )


def claim_mission(
    mission: ResearchMission,
    *,
    worker_id: str,
    owner_lane: str | None = None,
    now: datetime | None = None,
    lease_minutes: int = DEFAULT_LEASE_MINUTES,
) -> MissionClaim:
    current = _utcnow(now)
    return MissionClaim(
        mission_id=mission.mission_id,
        owner_lane=owner_lane or mission.lane,
        worker_id=worker_id,
        claimed_at=current.isoformat(),
        lease_expires_at=(current + timedelta(minutes=max(1, lease_minutes))).isoformat(),
        experiment_id=mission.experiment_id,
        last_progress_at=current.isoformat(),
    )


def claim_is_active(claim: MissionClaim | dict[str, Any], now: datetime | None = None) -> bool:
    current = _utcnow(now)
    raw = claim.to_dict() if isinstance(claim, MissionClaim) else claim
    if raw.get("state") not in {"claimed", "running", "queued"}:
        return False
    try:
        return datetime.fromisoformat(str(raw["lease_expires_at"])) > current
    except (KeyError, TypeError, ValueError):
        return False


def next_claimable_mission(
    missions: Iterable[ResearchMission],
    claims: Iterable[MissionClaim | dict[str, Any]],
    *,
    now: datetime | None = None,
) -> ResearchMission | None:
    current = _utcnow(now)
    active_ids = {
        (c.mission_id if isinstance(c, MissionClaim) else str(c.get("mission_id")))
        for c in claims
        if claim_is_active(c, current)
    }
    for mission in rank_missions(missions, current):
        if mission.mission_id not in active_ids and not mission.blocker:
            return mission
    return None


def build_daily_lead_report(
    *,
    generated_at: datetime | None = None,
    jobs_considered: int = 0,
    jobs_started: int = 0,
    jobs_completed: int = 0,
    worker_failures: int = 0,
    timeouts: int = 0,
    restarts: int = 0,
    experiments_tested: int = 0,
    experiments_rejected: int = 0,
    experiments_blocked: int = 0,
    validation_passed: int = 0,
    untouched_oos_opened: int = 0,
    metrics: dict[str, Any] | None = None,
    wait_findings: list[str] | None = None,
    execution_findings: list[str] | None = None,
    next_missions: Iterable[ResearchMission] | None = None,
    production_promotion: bool = False,
) -> dict[str, Any]:
    current = _utcnow(generated_at)
    ranked = list(next_missions or [])[:5]
    return {
        "director_version": DIRECTOR_VERSION,
        "generated_at": current.isoformat(),
        "jobs": {
            "considered": jobs_considered,
            "started": jobs_started,
            "completed": jobs_completed,
            "worker_failures": worker_failures,
            "timeouts": timeouts,
            "restarts": restarts,
        },
        "experiments": {
            "tested": experiments_tested,
            "rejected": experiments_rejected,
            "blocked": experiments_blocked,
            "validation_passed": validation_passed,
            "untouched_oos_opened": untouched_oos_opened,
        },
        "signal_metrics": metrics or {},
        "wait_findings": list(wait_findings or []),
        "execution_findings": list(execution_findings or []),
        "highest_priority_next_missions": [m.to_dict() for m in ranked],
        "production_promotion_occurred": bool(production_promotion),
        "evidence_note": "Measured evidence, hypotheses, and insufficient-history states must remain explicitly distinguished.",
    }


def report_json(**kwargs: Any) -> str:
    return json.dumps(build_daily_lead_report(**kwargs), sort_keys=True, indent=2)
