"""Deterministic outcome-blind randomized-timing placebo for abnormal-day momentum.

The placebo is formed at the authoritative UTC signal-day portfolio-block level so
randomization cannot manufacture extra independent observations by scattering
same-day cross-instrument candidate signals across different placebo days.
Only timestamp-safe eligibility and past/contemporaneous data needed by the
candidate's own formation rules may affect the randomized schedule. Forward
entry-to-exit returns are read only later by ``score_schedule``.
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone
from math import isfinite
from statistics import stdev
from typing import Any, Iterable, Mapping, Sequence

from orchestration.external_replication.abnormal_day_momentum_runner import (
    Bar,
    SignalEvent,
    normalize_development_rows,
    score_schedule,
    split_by_period,
)
from orchestration.external_replication.run_ext_abnormal_day_momentum_001_stage1 import (
    _portfolio_summary,
)

UTC = timezone.utc
HOUR = timedelta(hours=1)
DAY = timedelta(days=1)


class RandomizedTimingPlaceboInconclusiveError(RuntimeError):
    """Fail closed when the frozen placebo cannot be formed without shrinking it."""


def _parse_utc(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        parsed = value
    else:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("timestamp must be timezone-aware")
    parsed = parsed.astimezone(UTC)
    if parsed.minute or parsed.second or parsed.microsecond:
        raise ValueError("timestamp must lie on the UTC hourly grid")
    return parsed


def _day_start(value: datetime) -> datetime:
    return value.astimezone(UTC).replace(hour=0, minute=0, second=0, microsecond=0)


def _validate_contract(contract: Mapping[str, Any]) -> None:
    if contract.get("contract_id") != (
        "EXT-ABNORMAL-DAY-MOMENTUM-001-v1-RANDOMIZED-TIMING-PLACEBO-v1"
    ):
        raise RuntimeError("unexpected randomized-timing placebo contract")
    if contract.get("formed_before_replication_outcomes") is not True:
        raise RuntimeError("placebo must be frozen before replication outcomes")
    formation = contract.get("formation")
    if not isinstance(formation, Mapping):
        raise RuntimeError("placebo formation contract is missing")
    if formation.get("draw_count") != 1 or formation.get("post_outcome_redraw_allowed") is not False:
        raise RuntimeError("placebo contract must permit exactly one deterministic draw")
    if formation.get("authoritative_randomization_unit") != (
        "unique_utc_signal_day_portfolio_block"
    ):
        raise RuntimeError("placebo must randomize authoritative UTC-day blocks")
    if formation.get("candidate_signal_days_excluded") is not True:
        raise RuntimeError("candidate signal days must be excluded from placebo timing")
    if formation.get("placebo_days_without_replacement") is not True:
        raise RuntimeError("placebo UTC days must be selected without replacement")
    eligibility = contract.get("candidate_eligibility")
    if not isinstance(eligibility, Mapping):
        raise RuntimeError("candidate eligibility contract is missing")
    if eligibility.get("reference_days") != 90:
        raise RuntimeError("placebo warmup must match the frozen 90-day candidate rule")
    if eligibility.get("latest_signal_hour_utc") != 22:
        raise RuntimeError("placebo decision-hour cap drifted")
    if eligibility.get("entry_delay_hours") != 1:
        raise RuntimeError("placebo entry delay drifted")
    scoring = contract.get("scoring")
    if not isinstance(scoring, Mapping):
        raise RuntimeError("placebo scoring contract is missing")
    if scoring.get("same_candidate_cost_semantics") is not True:
        raise RuntimeError("placebo must use candidate cost semantics")
    if scoring.get("same_portfolio_sizing_and_utc_day_aggregation") is not True:
        raise RuntimeError("placebo must preserve candidate portfolio aggregation")
    if scoring.get("final_same_day_signal_count_normalization_allowed") is not False:
        raise RuntimeError("future-informed same-day normalization is forbidden")
    authority = contract.get("authority")
    if authority != {
        "research_only": True,
        "promotion_authority": False,
        "broker_connected": False,
        "trade_authority": False,
        "protected_oos_opened": False,
        "genuine_forward_opened": False,
    }:
        raise RuntimeError("placebo authority must remain research-only")


def _complete_daily_returns(
    by_instrument_ts: Mapping[str, Mapping[datetime, Bar]],
) -> dict[str, dict[datetime, float]]:
    result: dict[str, dict[datetime, float]] = {}
    for instrument, index in by_instrument_ts.items():
        days = sorted({_day_start(ts) for ts in index})
        instrument_returns: dict[datetime, float] = {}
        for day in days:
            day_bars = [index.get(day + hour * HOUR) for hour in range(24)]
            if any(bar is None for bar in day_bars):
                continue
            first = day_bars[0]
            last = day_bars[-1]
            assert first is not None and last is not None
            instrument_returns[day] = last.close / first.open - 1.0
        result[instrument] = instrument_returns
    return result


def _validation_half(ts: datetime, windows: Mapping[str, Any]) -> str | None:
    if _parse_utc(windows["validation_first_start_utc"]) <= ts <= _parse_utc(
        windows["validation_first_end_utc"]
    ):
        return "validation_first"
    if _parse_utc(windows["validation_second_start_utc"]) <= ts <= _parse_utc(
        windows["validation_second_end_utc"]
    ):
        return "validation_second"
    return None


def _period_and_half(ts: datetime, windows: Mapping[str, Any]) -> tuple[str, str] | None:
    train_start = _parse_utc(windows["train_start_utc"])
    train_end = _parse_utc(windows["train_end_utc"])
    validation_start = _parse_utc(windows["validation_start_utc"])
    validation_end = _parse_utc(windows["validation_end_utc"])
    if train_start <= ts <= train_end:
        return ("train", "train")
    if validation_start <= ts <= validation_end:
        half = _validation_half(ts, windows)
        if half is None:
            raise RuntimeError("validation timestamp is outside frozen validation halves")
        return ("validation", half)
    return None


def _eligible_timestamp(
    *,
    instrument: str,
    ts: datetime,
    by_instrument_ts: Mapping[str, Mapping[datetime, Bar]],
    daily_returns: Mapping[str, Mapping[datetime, float]],
    windows: Mapping[str, Any],
    reference_days: int,
    latest_signal_hour: int,
) -> bool:
    if ts.hour > latest_signal_hour:
        return False
    period_half = _period_and_half(ts, windows)
    if period_half is None:
        return False
    period, half = period_half
    index = by_instrument_ts.get(instrument, {})
    day = _day_start(ts)

    # Candidate signal-day continuity is part of eligibility and uses only data
    # observable by the decision timestamp.
    for hour in range(ts.hour + 1):
        if index.get(day + hour * HOUR) is None:
            return False

    completed = daily_returns.get(instrument, {})
    prior_days = sorted(d for d in completed if d < day)
    if len(prior_days) < reference_days:
        return False
    reference = [completed[d] for d in prior_days[-reference_days:]]
    reference_std = stdev(reference)
    if not isfinite(reference_std) or reference_std <= 0:
        return False

    entry = ts + HOUR
    exit_ts = day + DAY
    if index.get(entry) is None or index.get(exit_ts) is None:
        return False

    if period == "train":
        if exit_ts > _parse_utc(windows["train_end_utc"]):
            return False
    else:
        if exit_ts > _parse_utc(windows["validation_end_utc"]):
            return False
        exit_half = _validation_half(exit_ts, windows)
        if exit_half != half:
            return False
    if exit_ts >= _parse_utc(windows["protected_oos_start_utc"]):
        return False
    return True


def _source_blocks(
    schedule: Sequence[SignalEvent],
    windows: Mapping[str, Any],
) -> tuple[tuple[datetime, str, str, tuple[SignalEvent, ...]], ...]:
    grouped: dict[tuple[datetime, str, str], list[SignalEvent]] = {}
    for signal in schedule:
        signal_ts = signal.signal_timestamp.astimezone(UTC)
        period_half = _period_and_half(signal_ts, windows)
        if period_half is None:
            raise RuntimeError("candidate schedule escaped frozen train/validation windows")
        period, half = period_half
        if signal.period != period:
            raise RuntimeError("candidate period label disagrees with frozen chronology")
        key = (_day_start(signal_ts), period, half)
        grouped.setdefault(key, []).append(signal)

    blocks: list[tuple[datetime, str, str, tuple[SignalEvent, ...]]] = []
    for (day, period, half), events in grouped.items():
        ordered = tuple(sorted(events, key=lambda e: (e.instrument, e.signal_timestamp)))
        if len({event.instrument for event in ordered}) != len(ordered):
            raise RuntimeError("candidate UTC-day block has duplicate instrument")
        if any(event.direction not in {-1, 1} for event in ordered):
            raise RuntimeError("candidate placebo matching requires long/short directions")
        blocks.append((day, period, half, ordered))
    return tuple(sorted(blocks, key=lambda value: value[0]))


def _block_signature(period: str, half: str, events: Sequence[SignalEvent]) -> str:
    legs = ",".join(
        f"{event.instrument}@{event.signal_timestamp.astimezone(UTC).hour:02d}@{event.direction:+d}"
        for event in events
    )
    return f"{period}|{half}|{legs}"


def _rank_digest(seed: int, signature: str, placebo_day: datetime) -> str:
    payload = f"{seed}|{signature}|{placebo_day.date().isoformat()}".encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def form_randomized_timing_placebo_schedule(
    rows: Iterable[Mapping[str, object] | Bar],
    candidate_schedule: Sequence[SignalEvent],
    *,
    contract: Mapping[str, Any],
) -> tuple[SignalEvent, ...]:
    """Form the one frozen timing-placebo schedule without reading forward P&L."""

    _validate_contract(contract)
    windows = contract["frozen_windows"]
    eligibility = contract["candidate_eligibility"]
    protected = windows["protected_oos_start_utc"]
    bars = normalize_development_rows(rows, protected_oos_start=protected)
    by_instrument_ts: dict[str, dict[datetime, Bar]] = {}
    for bar in bars:
        by_instrument_ts.setdefault(bar.instrument, {})[bar.timestamp] = bar
    daily_returns = _complete_daily_returns(by_instrument_ts)

    blocks = _source_blocks(tuple(candidate_schedule), windows)
    candidate_days = {day for day, _, _, _ in blocks}
    all_days = sorted({_day_start(bar.timestamp) for bar in bars})
    used_placebo_days: set[datetime] = set()
    seed = int(contract["formation"]["seed_uint64"])
    placebo: list[SignalEvent] = []

    for _source_day, period, half, events in blocks:
        signature = _block_signature(period, half, events)
        eligible_days: list[datetime] = []
        for day in all_days:
            if day in candidate_days or day in used_placebo_days:
                continue
            day_period_half = _period_and_half(day, windows)
            if day_period_half != (period, half):
                continue
            if all(
                _eligible_timestamp(
                    instrument=event.instrument,
                    ts=day + event.signal_timestamp.astimezone(UTC).hour * HOUR,
                    by_instrument_ts=by_instrument_ts,
                    daily_returns=daily_returns,
                    windows=windows,
                    reference_days=int(eligibility["reference_days"]),
                    latest_signal_hour=int(eligibility["latest_signal_hour_utc"]),
                )
                for event in events
            ):
                eligible_days.append(day)

        if not eligible_days:
            raise RandomizedTimingPlaceboInconclusiveError(
                "DATA/PIT_INCONCLUSIVE_RANDOMIZED_PLACEBO_POOL: "
                f"no unused eligible UTC day for source block {signature}"
            )
        selected_day = min(
            eligible_days,
            key=lambda day: (_rank_digest(seed, signature, day), day),
        )
        used_placebo_days.add(selected_day)

        for source in events:
            hour = source.signal_timestamp.astimezone(UTC).hour
            signal_ts = selected_day + hour * HOUR
            placebo.append(
                SignalEvent(
                    instrument=source.instrument,
                    period=source.period,
                    signal_timestamp=signal_ts,
                    entry_timestamp=signal_ts + HOUR,
                    exit_timestamp=selected_day + DAY,
                    direction=source.direction,
                    baseline_direction=None,
                    intraday_return=0.0,
                    reference_mean=0.0,
                    reference_std=0.0,
                )
            )

    ordered = tuple(sorted(placebo, key=lambda e: (e.signal_timestamp, e.instrument)))
    if len(ordered) != len(candidate_schedule):
        raise RuntimeError("randomized placebo changed candidate event count")
    if len({_day_start(e.signal_timestamp) for e in ordered}) != len(blocks):
        raise RuntimeError("randomized placebo changed independent UTC-day block count")
    return ordered


def evaluate_randomized_timing_placebo(
    rows: Iterable[Mapping[str, object] | Bar],
    candidate_schedule: Sequence[SignalEvent],
    *,
    execution: Mapping[str, Any],
    contract: Mapping[str, Any],
) -> dict[str, Any]:
    """Form then score the single frozen randomized timing placebo."""

    materialized_rows = tuple(rows)
    placebo_schedule = form_randomized_timing_placebo_schedule(
        materialized_rows,
        tuple(candidate_schedule),
        contract=contract,
    )
    scored = score_schedule(
        materialized_rows,
        placebo_schedule,
        protected_oos_start=contract["frozen_windows"]["protected_oos_start_utc"],
        base_cost_bps=float(execution["screen"]["base_total_cost_bps"]),
        stress_multiplier=float(execution["screen"]["stress_multiplier"]),
        direction_source="candidate",
        entry_delay_bars=0,
    )
    if len(scored) != len(placebo_schedule):
        raise RuntimeError("randomized placebo scoring changed frozen schedule membership")
    periods = split_by_period(scored)
    return {
        "arm_id": "randomized_timing_placebo",
        "contract_id": contract["contract_id"],
        "scheduled_candidate_windows": len(candidate_schedule),
        "scored_windows": len(scored),
        "independent_candidate_utc_signal_days": len(
            {_day_start(event.signal_timestamp) for event in candidate_schedule}
        ),
        "independent_placebo_utc_signal_days": len(
            {_day_start(event.signal_timestamp) for event in placebo_schedule}
        ),
        "train": _portfolio_summary(periods["train"], dict(execution)),
        "validation": _portfolio_summary(periods["validation"], dict(execution)),
        "placebo_schedule": [
            {
                "instrument": event.instrument,
                "period": event.period,
                "signal_timestamp": event.signal_timestamp.isoformat(),
                "entry_timestamp": event.entry_timestamp.isoformat(),
                "exit_timestamp": event.exit_timestamp.isoformat(),
                "direction": event.direction,
            }
            for event in placebo_schedule
        ],
        "protected_oos_opened": False,
        "genuine_forward_opened": False,
        "promotion_authority": False,
        "broker_connected": False,
        "trade_authority": False,
    }
