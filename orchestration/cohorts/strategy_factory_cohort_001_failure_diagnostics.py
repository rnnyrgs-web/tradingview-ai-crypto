from __future__ import annotations

from dataclasses import dataclass
from statistics import fmean
from typing import Iterable
import math

from orchestration.cohorts.strategy_factory_cohort_001_stage1_runner import (
    CANDIDATE_IDS,
    VALIDATION_END,
    VALIDATION_START,
    Stage1Result,
    Trade,
    cluster_independent_events,
)


@dataclass(frozen=True)
class Stage1FailureDiagnostics:
    candidate_id: str
    validation_independent_events: int
    mean_48bps: float | None
    winner_concentration_share_24bps: float


def _validation_trades(candidate_id: str, trades: Iterable[Trade]) -> list[Trade]:
    materialized = list(trades)
    if any(trade.candidate_id != candidate_id for trade in materialized):
        raise RuntimeError("mixed candidate trades are forbidden in failure diagnostics")
    return [
        trade
        for trade in materialized
        if VALIDATION_START <= trade.signal_time <= VALIDATION_END
        and VALIDATION_START <= trade.entry_time <= VALIDATION_END
        and VALIDATION_START <= trade.exit_time <= VALIDATION_END
    ]


def build_stage1_failure_diagnostics(
    candidate_id: str,
    trades: Iterable[Trade],
    result: Stage1Result,
) -> Stage1FailureDiagnostics:
    """Compute only pre-frozen supplemental diagnostics missing from Stage1Result.

    Stage-1 status/classification is deliberately left untouched. Failure learning
    may independently classify preserved tail evidence under #511, but this helper
    cannot change the frozen Stage-1 status precedence.
    """
    if candidate_id not in CANDIDATE_IDS:
        raise RuntimeError("candidate is not Stage-1 authorized")
    if result.candidate_id != candidate_id:
        raise RuntimeError("Stage-1 result candidate_id mismatch")

    validation_events = cluster_independent_events(_validation_trades(candidate_id, trades))
    if len(validation_events) != result.validation.independent_events:
        raise RuntimeError("validation independent-event count diverges from Stage-1 result")

    if not validation_events:
        if result.validation.mean_24bps is not None or result.validation.mean_72bps is not None:
            raise RuntimeError("empty validation events disagree with Stage-1 summary")
        return Stage1FailureDiagnostics(candidate_id, 0, None, 1.0)

    mean_24 = fmean(event.return_at_cost(24.0) for event in validation_events)
    mean_48 = fmean(event.return_at_cost(48.0) for event in validation_events)
    mean_72 = fmean(event.return_at_cost(72.0) for event in validation_events)
    if result.validation.mean_24bps is None or not math.isclose(
        mean_24,
        result.validation.mean_24bps,
        rel_tol=1e-12,
        abs_tol=1e-15,
    ):
        raise RuntimeError("24-bps validation mean diverges from Stage-1 result")
    if result.validation.mean_72bps is None or not math.isclose(
        mean_72,
        result.validation.mean_72bps,
        rel_tol=1e-12,
        abs_tol=1e-15,
    ):
        raise RuntimeError("72-bps validation mean diverges from Stage-1 result")

    base_returns = [event.return_at_cost(24.0) for event in validation_events]
    positive_returns = [value for value in base_returns if value > 0.0]
    positive_pool = sum(positive_returns)
    winner_share = max(positive_returns) / positive_pool if positive_pool > 0.0 else 1.0
    if not 0.0 <= winner_share <= 1.0:
        raise RuntimeError("winner concentration share escaped [0,1]")

    return Stage1FailureDiagnostics(
        candidate_id=candidate_id,
        validation_independent_events=len(validation_events),
        mean_48bps=mean_48,
        winner_concentration_share_24bps=winner_share,
    )
