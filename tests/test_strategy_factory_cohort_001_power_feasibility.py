from __future__ import annotations

from datetime import datetime, timedelta, timezone
import hashlib
import json
from pathlib import Path

from orchestration.cohorts.strategy_factory_cohort_001_stage1_runner import (
    EXPECTED_INSTRUMENTS,
    Trade,
    cluster_independent_events,
)

UTC = timezone.utc
ARTIFACT = (
    Path(__file__).parents[1]
    / "orchestration"
    / "cohorts"
    / "strategy_factory_cohort_001_power_feasibility.json"
)


def _canonical_sha(payload: dict) -> str:
    body = dict(payload)
    body.pop("artifact_sha256", None)
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validation_sundays() -> list[datetime]:
    start = datetime(2026, 5, 1, 0, tzinfo=UTC)
    end = datetime(2026, 8, 31, 23, tzinfo=UTC)
    cursor = start
    signals: list[datetime] = []
    while cursor <= end:
        if cursor.weekday() == 6 and cursor.hour == 23:
            entry = cursor + timedelta(hours=1)
            exit_ = cursor + timedelta(hours=13)
            if start <= entry <= end and start <= exit_ <= end:
                signals.append(cursor)
        cursor += timedelta(hours=1)
    return signals


def test_power_artifact_self_digest_and_authority_locks() -> None:
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    assert payload["artifact_sha256"] == _canonical_sha(payload)
    assert payload["scope"] == "OUTCOME_BLIND_CALENDAR_AND_EXECUTION_GEOMETRY_ONLY"
    assert payload["deterministic_conclusion"]["economic_evidence"] == "NONE_OPENED"
    assert payload["deterministic_conclusion"]["classification"] == "INCONCLUSIVE_POWER_PRE_OUTCOME"
    assert payload["authority"] == {
        "protected_oos_opened": False,
        "genuine_forward_opened": False,
        "broker_connected": False,
        "trade_authority": False,
        "promotion_authority": False,
        "rejected_exact_memory_mutated": False,
        "rejected_semantic_memory_mutated": False,
    }


def test_weekend_candidate_cannot_reach_validation_power_gate_before_outcomes() -> None:
    payload = json.loads(ARTIFACT.read_text(encoding="utf-8"))
    signals = _validation_sundays()
    assert len(signals) == 18
    assert signals[0] == datetime(2026, 5, 3, 23, tzinfo=UTC)
    assert signals[-1] == datetime(2026, 8, 30, 23, tzinfo=UTC)

    # Give every frozen instrument a trade on every possible weekend.  This is the
    # absolute maximum event geometry before applying move/participation filters.
    trades = []
    for signal in signals:
        entry = signal + timedelta(hours=1)
        exit_ = signal + timedelta(hours=13)
        for instrument in EXPECTED_INSTRUMENTS:
            trades.append(
                Trade(
                    "DISC-WEEKEND-NORMALIZE-001-v1",
                    instrument,
                    signal,
                    entry,
                    exit_,
                    0.0,
                )
            )

    events = cluster_independent_events(trades)
    assert len(events) == 18
    assert payload["candidate"]["maximum_possible_validation_independent_events"] == len(events)
    assert payload["candidate"]["minimum_independent_events_validation"] == 20
    assert len(events) < payload["candidate"]["minimum_independent_events_validation"]
    assert payload["candidate"]["power_gate_possible"] is False
