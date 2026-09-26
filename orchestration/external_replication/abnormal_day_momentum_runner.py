from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
from math import isfinite
from statistics import mean, stdev
from typing import Iterable, Mapping, Sequence

UTC = timezone.utc
HOUR = timedelta(hours=1)
DAY = timedelta(days=1)


@dataclass(frozen=True)
class Bar:
    instrument: str
    timestamp: datetime
    open: float
    close: float


@dataclass(frozen=True)
class SignalEvent:
    instrument: str
    period: str
    signal_timestamp: datetime
    entry_timestamp: datetime
    exit_timestamp: datetime
    direction: int
    baseline_direction: int | None
    intraday_return: float
    reference_mean: float
    reference_std: float


@dataclass(frozen=True)
class ScoredEvent:
    signal: SignalEvent
    entry_price: float
    exit_price: float
    gross_return: float
    net_return: float
    stress_3x_net_return: float


@dataclass(frozen=True)
class ScheduleExecutionIssue:
    instrument: str
    period: str
    signal_timestamp: datetime
    required_timestamp: datetime
    reason: str
    entry_delay_bars: int


class DataPitInconclusiveError(RuntimeError):
    """Fail closed when a frozen event cannot be scored from required PIT bars."""

    def __init__(self, issues: Sequence[ScheduleExecutionIssue]):
        self.issues = tuple(issues)
        details = "; ".join(
            f"{issue.instrument} {issue.signal_timestamp.isoformat()} "
            f"{issue.reason}@{issue.required_timestamp.isoformat()}"
            for issue in self.issues
        )
        super().__init__(
            "DATA/PIT_INCONCLUSIVE: frozen schedule is missing required PIT bars: "
            + details
        )


def _parse_utc_hour(value: str | datetime) -> datetime:
    if isinstance(value, datetime):
        dt = value
    else:
        dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware UTC")
    dt = dt.astimezone(UTC)
    if dt.minute or dt.second or dt.microsecond:
        raise ValueError("timestamp must lie on the UTC hourly grid")
    return dt


def _coerce_bar(row: Mapping[str, object] | Bar) -> Bar:
    if isinstance(row, Bar):
        bar = row
    else:
        try:
            bar = Bar(
                instrument=str(row["instrument"]),
                timestamp=_parse_utc_hour(row["timestamp"]),
                open=float(row["open"]),
                close=float(row["close"]),
            )
        except KeyError as exc:
            raise ValueError(f"missing required bar field: {exc.args[0]}") from exc
    if not bar.instrument:
        raise ValueError("instrument must be non-empty")
    if bar.timestamp.tzinfo is None:
        raise ValueError("timestamp must be timezone-aware UTC")
    ts = _parse_utc_hour(bar.timestamp)
    if not all(isfinite(x) and x > 0 for x in (bar.open, bar.close)):
        raise ValueError("open/close must be finite positive numbers")
    return Bar(bar.instrument, ts, float(bar.open), float(bar.close))


def normalize_development_rows(
    rows: Iterable[Mapping[str, object] | Bar],
    *,
    protected_oos_start: str | datetime,
) -> tuple[Bar, ...]:
    """Validate selection-only rows and reject protected evidence before any scoring."""
    protected = _parse_utc_hour(protected_oos_start)
    bars = sorted((_coerce_bar(row) for row in rows), key=lambda x: (x.instrument, x.timestamp))
    seen: set[tuple[str, datetime]] = set()
    for bar in bars:
        key = (bar.instrument, bar.timestamp)
        if key in seen:
            raise ValueError(f"duplicate instrument/timestamp: {bar.instrument} {bar.timestamp.isoformat()}")
        seen.add(key)
        if bar.timestamp >= protected:
            raise ValueError("protected OOS row supplied to development-only runner")
    return tuple(bars)


def _period_for_timestamp(
    ts: datetime,
    *,
    train_start: datetime,
    train_end: datetime,
    validation_start: datetime,
    validation_end: datetime,
) -> str | None:
    if train_start <= ts <= train_end:
        return "train"
    if validation_start <= ts <= validation_end:
        return "validation"
    return None


def _index_by_instrument(
    bars: Sequence[Bar],
) -> tuple[dict[str, dict[datetime, Bar]], dict[str, dict[datetime, list[Bar]]]]:
    by_ts: dict[str, dict[datetime, Bar]] = {}
    by_day: dict[str, dict[datetime, list[Bar]]] = {}
    for bar in bars:
        by_ts.setdefault(bar.instrument, {})[bar.timestamp] = bar
        day = bar.timestamp.replace(hour=0)
        by_day.setdefault(bar.instrument, {}).setdefault(day, []).append(bar)
    for instrument_days in by_day.values():
        for day_bars in instrument_days.values():
            day_bars.sort(key=lambda x: x.timestamp)
    return by_ts, by_day


def _complete_daily_returns(days: Mapping[datetime, Sequence[Bar]]) -> dict[datetime, float]:
    returns: dict[datetime, float] = {}
    expected_hours = list(range(24))
    for day, day_bars in days.items():
        hours = [bar.timestamp.hour for bar in day_bars]
        if len(day_bars) != 24 or hours != expected_hours:
            continue
        returns[day] = day_bars[-1].close / day_bars[0].open - 1.0
    return returns


def build_signal_schedule(
    rows: Iterable[Mapping[str, object] | Bar],
    *,
    train_start: str | datetime,
    train_end: str | datetime,
    validation_start: str | datetime,
    validation_end: str | datetime,
    protected_oos_start: str | datetime,
    reference_days: int = 90,
    sigma_multiple: float = 1.5,
    latest_signal_hour_utc: int = 22,
) -> tuple[SignalEvent, ...]:
    """Form the frozen event schedule using only contemporaneous/past information.

    This function intentionally does not read entry/exit prices. Forward-return scoring is
    separated into ``score_schedule`` so event formation cannot condition on future P&L.
    """
    if reference_days < 2:
        raise ValueError("reference_days must be >= 2")
    if not isfinite(sigma_multiple) or sigma_multiple <= 0:
        raise ValueError("sigma_multiple must be finite and > 0")
    if not 0 <= latest_signal_hour_utc <= 22:
        raise ValueError("latest_signal_hour_utc must be between 0 and 22")

    train_start_dt = _parse_utc_hour(train_start)
    train_end_dt = _parse_utc_hour(train_end)
    validation_start_dt = _parse_utc_hour(validation_start)
    validation_end_dt = _parse_utc_hour(validation_end)
    protected_dt = _parse_utc_hour(protected_oos_start)
    if not (
        train_start_dt <= train_end_dt
        < validation_start_dt
        <= validation_end_dt
        < protected_dt
    ):
        raise ValueError("train/validation/protected chronology must be strict and non-overlapping")

    bars = normalize_development_rows(rows, protected_oos_start=protected_dt)
    by_ts, by_day = _index_by_instrument(bars)
    events: list[SignalEvent] = []

    for instrument, days in sorted(by_day.items()):
        complete_returns = _complete_daily_returns(days)
        complete_days = sorted(complete_returns)
        ts_index = by_ts[instrument]

        for day in sorted(days):
            day_bars = days[day]
            past_complete = [d for d in complete_days if d < day]
            if len(past_complete) < reference_days:
                continue
            reference_dates = past_complete[-reference_days:]
            reference_values = [complete_returns[d] for d in reference_dates]
            ref_mean = mean(reference_values)
            ref_std = stdev(reference_values)
            if not isfinite(ref_std) or ref_std <= 0:
                continue

            open_bar = ts_index.get(day)
            if open_bar is None:
                continue
            continuous_from_midnight = True
            for hour in range(24):
                ts = day + hour * HOUR
                bar = ts_index.get(ts)
                if bar is None:
                    continuous_from_midnight = False
                    continue
                if not continuous_from_midnight:
                    continue
                if hour > latest_signal_hour_utc:
                    break

                period = _period_for_timestamp(
                    ts,
                    train_start=train_start_dt,
                    train_end=train_end_dt,
                    validation_start=validation_start_dt,
                    validation_end=validation_end_dt,
                )
                if period is None:
                    continue

                intraday = bar.close / open_bar.open - 1.0
                upper = ref_mean + sigma_multiple * ref_std
                lower = ref_mean - sigma_multiple * ref_std
                direction = 1 if intraday > upper else -1 if intraday < lower else 0
                if direction == 0:
                    continue

                entry_ts = ts + HOUR
                exit_ts = day + DAY
                if entry_ts >= protected_dt or exit_ts >= protected_dt:
                    break
                # Keep every scored return entirely inside its declared chronological
                # period. In particular, the final training day's midnight exit may
                # not consume the first validation timestamp.
                if period == "train" and exit_ts > train_end_dt:
                    break
                if period == "validation" and exit_ts > validation_end_dt:
                    break

                # The frozen #517 simple-trend baseline is defined on the exact
                # candidate window using the immediately preceding completed hourly
                # close. Resolve t-1h from the instrument index so 00:00 UTC signals
                # correctly use the prior UTC day's 23:00 close. Missing t-1h is not
                # the same thing as a true zero return and remains explicit for the
                # baseline scorer to fail closed.
                prior_bar = ts_index.get(ts - HOUR)
                baseline_direction: int | None = None
                if prior_bar is not None:
                    one_hour = bar.close / prior_bar.close - 1.0
                    baseline_direction = 1 if one_hour > 0 else -1 if one_hour < 0 else 0

                events.append(
                    SignalEvent(
                        instrument=instrument,
                        period=period,
                        signal_timestamp=ts,
                        entry_timestamp=entry_ts,
                        exit_timestamp=exit_ts,
                        direction=direction,
                        baseline_direction=baseline_direction,
                        intraday_return=intraday,
                        reference_mean=ref_mean,
                        reference_std=ref_std,
                    )
                )
                break  # first qualifying completed hourly bar per instrument/day only

    return tuple(sorted(events, key=lambda e: (e.signal_timestamp, e.instrument)))


def _execution_issues_from_index(
    by_ts: Mapping[str, Mapping[datetime, Bar]],
    schedule: Sequence[SignalEvent],
    *,
    entry_delay_bars: int,
) -> tuple[ScheduleExecutionIssue, ...]:
    issues: list[ScheduleExecutionIssue] = []
    for signal in schedule:
        entry_ts = signal.entry_timestamp + entry_delay_bars * HOUR
        if entry_ts >= signal.exit_timestamp:
            # Structural no-hold interval is a frozen, price-independent exclusion for
            # the delay arm. It is distinct from missing market data.
            continue
        instrument_index = by_ts.get(signal.instrument, {})
        if instrument_index.get(entry_ts) is None:
            issues.append(
                ScheduleExecutionIssue(
                    instrument=signal.instrument,
                    period=signal.period,
                    signal_timestamp=signal.signal_timestamp,
                    required_timestamp=entry_ts,
                    reason="MISSING_REQUIRED_ENTRY_BAR",
                    entry_delay_bars=entry_delay_bars,
                )
            )
        if instrument_index.get(signal.exit_timestamp) is None:
            issues.append(
                ScheduleExecutionIssue(
                    instrument=signal.instrument,
                    period=signal.period,
                    signal_timestamp=signal.signal_timestamp,
                    required_timestamp=signal.exit_timestamp,
                    reason="MISSING_REQUIRED_EXIT_BAR",
                    entry_delay_bars=entry_delay_bars,
                )
            )
    return tuple(issues)


def schedule_execution_issues(
    rows: Iterable[Mapping[str, object] | Bar],
    schedule: Sequence[SignalEvent],
    *,
    protected_oos_start: str | datetime,
    entry_delay_bars: int = 0,
) -> tuple[ScheduleExecutionIssue, ...]:
    """Return deterministic future-bar availability defects without reading returns."""
    if entry_delay_bars < 0:
        raise ValueError("entry_delay_bars must be non-negative")
    bars = normalize_development_rows(rows, protected_oos_start=protected_oos_start)
    by_ts, _ = _index_by_instrument(bars)
    return _execution_issues_from_index(by_ts, schedule, entry_delay_bars=entry_delay_bars)


def score_schedule(
    rows: Iterable[Mapping[str, object] | Bar],
    schedule: Sequence[SignalEvent],
    *,
    protected_oos_start: str | datetime,
    base_cost_bps: float = 24.0,
    stress_multiplier: float = 3.0,
    direction_source: str = "candidate",
    entry_delay_bars: int = 0,
) -> tuple[ScoredEvent, ...]:
    """Score a preformed schedule without altering event membership from outcomes.

    Any frozen event missing a required PIT input is a DATA/PIT_INCONCLUSIVE
    screen, never an event that may be silently removed to improve evidence.
    A genuine zero prior-hour baseline return is different: it preserves the exact
    candidate window as a zero-position, zero-economic baseline observation.
    """
    if not isfinite(base_cost_bps) or base_cost_bps < 0:
        raise ValueError("base_cost_bps must be finite and non-negative")
    if not isfinite(stress_multiplier) or stress_multiplier < 1:
        raise ValueError("stress_multiplier must be finite and >= 1")
    if entry_delay_bars < 0:
        raise ValueError("entry_delay_bars must be non-negative")
    if direction_source not in {"candidate", "baseline", "sign_flip"}:
        raise ValueError("unknown direction_source")

    bars = normalize_development_rows(rows, protected_oos_start=protected_oos_start)
    by_ts, _ = _index_by_instrument(bars)
    issues = list(_execution_issues_from_index(by_ts, schedule, entry_delay_bars=entry_delay_bars))
    if direction_source == "baseline":
        for signal in schedule:
            if signal.baseline_direction is None:
                issues.append(
                    ScheduleExecutionIssue(
                        instrument=signal.instrument,
                        period=signal.period,
                        signal_timestamp=signal.signal_timestamp,
                        required_timestamp=signal.signal_timestamp - HOUR,
                        reason="MISSING_REQUIRED_BASELINE_BAR",
                        entry_delay_bars=entry_delay_bars,
                    )
                )
    if issues:
        raise DataPitInconclusiveError(issues)

    cost = base_cost_bps / 10_000.0
    stress_cost = base_cost_bps * stress_multiplier / 10_000.0
    scored: list[ScoredEvent] = []

    for signal in schedule:
        direction = (
            signal.direction
            if direction_source == "candidate"
            else signal.baseline_direction
            if direction_source == "baseline"
            else -signal.direction
        )
        entry_ts = signal.entry_timestamp + entry_delay_bars * HOUR
        if entry_ts >= signal.exit_timestamp:
            continue
        instrument_index = by_ts.get(signal.instrument, {})
        # Required PIT bars were validated above for the complete frozen schedule.
        entry = instrument_index[entry_ts]
        exit_bar = instrument_index[signal.exit_timestamp]
        if direction is None:
            raise RuntimeError("baseline PIT input was not validated before scoring")
        if direction == 0:
            if direction_source == "baseline":
                scored.append(
                    ScoredEvent(
                        signal=signal,
                        entry_price=entry.open,
                        exit_price=exit_bar.open,
                        gross_return=0.0,
                        net_return=0.0,
                        stress_3x_net_return=0.0,
                    )
                )
            continue
        raw_price_return = exit_bar.open / entry.open - 1.0
        gross = direction * raw_price_return
        scored.append(
            ScoredEvent(
                signal=signal,
                entry_price=entry.open,
                exit_price=exit_bar.open,
                gross_return=gross,
                net_return=gross - cost,
                stress_3x_net_return=gross - stress_cost,
            )
        )
    return tuple(scored)


def independent_utc_signal_days(scored: Sequence[ScoredEvent]) -> int:
    """Pooled BTC/ETH/SOL independence unit: unique UTC signal day."""
    return len({event.signal.signal_timestamp.astimezone(UTC).date() for event in scored})


def summarize(scored: Sequence[ScoredEvent]) -> dict[str, float | int | None]:
    net = [event.net_return for event in scored]
    stress = [event.stress_3x_net_return for event in scored]
    gains = [value for value in net if value > 0]
    losses = [-value for value in net if value < 0]
    total = sum(net)
    profit_factor = None
    if losses:
        profit_factor = sum(gains) / sum(losses)
    elif gains:
        profit_factor = float("inf")
    largest_winner = max(gains, default=0.0)
    worst = min(net, default=0.0)
    return {
        "n": len(net),
        "independent_utc_signal_days": independent_utc_signal_days(scored),
        "mean_net_return": mean(net) if net else None,
        "total_net_return": total,
        "profit_factor": profit_factor,
        "total_3x_cost_return": sum(stress),
        "largest_winner_return": largest_winner,
        "leave_largest_winner_out_total": total - largest_winner,
        "worst_event_return": worst,
        "repeat_worst_event_stressed_total": total + worst,
    }


def split_by_period(scored: Sequence[ScoredEvent]) -> dict[str, tuple[ScoredEvent, ...]]:
    return {
        "train": tuple(event for event in scored if event.signal.period == "train"),
        "validation": tuple(event for event in scored if event.signal.period == "validation"),
    }


def schedule_as_dicts(schedule: Sequence[SignalEvent]) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for event in schedule:
        row = asdict(event)
        for key in ("signal_timestamp", "entry_timestamp", "exit_timestamp"):
            row[key] = row[key].astimezone(UTC).isoformat().replace("+00:00", "Z")
        rows.append(row)
    return rows
