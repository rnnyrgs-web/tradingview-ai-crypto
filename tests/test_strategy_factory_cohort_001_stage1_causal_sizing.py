from datetime import datetime, timedelta, timezone

import pytest

from orchestration.cohorts.strategy_factory_cohort_001_stage1_runner import (
    CANDIDATE_IDS,
    IndependentEvent,
    Trade,
    cluster_independent_events,
)


UTC = timezone.utc
SLOT_NAV_FRACTION = 1.0 / 3.0
CID = CANDIDATE_IDS[1]
T0 = datetime(2026, 1, 1, 0, tzinfo=UTC)


def _trade(
    instrument: str,
    *,
    entry_hour: int,
    exit_hour: int,
    gross_return: float,
    gross_notional: float = 1.0,
) -> Trade:
    entry = T0 + timedelta(hours=entry_hour)
    return Trade(
        CID,
        instrument,
        entry - timedelta(hours=1),
        entry,
        T0 + timedelta(hours=exit_hour),
        gross_return,
        gross_notional,
    )


def test_fixed_one_third_nav_slot_does_not_depend_on_final_cluster_membership() -> None:
    """A later overlapping signal must not retroactively resize an earlier trade."""
    first = _trade(
        "BTC-USDT-SWAP",
        entry_hour=0,
        exit_hour=6,
        gross_return=0.0100,
        gross_notional=2.0,
    )
    later = _trade(
        "ETH-USDT-SWAP",
        entry_hour=3,
        exit_hour=5,
        gross_return=-0.0040,
        gross_notional=1.0,
    )

    first_only = IndependentEvent(first.entry_time, first.exit_time, (first,))
    combined = IndependentEvent(first.entry_time, first.exit_time, (first, later))

    first_contribution = SLOT_NAV_FRACTION * first.net_return(24.0)
    later_contribution = SLOT_NAV_FRACTION * later.net_return(24.0)

    assert first_only.return_at_cost(24.0) == pytest.approx(first_contribution)
    assert combined.return_at_cost(24.0) == pytest.approx(
        first_contribution + later_contribution
    )
    assert combined.return_at_cost(24.0) - later_contribution == pytest.approx(
        first_only.return_at_cost(24.0)
    )


def test_one_two_three_simultaneous_slots_leave_unused_capacity_as_cash() -> None:
    trades = (
        _trade("BTC-USDT-SWAP", entry_hour=0, exit_hour=4, gross_return=0.0090),
        _trade("ETH-USDT-SWAP", entry_hour=0, exit_hour=4, gross_return=0.0060),
        _trade("SOL-USDT-SWAP", entry_hour=0, exit_hour=4, gross_return=-0.0030),
    )

    one = IndependentEvent(T0, T0 + timedelta(hours=4), trades[:1])
    two = IndependentEvent(T0, T0 + timedelta(hours=4), trades[:2])
    three = IndependentEvent(T0, T0 + timedelta(hours=4), trades)

    assert one.return_at_cost(0.0) == pytest.approx(SLOT_NAV_FRACTION * 0.0090)
    assert two.return_at_cost(0.0) == pytest.approx(
        SLOT_NAV_FRACTION * (0.0090 + 0.0060)
    )
    assert three.return_at_cost(0.0) == pytest.approx(
        SLOT_NAV_FRACTION * (0.0090 + 0.0060 - 0.0030)
    )


def test_internal_multileg_gross_notional_does_not_become_future_portfolio_weight() -> None:
    """Residual-pair normalization happens inside Trade.gross_return, then gets one slot."""
    eth_pair = _trade(
        "ETH-USDT-SWAP",
        entry_hour=0,
        exit_hour=6,
        gross_return=0.0180,
        gross_notional=1.8,
    )
    sol_pair = _trade(
        "SOL-USDT-SWAP",
        entry_hour=0,
        exit_hour=6,
        gross_return=0.0120,
        gross_notional=2.4,
    )
    event = IndependentEvent(T0, T0 + timedelta(hours=6), (eth_pair, sol_pair))

    assert event.return_at_cost(0.0) == pytest.approx(
        SLOT_NAV_FRACTION * (0.0180 + 0.0120)
    )


def test_overlap_clustering_remains_statistical_only_and_half_open() -> None:
    first = _trade("BTC-USDT-SWAP", entry_hour=0, exit_hour=3, gross_return=0.01)
    overlapping = _trade(
        "ETH-USDT-SWAP", entry_hour=2, exit_hour=5, gross_return=-0.01
    )
    equality_is_independent = _trade(
        "SOL-USDT-SWAP", entry_hour=5, exit_hour=6, gross_return=0.02
    )

    events = cluster_independent_events([equality_is_independent, overlapping, first])

    assert len(events) == 2
    assert events[0].trades == (first, overlapping)
    assert events[1].trades == (equality_is_independent,)
    assert events[1].entry_time == events[0].exit_time
