from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from orchestration.external_replication.abnormal_day_momentum_runner import (
    ScoredEvent,
    SignalEvent,
)
from orchestration.external_replication.run_ext_abnormal_day_momentum_001_stage1 import (
    evaluate_stage1_gates,
)


UTC = timezone.utc
EXECUTION_PATH = Path(
    "orchestration/external_replication/ext_abnormal_day_momentum_001_stage1_execution.json"
)


def _crossing_validation_event() -> ScoredEvent:
    """A valid overall-validation event whose exit lands in validation half 2.

    The signal and entry are on the final UTC day of the frozen May-Jun half,
    but the frozen midnight exit is exactly the Jul-Aug half start. Assigning
    this return to half 1 by signal timestamp lets half 1 consume a half-2
    price and makes the two validation halves non-disjoint.
    """

    signal_ts = datetime(2026, 6, 30, 22, tzinfo=UTC)
    signal = SignalEvent(
        instrument="BTC-USDT-SWAP",
        period="validation",
        signal_timestamp=signal_ts,
        entry_timestamp=signal_ts + timedelta(hours=1),
        exit_timestamp=datetime(2026, 7, 1, 0, tzinfo=UTC),
        direction=1,
        baseline_direction=1,
        intraday_return=0.05,
        reference_mean=0.0,
        reference_std=0.01,
    )
    return ScoredEvent(
        signal=signal,
        entry_price=100.0,
        exit_price=101.0,
        gross_return=0.01,
        net_return=0.0076,
        stress_3x_net_return=0.0028,
    )


def test_validation_half_cannot_consume_second_half_boundary_price() -> None:
    execution = json.loads(EXECUTION_PATH.read_text(encoding="utf-8"))

    # Fixed wall-clock validation halves are scientific robustness partitions,
    # not labels on the signal timestamp alone. A return whose exit crosses the
    # half boundary must fail closed (or be structurally excluded under an
    # explicit frozen rule) before half-specific economics are accepted.
    with pytest.raises(RuntimeError, match=r"validation.*half|half.*boundary|chronolog"):
        evaluate_stage1_gates((), (_crossing_validation_event(),), execution)
