from __future__ import annotations

import json
import os
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from research_director import build_daily_lead_report, build_mission, claim_mission, rank_missions

_STATE_PATH = Path(
    os.getenv(
        "RESEARCH_DIRECTOR_STATE_PATH",
        str(Path(tempfile.gettempdir()) / "tradingview-ai-research-director.json"),
    )
)
_lock = Lock()
_state: dict[str, Any] = {
    "updated_at": None,
    "missions": [],
    "claims": [],
    "next_missions": [],
    "daily_lead_report": {},
    "research_only": True,
    "trade_authority": False,
    "promotion_authority": False,
    "write_authority": False,
}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _worker_evidence(row: dict[str, Any]) -> dict[str, Any]:
    evidence = row.get("latest_evidence")
    return evidence if isinstance(evidence, dict) else {}


def _pure_history_block(evidence: dict[str, Any]) -> bool:
    failure_types = evidence.get("failure_type_counts")
    return (
        evidence.get("research_blocked") is True
        and isinstance(failure_types, dict)
        and bool(failure_types)
        and set(failure_types) == {"InsufficientHistory"}
    )


def _mission_for_worker(name: str, row: dict[str, Any]):
    evidence = _worker_evidence(row)
    blocker = "InsufficientHistory" if _pure_history_block(evidence) else None
    if name == "adaptive-accuracy":
        experiment = evidence.get("experiment") if isinstance(evidence.get("experiment"), dict) else {}
        horizon = str(experiment.get("effective_horizon") or "both")
        dimension = str(experiment.get("dimension") or "adaptive")
        group = str(experiment.get("group") or "next-best-restrictive-hypothesis")
        return build_mission(
            lane="adaptive-accuracy",
            horizon=horizon,
            direction=group if dimension == "direction" else "BUY_SELL_WAIT",
            theme=dimension,
            hypothesis=str(experiment.get("hypothesis") or "test the highest-value falsifiable restrictive accuracy hypothesis"),
            expected_information_gain=0.95,
            expected_signal_impact=0.95,
            sample_readiness=0.9 if evidence.get("evidence_conclusion") not in {"no_dispatchable_hypothesis", None} else 0.55,
            novelty=0.9,
            compute_cost=0.55,
            blocker=blocker,
            experiment_id=experiment.get("experiment_id"),
        )
    if name in {"cross-asset-rank-24h", "cross-asset-rank-7d"}:
        horizon = "24h" if name.endswith("24h") else "7d"
        resolved = int(evidence.get("universe_resolved") or 0)
        requested = max(1, int(evidence.get("universe_requested") or 30))
        readiness = min(1.0, resolved / requested)
        return build_mission(
            lane="cross-asset",
            horizon=horizon,
            direction="BUY_SELL_WAIT",
            theme="cross_asset_rank_validation",
            hypothesis=f"validate point-in-time cross-asset ranking edge for {horizon}",
            expected_information_gain=0.88,
            expected_signal_impact=0.9,
            sample_readiness=readiness,
            novelty=0.75,
            compute_cost=0.8,
            blocker=blocker,
        )
    if name == "learning-diagnostics":
        return build_mission(
            lane="learning-diagnostics",
            horizon="both",
            direction="BUY_SELL_WAIT",
            theme="resolved_error_diagnostics",
            hypothesis="diagnose fresh resolved-signal mistakes into falsifiable mechanisms",
            expected_information_gain=0.82,
            expected_signal_impact=0.78,
            sample_readiness=0.85,
            novelty=0.8,
            compute_cost=0.15,
        )
    if name == "experiment-factory":
        return build_mission(
            lane="experiment-factory",
            horizon="both",
            direction="BUY_SELL_WAIT",
            theme="hypothesis_generation",
            hypothesis="convert fresh diagnostics into ranked predeclared experiments",
            expected_information_gain=0.84,
            expected_signal_impact=0.8,
            sample_readiness=0.8,
            novelty=0.9,
            compute_cost=0.15,
        )
    horizon = "7d" if "swing" in name else "24h"
    return build_mission(
        lane="feature-research",
        horizon=horizon,
        direction="BUY_SELL_WAIT",
        theme=name,
        hypothesis=f"search for robust after-cost predictive edge in {name}",
        expected_information_gain=0.62,
        expected_signal_impact=0.62,
        sample_readiness=0.75,
        novelty=0.58,
        compute_cost=0.65,
        blocker=blocker,
    )


def _daily_report(army: dict[str, Any], missions) -> dict[str, Any]:
    workers = army.get("workers") if isinstance(army.get("workers"), dict) else {}
    supervisor = army.get("supervisor") if isinstance(army.get("supervisor"), dict) else {}
    adaptive = _worker_evidence(workers.get("adaptive-accuracy") or {})
    experiment = adaptive.get("experiment") if isinstance(adaptive.get("experiment"), dict) else {}
    conclusion = str(adaptive.get("evidence_conclusion") or "")
    tested = 1 if experiment else 0
    rejected = 1 if conclusion == "validation_failed" else 0
    blocked = sum(1 for mission in missions if mission.blocker)
    validation_passed = 1 if experiment.get("validation_passed") is True else 0
    oos_opened = 1 if adaptive.get("oos_opened") is True else 0
    observability = army.get("observability") if isinstance(army.get("observability"), dict) else {}
    worker_obs = observability.get("workers") if isinstance(observability.get("workers"), dict) else {}
    wait_findings = []
    if experiment and str(experiment.get("dimension")) in {"score_band", "market_regime", "direction", "strategy_identity"}:
        wait_findings.append(
            f"adaptive restrictive test dimension={experiment.get('dimension')} group={experiment.get('group')} conclusion={conclusion or 'pending'}"
        )
    return build_daily_lead_report(
        jobs_considered=len(missions),
        jobs_started=sum(1 for row in workers.values() if isinstance(row, dict) and row.get("state") in {"queued", "running"}),
        jobs_completed=int(army.get("completed_jobs") or 0),
        worker_failures=int(worker_obs.get("failed") or army.get("failed_jobs") or 0),
        timeouts=int(worker_obs.get("timeouts") or 0),
        restarts=int(supervisor.get("task_restarts") or 0),
        experiments_tested=tested,
        experiments_rejected=rejected,
        experiments_blocked=blocked,
        validation_passed=validation_passed,
        untouched_oos_opened=oos_opened,
        metrics={
            "worker_count": int(army.get("worker_count") or 0),
            "heavy_worker_count": int(army.get("heavy_worker_count") or 0),
            "lightweight_worker_count": int(army.get("lightweight_worker_count") or 0),
            "active_jobs": int(army.get("active_jobs") or 0),
        },
        wait_findings=wait_findings,
        execution_findings=[],
        next_missions=rank_missions(missions)[:5],
        production_promotion=False,
    )


def _write_state(payload: dict[str, Any]) -> None:
    try:
        _STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        fd, tmp = tempfile.mkstemp(prefix="research-director-", suffix=".tmp", dir=_STATE_PATH.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(payload, handle, sort_keys=True, separators=(",", ":"))
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp, _STATE_PATH)
        finally:
            try:
                Path(tmp).unlink()
            except FileNotFoundError:
                pass
    except OSError:
        return


def refresh_director(army: dict[str, Any]) -> dict[str, Any]:
    workers = army.get("workers") if isinstance(army.get("workers"), dict) else {}
    missions = [_mission_for_worker(name, row if isinstance(row, dict) else {}) for name, row in sorted(workers.items())]
    claims = []
    for name, row in sorted(workers.items()):
        if not isinstance(row, dict) or row.get("state") not in {"queued", "running"}:
            continue
        mission = next((item for item in missions if item.theme == name or item.lane == name), None)
        if mission is None:
            mission = next((item for item in missions if item.lane == "adaptive-accuracy" and name == "adaptive-accuracy"), None)
        if mission is not None:
            claims.append(claim_mission(mission, worker_id=name, owner_lane=mission.lane).to_dict())
    claimed_ids = {claim["mission_id"] for claim in claims}
    next_missions = [m for m in rank_missions(missions) if not m.blocker and m.mission_id not in claimed_ids][:5]
    visible_missions = sorted(
        missions,
        key=lambda m: (m.priority, m.expected_information_gain, m.expected_signal_impact, m.mission_id),
        reverse=True,
    )
    payload = {
        "updated_at": _now(),
        "missions": [m.to_dict() for m in visible_missions],
        "claims": claims,
        "next_missions": [m.to_dict() for m in next_missions],
        "daily_lead_report": _daily_report(army, missions),
        "research_only": True,
        "trade_authority": False,
        "promotion_authority": False,
        "write_authority": False,
        "broker_connected": False,
        "automatic_strategy_promotion": False,
    }
    with _lock:
        _state.clear()
        _state.update(payload)
    _write_state(payload)
    return payload


def snapshot() -> dict[str, Any]:
    with _lock:
        return json.loads(json.dumps(_state))
