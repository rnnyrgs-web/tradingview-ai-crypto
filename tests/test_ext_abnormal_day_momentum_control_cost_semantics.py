from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from orchestration.external_replication.abnormal_day_momentum_controls import (
    _control_portfolio_summary,
)
from orchestration.external_replication.abnormal_day_momentum_runner import (
    ScoredEvent,
    SignalEvent,
)
from orchestration.external_replication.run_ext_abnormal_day_momentum_001_stage1 import (
    EXECUTION_CONTRACT_PATH,
)

UTC = timezone.utc


def _execution() -> dict:
    return json.loads(Path(EXECUTION_CONTRACT_PATH).read_text(encoding="utf-8"))


def _signal() -> SignalEvent:
    signal_ts = datetime(2025, 6, 11, 12, tzinfo=UTC)
    return SignalEvent(
        instrument="BTC-USDT-SWAP",
        period="train",
        signal_timestamp=signal_ts,
        entry_timestamp=signal_ts + timedelta(hours=1),
        exit_timestamp=(signal_ts + timedelta(days=1)).replace(hour=0),
        direction=1,
        baseline_direction=0,
        intraday_return=0.03,
        reference_mean=0.0,
        reference_std=0.01,
    )


def test_explicit_zero_position_stays_zero_at_every_cost_level() -> None:
    event = ScoredEvent(
        signal=_signal(),
        entry_price=100.0,
        exit_price=103.0,
        gross_return=0.0,
        net_return=0.0,
        stress_3x_net_return=0.0,
    )
    summary = _control_portfolio_summary((event,), _execution())

    assert summary["total_net_return"] == pytest.approx(0.0)
    assert summary["total_2x_cost_return"] == pytest.approx(0.0)
    assert summary["total_3x_cost_return"] == pytest.approx(0.0)


def test_positioned_flat_price_trade_still_pays_all_frozen_costs() -> None:
    # This is intentionally distinct from the zero-position sentinel: a real trade
    # whose entry and exit price are equal still incurs transaction costs.
    event = ScoredEvent(
        signal=_signal(),
        entry_price=100.0,
        exit_price=100.0,
        gross_return=0.0,
        net_return=-0.0024,
        stress_3x_net_return=-0.0072,
    )
    summary = _control_portfolio_summary((event,), _execution())

    assert summary["total_net_return"] == pytest.approx(-0.0024 / 3.0)
    assert summary["total_2x_cost_return"] == pytest.approx(-0.0048 / 3.0)
    assert summary["total_3x_cost_return"] == pytest.approx(-0.0072 / 3.0)
