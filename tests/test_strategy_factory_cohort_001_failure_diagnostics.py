from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone

import pytest

from orchestration.cohorts.strategy_factory_cohort_001_failure_diagnostics import (
    build_stage1_failure_diagnostics,
)
from orchestration.cohorts.strategy_factory_cohort_001_stage1_runner import (
    CANDIDATE_IDS,
    Trade,
    evaluate_stage1,
)


UTC = timezone.utc


def _trade(candidate: str, entry: datetime, gross: float, instrument: str) -> Trade:
    return Trade(
        candidate,
        instrument,
        entry - timedelta(hours=1),
        entry,
        entry + timedelta(hours=1),
        gross,
    )


def test_failure_diagnostics_add_48bps_and_independent_winner_share_without_changing_status() -> None:
    candidate = CANDIDATE_IDS[1]
    trades = [
        _trade(candidate, datetime(2026, 5, 5, tzinfo=UTC), 0.0200, "BTC-USDT-SWAP"),
        _trade(candidate, datetime(2026, 5, 7, tzinfo=UTC), 0.0100, "ETH-USDT-SWAP"),
        _trade(candidate, datetime(2026, 5, 9, tzinfo=UTC), -0.0050, "SOL-USDT-SWAP"),
    ]
    result = evaluate_stage1(candidate, trades)
    assert result.classification == "INCONCLUSIVE_POWER"

    diagnostics = build_stage1_failure_diagnostics(candidate, trades, result)

    assert diagnostics.validation_independent_events == 3
    assert diagnostics.mean_48bps == pytest.approx((0.0152 + 0.0052 - 0.0098) / 3.0)
    assert diagnostics.winner_concentration_share_24bps == pytest.approx(0.0176 / (0.0176 + 0.0076))
    assert result.classification == "INCONCLUSIVE_POWER"


def test_failure_diagnostics_fail_closed_on_result_divergence() -> None:
    candidate = CANDIDATE_IDS[0]
    trades = [
        _trade(candidate, datetime(2026, 5, 5, tzinfo=UTC), 0.0200, "ETH-USDT-SWAP"),
        _trade(candidate, datetime(2026, 5, 7, tzinfo=UTC), 0.0100, "SOL-USDT-SWAP"),
    ]
    result = evaluate_stage1(candidate, trades)
    tampered_validation = replace(result.validation, mean_24bps=0.123456)
    tampered_result = replace(result, validation=tampered_validation)

    with pytest.raises(RuntimeError, match="24-bps validation mean diverges"):
        build_stage1_failure_diagnostics(candidate, trades, tampered_result)


def test_failure_diagnostics_use_fail_closed_winner_share_when_no_positive_pool() -> None:
    candidate = CANDIDATE_IDS[2]
    trades = [
        _trade(candidate, datetime(2026, 5, 5, tzinfo=UTC), -0.0100, "BTC-USDT-SWAP"),
        _trade(candidate, datetime(2026, 5, 7, tzinfo=UTC), -0.0200, "ETH-USDT-SWAP"),
    ]
    result = evaluate_stage1(candidate, trades)
    diagnostics = build_stage1_failure_diagnostics(candidate, trades, result)

    assert diagnostics.winner_concentration_share_24bps == 1.0
    assert diagnostics.mean_48bps is not None


def test_failure_diagnostics_reject_mixed_candidate_trades() -> None:
    candidate = CANDIDATE_IDS[0]
    other = CANDIDATE_IDS[1]
    trades = [
        _trade(candidate, datetime(2026, 5, 5, tzinfo=UTC), 0.0100, "ETH-USDT-SWAP"),
    ]
    result = evaluate_stage1(candidate, trades)
    mixed = trades + [
        _trade(other, datetime(2026, 5, 7, tzinfo=UTC), 0.0100, "BTC-USDT-SWAP"),
    ]

    with pytest.raises(RuntimeError, match="mixed candidate trades"):
        build_stage1_failure_diagnostics(candidate, mixed, result)
