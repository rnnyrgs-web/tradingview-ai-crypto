"""Outcome-blind control-arm executor for EXT-ABNORMAL-DAY-MOMENTUM-001-v1.

This module deliberately does not load the repository dataset and does not decide
whether the replication survives Stage 1.  It only implements the already-frozen
#517/#518 non-random control arms on a caller-supplied candidate schedule so a
legitimate Stage-1 survivor can be falsified without adding post-outcome execution
choices.
"""
from __future__ import annotations

from datetime import timedelta
from typing import Any, Iterable, Mapping, Sequence

from orchestration.external_replication.abnormal_day_momentum_runner import (
    Bar,
    ScoredEvent,
    SignalEvent,
    score_schedule,
    split_by_period,
)
from orchestration.external_replication.run_ext_abnormal_day_momentum_001_stage1 import (
    _portfolio_summary,
)


_NONRANDOM_CONTROL_SPECS = {
    "primary_one_hour_momentum": {
        "direction_source": "baseline",
        "entry_delay_bars": 0,
    },
    "sign_flip_falsifier": {
        "direction_source": "sign_flip",
        "entry_delay_bars": 0,
    },
    "one_bar_delayed_candidate": {
        "direction_source": "candidate",
        "entry_delay_bars": 1,
    },
}


def _structural_no_hold_count(schedule: Sequence[SignalEvent], entry_delay_bars: int) -> int:
    delay = timedelta(hours=entry_delay_bars)
    return sum(event.entry_timestamp + delay >= event.exit_timestamp for event in schedule)


def _is_zero_position_observation(event: ScoredEvent) -> bool:
    """Identify the explicit baseline no-position sentinel emitted by score_schedule().

    A real positioned trade with a flat price path has gross_return == 0 but still
    pays base/stress costs, so it is deliberately *not* classified as a zero position.
    The frozen baseline zero-direction observation is the only scored event whose
    gross, base-cost net and stress-cost net economics are all exactly zero.
    """

    return (
        event.gross_return == 0.0
        and event.net_return == 0.0
        and event.stress_3x_net_return == 0.0
    )


def _control_portfolio_summary(
    scored: Sequence[ScoredEvent], execution: Mapping[str, Any]
) -> dict[str, Any]:
    """Reuse candidate aggregation while preserving zero-position economics at 2x cost.

    The Stage-1 candidate summary reconstructs the diagnostic 2x-cost value from
    gross return because every candidate observation is a positioned trade.  The
    primary control additionally permits an explicit zero-position observation when
    the immediately preceding hourly return is exactly zero.  Such an observation
    must remain zero at every cost stress rather than being charged a fictitious
    round-trip cost.  Base and 3x values are already explicit on ScoredEvent; only
    the reconstructed 2x diagnostic needs this control-aware correction.
    """

    events = tuple(scored)
    summary = _portfolio_summary(events, dict(execution))
    sizing = execution["portfolio_sizing"]
    weight = float(sizing["nav_fraction_per_eligible_instrument"])
    middle_cost = (
        float(execution["screen"]["base_total_cost_bps"])
        * float(execution["screen"]["middle_cost_multiplier"])
        / 10_000.0
    )

    daily_middle: dict[object, float] = {}
    for event in events:
        day = event.signal.signal_timestamp.astimezone().date()
        contribution = (
            0.0
            if _is_zero_position_observation(event)
            else event.gross_return - middle_cost
        )
        daily_middle[day] = daily_middle.get(day, 0.0) + weight * contribution

    summary["total_2x_cost_return"] = sum(daily_middle.values())
    return summary


def _arm_payload(
    *,
    arm_id: str,
    scored: Sequence[ScoredEvent],
    schedule: Sequence[SignalEvent],
    execution: Mapping[str, Any],
    entry_delay_bars: int,
) -> dict[str, Any]:
    periods = split_by_period(scored)
    structural_no_hold = _structural_no_hold_count(schedule, entry_delay_bars)
    expected_scored = len(schedule) - structural_no_hold

    # Candidate-window membership is frozen. Baseline zero-direction observations
    # remain explicit zero-position observations inside score_schedule(), while only
    # the predeclared price-independent no-hold condition may remove a delayed arm.
    if len(scored) != expected_scored:
        raise RuntimeError(
            f"{arm_id} changed frozen candidate-window membership: "
            f"expected {expected_scored} scored windows, got {len(scored)}"
        )

    return {
        "arm_id": arm_id,
        "scheduled_candidate_windows": len(schedule),
        "scored_windows": len(scored),
        "structural_no_hold_windows": structural_no_hold,
        "entry_delay_bars": entry_delay_bars,
        "train": _control_portfolio_summary(periods["train"], execution),
        "validation": _control_portfolio_summary(periods["validation"], execution),
        "protected_oos_opened": False,
        "genuine_forward_opened": False,
        "promotion_authority": False,
        "broker_connected": False,
        "trade_authority": False,
    }


def evaluate_frozen_nonrandom_controls(
    rows: Iterable[Mapping[str, object] | Bar],
    schedule: Sequence[SignalEvent],
    *,
    execution: Mapping[str, Any],
    protected_oos_start: str,
) -> dict[str, dict[str, Any]]:
    """Score the three already-frozen deterministic control arms.

    The caller must pass the exact preformed candidate schedule.  This function may
    not regenerate candidate membership from outcomes.  All arms inherit the same
    fixed 1/3-NAV sizing, UTC-day block aggregation and 24/48/72-bps economics from
    the Stage-1 execution contract. Randomized timing is intentionally excluded: it
    has a separate deterministic schedule-formation contract and must not be silently
    approximated here.
    """
    sizing = execution.get("portfolio_sizing")
    if not isinstance(sizing, Mapping) or sizing.get("controls_use_same_sizing_and_aggregation") is not True:
        raise RuntimeError("control arms require the frozen candidate sizing/aggregation contract")
    if sizing.get("final_same_day_signal_count_normalization_allowed") is not False:
        raise RuntimeError("future-informed same-day renormalization is forbidden for controls")

    materialized_rows = tuple(rows)
    frozen_schedule = tuple(schedule)
    results: dict[str, dict[str, Any]] = {}

    for arm_id, spec in _NONRANDOM_CONTROL_SPECS.items():
        scored = score_schedule(
            materialized_rows,
            frozen_schedule,
            protected_oos_start=protected_oos_start,
            base_cost_bps=float(execution["screen"]["base_total_cost_bps"]),
            stress_multiplier=float(execution["screen"]["stress_multiplier"]),
            direction_source=str(spec["direction_source"]),
            entry_delay_bars=int(spec["entry_delay_bars"]),
        )
        results[arm_id] = _arm_payload(
            arm_id=arm_id,
            scored=scored,
            schedule=frozen_schedule,
            execution=execution,
            entry_delay_bars=int(spec["entry_delay_bars"]),
        )

    return results
