from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from research_director import build_daily_lead_report, build_mission, claim_is_active, claim_mission, mission_priority, next_claimable_mission, rank_missions, stable_mission_id


def test_stable_mission_id_is_deterministic():
    a = stable_mission_id("24h", "BUY", "wait", "regime", "suppress weak bull signals")
    b = stable_mission_id("24h", "buy", "WAIT", "REGIME", "suppress weak bull signals")
    assert a == b and a.startswith("mission-")


def test_blocked_work_is_deprioritized():
    unblocked = mission_priority(expected_information_gain=0.7, expected_signal_impact=0.7, sample_readiness=0.7, novelty=0.7)
    blocked = mission_priority(expected_information_gain=0.9, expected_signal_impact=0.9, sample_readiness=0.9, novelty=0.9, blocker="InsufficientHistory")
    assert unblocked > blocked


def test_scheduler_prefers_falsifiable_actionable_low_cost_evidence():
    useful = mission_priority(expected_information_gain=0.82, expected_signal_impact=0.82, sample_readiness=0.8, novelty=0.6, falsification_value=0.95, actionable_evidence_probability=0.9, compute_cost=0.2)
    flashy = mission_priority(expected_information_gain=0.98, expected_signal_impact=0.98, sample_readiness=0.35, novelty=1.0, falsification_value=0.2, actionable_evidence_probability=0.2, compute_cost=0.9)
    assert useful > flashy


def test_redundant_hypothesis_is_penalized():
    novel = mission_priority(expected_information_gain=0.8, expected_signal_impact=0.8, sample_readiness=0.8, novelty=0.7, falsification_value=0.8, actionable_evidence_probability=0.8, compute_cost=0.4, redundancy_risk=0.0)
    duplicate = mission_priority(expected_information_gain=0.8, expected_signal_impact=0.8, sample_readiness=0.8, novelty=0.7, falsification_value=0.8, actionable_evidence_probability=0.8, compute_cost=0.4, redundancy_risk=0.9)
    assert novel > duplicate


def test_insufficient_history_gets_future_recheck_and_is_not_ranked_early():
    now = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)
    mission = build_mission(lane="accuracy", horizon="7d", direction="SELL", theme="natural-history", hypothesis="collect more resolved outcomes", expected_information_gain=0.9, expected_signal_impact=0.9, sample_readiness=0.1, novelty=0.5, blocker="InsufficientHistory", now=now)
    assert mission.recheck_after is not None
    assert rank_missions([mission], now=now) == []
    assert rank_missions([mission], now=now + timedelta(hours=7)) == [mission]


def test_active_claim_prevents_duplicate_assignment_until_lease_expires():
    now = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)
    first = build_mission(lane="wait", horizon="24h", direction="BUY", theme="abstention", hypothesis="suppress low agreement buys", expected_information_gain=0.9, expected_signal_impact=0.9, sample_readiness=0.8, novelty=0.8, now=now)
    second = build_mission(lane="regime", horizon="24h", direction="BUY", theme="regime", hypothesis="suppress high-volatility buys", expected_information_gain=0.7, expected_signal_impact=0.7, sample_readiness=0.8, novelty=0.8, now=now)
    claim = claim_mission(first, worker_id="worker-1", now=now, lease_minutes=45)
    assert claim_is_active(claim, now=now + timedelta(minutes=10))
    assert next_claimable_mission([first, second], [claim], now=now) == second
    assert not claim_is_active(claim, now=now + timedelta(hours=1))
    assert next_claimable_mission([first, second], [claim], now=now + timedelta(hours=1)) == first


def test_daily_report_explicitly_reports_no_production_promotion():
    report = build_daily_lead_report(generated_at=datetime(2026, 9, 9, tzinfo=timezone.utc), jobs_considered=10, jobs_completed=8, experiments_tested=3, experiments_rejected=2, production_promotion=False)
    assert report["jobs"]["considered"] == 10
    assert report["experiments"]["rejected"] == 2
    assert report["production_promotion_occurred"] is False
    assert "Measured evidence" in report["evidence_note"]


@pytest.mark.parametrize("nonfinite", [float("nan"), float("inf"), float("-inf")])
def test_mission_admission_rejects_nonfinite_scientific_estimates(nonfinite):
    """Malformed estimates must not become maximum-priority evidence."""
    with pytest.raises(ValueError, match="finite"):
        build_mission(
            lane="strategy-discovery",
            horizon="24h",
            direction="RESEARCH_ONLY",
            theme="malformed-priority",
            hypothesis="non-finite profitability must not claim research capacity",
            expected_information_gain=0.7,
            expected_signal_impact=0.6,
            expected_profitability_impact=nonfinite,
            sample_readiness=0.8,
            novelty=0.7,
        )


@pytest.mark.parametrize(
    "field",
    [
        "priority",
        "expected_information_gain",
        "expected_signal_impact",
        "expected_profitability_impact",
        "sample_readiness",
        "novelty",
        "falsification_value",
        "actionable_evidence_probability",
        "compute_cost",
        "redundancy_risk",
    ],
)
def test_ranking_rejects_nonfinite_scientific_state_on_imported_mission(field):
    """A caller cannot bypass admission by constructing a mission directly."""
    valid = build_mission(
        lane="strategy-discovery",
        horizon="24h",
        direction="RESEARCH_ONLY",
        theme="finite-priority",
        hypothesis="finite mission remains rankable",
        expected_information_gain=0.7,
        expected_signal_impact=0.6,
        expected_profitability_impact=0.5,
        sample_readiness=0.8,
        novelty=0.7,
    )
    forged = replace(valid, mission_id="mission-forged", **{field: float("nan")})

    with pytest.raises(ValueError, match="finite"):
        rank_missions([valid, forged])


def test_finite_population_preserves_legacy_ranking_order_exactly():
    """The fail-closed validation must not reorder any finite mission population."""
    base = build_mission(
        lane="strategy-discovery",
        horizon="24h",
        direction="RESEARCH_ONLY",
        theme="finite-compatibility",
        hypothesis="finite mission ordering remains unchanged",
        expected_information_gain=0.6,
        expected_signal_impact=0.5,
        expected_profitability_impact=0.4,
        sample_readiness=0.7,
        novelty=0.3,
    )
    population = [
        replace(
            base,
            mission_id="mission-low-priority",
            priority=0.25,
            expected_profitability_impact=0.95,
        ),
        replace(
            base,
            mission_id="mission-high-low-profitability",
            priority=0.75,
            expected_profitability_impact=0.2,
        ),
        replace(
            base,
            mission_id="mission-high-high-profitability-z",
            priority=0.75,
            expected_profitability_impact=0.8,
            falsification_value=0.3,
        ),
        replace(
            base,
            mission_id="mission-high-high-profitability-a",
            priority=0.75,
            expected_profitability_impact=0.8,
            falsification_value=0.9,
        ),
    ]

    assert [mission.mission_id for mission in rank_missions(population)] == [
        "mission-high-high-profitability-a",
        "mission-high-high-profitability-z",
        "mission-high-low-profitability",
        "mission-low-priority",
    ]
