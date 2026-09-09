from datetime import datetime, timedelta, timezone

from research_director import (
    build_daily_lead_report,
    build_mission,
    claim_is_active,
    claim_mission,
    mission_priority,
    next_claimable_mission,
    rank_missions,
    stable_mission_id,
)


def test_stable_mission_id_is_deterministic():
    a = stable_mission_id("24h", "BUY", "wait", "regime", "suppress weak bull signals")
    b = stable_mission_id("24h", "buy", "WAIT", "REGIME", "suppress weak bull signals")
    assert a == b
    assert a.startswith("mission-")


def test_blocked_work_is_deprioritized():
    unblocked = mission_priority(
        expected_information_gain=0.7,
        expected_signal_impact=0.7,
        sample_readiness=0.7,
        novelty=0.7,
    )
    blocked = mission_priority(
        expected_information_gain=0.9,
        expected_signal_impact=0.9,
        sample_readiness=0.9,
        novelty=0.9,
        blocker="InsufficientHistory",
    )
    assert unblocked > blocked


def test_insufficient_history_gets_future_recheck_and_is_not_ranked_early():
    now = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)
    mission = build_mission(
        lane="accuracy",
        horizon="7d",
        direction="SELL",
        theme="natural-history",
        hypothesis="collect more resolved outcomes",
        expected_information_gain=0.9,
        expected_signal_impact=0.9,
        sample_readiness=0.1,
        novelty=0.5,
        blocker="InsufficientHistory",
        now=now,
    )
    assert mission.recheck_after is not None
    assert rank_missions([mission], now=now) == []
    assert rank_missions([mission], now=now + timedelta(hours=7)) == [mission]


def test_active_claim_prevents_duplicate_assignment_until_lease_expires():
    now = datetime(2026, 9, 9, 12, 0, tzinfo=timezone.utc)
    first = build_mission(
        lane="wait",
        horizon="24h",
        direction="BUY",
        theme="abstention",
        hypothesis="suppress low agreement buys",
        expected_information_gain=0.9,
        expected_signal_impact=0.9,
        sample_readiness=0.8,
        novelty=0.8,
        now=now,
    )
    second = build_mission(
        lane="regime",
        horizon="24h",
        direction="BUY",
        theme="regime",
        hypothesis="suppress high-volatility buys",
        expected_information_gain=0.7,
        expected_signal_impact=0.7,
        sample_readiness=0.8,
        novelty=0.8,
        now=now,
    )
    claim = claim_mission(first, worker_id="worker-1", now=now, lease_minutes=45)
    assert claim_is_active(claim, now=now + timedelta(minutes=10))
    assert next_claimable_mission([first, second], [claim], now=now) == second
    assert not claim_is_active(claim, now=now + timedelta(hours=1))
    assert next_claimable_mission([first, second], [claim], now=now + timedelta(hours=1)) == first


def test_daily_report_explicitly_reports_no_production_promotion():
    report = build_daily_lead_report(
        generated_at=datetime(2026, 9, 9, tzinfo=timezone.utc),
        jobs_considered=10,
        jobs_completed=8,
        experiments_tested=3,
        experiments_rejected=2,
        production_promotion=False,
    )
    assert report["jobs"]["considered"] == 10
    assert report["experiments"]["rejected"] == 2
    assert report["production_promotion_occurred"] is False
    assert "Measured evidence" in report["evidence_note"]
