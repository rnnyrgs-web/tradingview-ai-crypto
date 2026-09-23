from datetime import datetime, timedelta, timezone

import pytest

from orchestration.cohorts.strategy_factory_cohort_001_stage1_runner import (
    CANDIDATE_IDS,
    Trade,
    evaluate_stage1,
)

UTC = timezone.utc


def _trade(candidate: str, entry: datetime, gross: float) -> Trade:
    return Trade(
        candidate_id=candidate,
        instrument_key="BTC-USDT-SWAP",
        signal_time=entry - timedelta(hours=1),
        entry_time=entry,
        exit_time=entry + timedelta(hours=1),
        gross_return=gross,
    )


def test_validation_half_does_not_score_signal_formed_in_other_half() -> None:
    """Half-specific robustness evidence must be chronologically self-contained.

    A signal formed on 2026-06-30 23:00 UTC belongs to VAL-H1 information time.
    Even if its entry and exit occur after 2026-07-01 00:00 UTC, it must not be
    allowed to alter VAL-H2's half-specific mean. Overall validation may still
    retain the trade because signal, entry and exit all remain inside the overall
    May-Aug development validation partition.
    """

    candidate = CANDIDATE_IDS[1]
    trades: list[Trade] = []

    train_start = datetime(2025, 8, 1, 0, tzinfo=UTC)
    for i in range(45):
        trades.append(_trade(candidate, train_start + timedelta(days=5 * i), 0.02))

    val1_start = datetime(2026, 5, 2, 0, tzinfo=UTC)
    for i in range(11):
        trades.append(_trade(candidate, val1_start + timedelta(days=4 * i), 0.02))

    # This trade is valid for overall validation, but its signal is still in VAL-H1.
    # A very large return makes accidental inclusion in VAL-H2 deterministic to detect.
    cross_half = Trade(
        candidate_id=candidate,
        instrument_key="BTC-USDT-SWAP",
        signal_time=datetime(2026, 6, 30, 23, tzinfo=UTC),
        entry_time=datetime(2026, 7, 1, 0, tzinfo=UTC),
        exit_time=datetime(2026, 7, 1, 1, tzinfo=UTC),
        gross_return=0.50,
    )
    trades.append(cross_half)

    val2_start = datetime(2026, 7, 2, 0, tzinfo=UTC)
    for i in range(11):
        trades.append(_trade(candidate, val2_start + timedelta(days=4 * i), 0.02))

    result = evaluate_stage1(candidate, trades)

    expected_half_mean = (0.02 - 24.0 / 10_000.0) / 3.0
    assert result.validation_half_means_24bps[1] == pytest.approx(expected_half_mean)
