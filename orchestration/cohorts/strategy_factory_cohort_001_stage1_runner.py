"""Deterministic, outcome-blind Cohort-001 Stage-1 execution engine.

This module intentionally contains no repository-dataset loader and no CLI that can
open real Cohort outcomes.  It turns caller-supplied completed hourly bars into the
six frozen Stage-1 candidate trade streams and evaluates the already-frozen economic
gates.  A separately reviewed adapter may feed the certified development-only view
after the parent admission/binding gates clear.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
import math
from statistics import fmean
from typing import Iterable, Mapping, Sequence

UTC = timezone.utc

TRAIN_START = datetime(2025, 5, 7, 5, tzinfo=UTC)
TRAIN_END = datetime(2026, 4, 30, 23, tzinfo=UTC)
VALIDATION_START = datetime(2026, 5, 1, 0, tzinfo=UTC)
VALIDATION_END = datetime(2026, 8, 31, 23, tzinfo=UTC)
PROTECTED_START = datetime(2026, 9, 1, 0, tzinfo=UTC)
VALIDATION_HALVES = (
    (datetime(2026, 5, 1, 0, tzinfo=UTC), datetime(2026, 6, 30, 23, tzinfo=UTC)),
    (datetime(2026, 7, 1, 0, tzinfo=UTC), datetime(2026, 8, 31, 23, tzinfo=UTC)),
)
COST_BPS = (24.0, 48.0, 72.0)
CANDIDATE_IDS = (
    "DISC-RESIDUAL-REV-001-v1",
    "DISC-SIGNED-VOLUME-DRIFT-001-v1",
    "DISC-LOWVOL-DRIFT-REV-001-v1",
    "DISC-WEEKEND-NORMALIZE-001-v1",
    "DISC-MODERATEVOL-AUTOCORR-001-v1",
    "DISC-RANGE-AUCTION-REV-001-v1",
)
EXPECTED_INSTRUMENTS = (
    "BTC-USDT-SWAP",
    "ETH-USDT-SWAP",
    "SOL-USDT-SWAP",
)


@dataclass(frozen=True)
class Bar:
    timestamp: datetime
    open: float
    high: float
    low: float
    close: float
    quote_volume: float

    def __post_init__(self) -> None:
        ts = self.timestamp
        if ts.tzinfo is None or ts.utcoffset() is None:
            raise ValueError("bar timestamp must be timezone-aware")
        ts = ts.astimezone(UTC)
        if ts.minute or ts.second or ts.microsecond:
            raise ValueError("bar timestamp must lie on the UTC hourly grid")
        object.__setattr__(self, "timestamp", ts)
        values = (self.open, self.high, self.low, self.close, self.quote_volume)
        if any(not math.isfinite(float(v)) for v in values):
            raise ValueError("bar market values must be finite")
        if min(self.open, self.high, self.low, self.close) <= 0:
            raise ValueError("bar prices must be positive")
        if self.quote_volume < 0:
            raise ValueError("quote volume must be non-negative")
        if self.high < max(self.open, self.close, self.low):
            raise ValueError("high is inconsistent with OHLC")
        if self.low > min(self.open, self.close, self.high):
            raise ValueError("low is inconsistent with OHLC")


@dataclass(frozen=True)
class Trade:
    candidate_id: str
    instrument_key: str
    signal_time: datetime
    entry_time: datetime
    exit_time: datetime
    gross_return: float
    gross_notional: float = 1.0
    exit_reasons: tuple[str, ...] = ("fixed_hold",)

    def __post_init__(self) -> None:
        if self.candidate_id not in CANDIDATE_IDS:
            raise ValueError("unexpected candidate id")
        if not (self.signal_time < self.entry_time < self.exit_time):
            raise ValueError("trade chronology must be signal < entry < exit")
        if self.exit_time >= PROTECTED_START:
            raise ValueError("trade may not touch protected evidence")
        if not math.isfinite(self.gross_return):
            raise ValueError("gross return must be finite")
        if not math.isfinite(self.gross_notional) or self.gross_notional <= 0:
            raise ValueError("gross notional must be finite and positive")

    def net_return(self, cost_bps: float) -> float:
        return self.gross_return - float(cost_bps) / 10_000.0


@dataclass(frozen=True)
class IndependentEvent:
    entry_time: datetime
    exit_time: datetime
    trades: tuple[Trade, ...]

    def return_at_cost(self, cost_bps: float) -> float:
        return sum((1.0 / 3.0) * trade.net_return(cost_bps) for trade in self.trades)


@dataclass(frozen=True)
class PartitionSummary:
    independent_events: int
    mean_24bps: float | None
    mean_48bps: float | None
    mean_72bps: float | None
    profit_factor_24bps: float | None
    leave_best_mean_24bps: float | None
    worst_loss_abs_24bps: float | None
    positive_pool_24bps: float
    catastrophic_tail_pass_24bps: bool


@dataclass(frozen=True)
class Stage1Result:
    candidate_id: str
    classification: str
    raw_trade_count: int
    training: PartitionSummary
    validation: PartitionSummary
    validation_half_means_24bps: tuple[float | None, float | None]
    gate_results: Mapping[str, bool]
    evidence_authority: str = field(default="TEST_ONLY_UNTRUSTED", init=False)
    canonical_stage1_evidence: bool = field(default=False, init=False)
    protected_oos_opened: bool = False
    genuine_forward_opened: bool = False
    broker_connected: bool = False
    trade_authority: bool = False
    promotion_authority: bool = False


def type7_quantile(values: Sequence[float], p: float) -> float:
    if not 0.0 <= p <= 1.0:
        raise ValueError("quantile probability must be in [0,1]")
    clean = [float(v) for v in values]
    if not clean or any(not math.isfinite(v) for v in clean):
        raise ValueError("quantile requires non-empty finite values")
    clean.sort()
    h = (len(clean) - 1) * p
    lo = math.floor(h)
    hi = math.ceil(h)
    if lo == hi:
        return clean[lo]
    frac = h - lo
    return clean[lo] * (1.0 - frac) + clean[hi] * frac


def population_std(values: Sequence[float]) -> float:
    clean = [float(v) for v in values]
    if not clean or any(not math.isfinite(v) for v in clean):
        raise ValueError("population std requires non-empty finite values")
    mean = fmean(clean)
    return math.sqrt(fmean([(value - mean) ** 2 for value in clean]))


def _sign(value: float) -> int:
    return 1 if value > 0 else -1 if value < 0 else 0


def _true_range(bars: Sequence[Bar], i: int) -> float | None:
    if i <= 0:
        return None
    bar = bars[i]
    prev_close = bars[i - 1].close
    return max(bar.high - bar.low, abs(bar.high - prev_close), abs(bar.low - prev_close))


def _simple_return(bars: Sequence[Bar], end: int, horizon: int) -> float | None:
    if end - horizon < 0:
        return None
    return bars[end].close / bars[end - horizon].close - 1.0


def _hourly_returns(bars: Sequence[Bar]) -> list[float | None]:
    result: list[float | None] = [None]
    result.extend(bars[i].close / bars[i - 1].close - 1.0 for i in range(1, len(bars)))
    return result


def _covariance_slope_and_corr(xs: Sequence[float], ys: Sequence[float]) -> tuple[float, float] | None:
    if len(xs) != len(ys) or not xs:
        raise ValueError("aligned non-empty windows required")
    mx, my = fmean(xs), fmean(ys)
    dx = [x - mx for x in xs]
    dy = [y - my for y in ys]
    varx = fmean([x * x for x in dx])
    vary = fmean([y * y for y in dy])
    if varx <= 0.0 or vary <= 0.0:
        return None
    cov = fmean([x * y for x, y in zip(dx, dy)])
    beta = cov / varx
    corr = cov / math.sqrt(varx * vary)
    return beta, corr


def validate_histories(histories: Mapping[str, Sequence[Bar]]) -> dict[str, tuple[Bar, ...]]:
    if set(histories) != set(EXPECTED_INSTRUMENTS):
        raise ValueError("histories must contain exactly the frozen BTC/ETH/SOL instruments")
    normalized = {key: tuple(histories[key]) for key in EXPECTED_INSTRUMENTS}
    lengths = {len(v) for v in normalized.values()}
    if len(lengths) != 1 or not lengths or next(iter(lengths)) < 2:
        raise ValueError("histories must be non-empty and exactly aligned")
    reference_times = tuple(bar.timestamp for bar in normalized[EXPECTED_INSTRUMENTS[0]])
    if any(ts >= PROTECTED_START for ts in reference_times):
        raise ValueError("caller-supplied histories may not contain protected rows")
    for instrument, bars in normalized.items():
        times = tuple(bar.timestamp for bar in bars)
        if times != reference_times:
            raise ValueError(f"{instrument} timestamps are not exactly aligned")
        if any(b.timestamp - a.timestamp != timedelta(hours=1) for a, b in zip(bars, bars[1:])):
            raise ValueError(f"{instrument} history is not continuous hourly data")
    return normalized


def _fixed_hold_trade(
    candidate_id: str,
    instrument: str,
    bars: Sequence[Bar],
    i: int,
    direction: int,
    hold_hours: int,
) -> Trade | None:
    entry_i = i + 1
    exit_i = entry_i + hold_hours
    if direction == 0 or exit_i >= len(bars):
        return None
    signal_time, entry_time, exit_time = bars[i].timestamp, bars[entry_i].timestamp, bars[exit_i].timestamp
    if exit_time >= PROTECTED_START:
        return None
    gross = direction * (bars[exit_i].open / bars[entry_i].open - 1.0)
    return Trade(candidate_id, instrument, signal_time, entry_time, exit_time, gross)


def _append_nonoverlap(trades: list[Trade], trade: Trade | None, busy_until: dict[str, datetime]) -> None:
    if trade is None:
        return
    prior_exit = busy_until.get(trade.instrument_key)
    if prior_exit is not None and trade.entry_time < prior_exit:
        return
    trades.append(trade)
    busy_until[trade.instrument_key] = trade.exit_time


def residual_reversion_trades(histories: Mapping[str, Sequence[Bar]]) -> list[Trade]:
    h = validate_histories(histories)
    btc = h["BTC-USDT-SWAP"]
    btc_r = _hourly_returns(btc)
    trades: list[Trade] = []
    busy: dict[str, datetime] = {}
    for follower_name in ("ETH-USDT-SWAP", "SOL-USDT-SWAP"):
        follower = h[follower_name]
        follower_r = _hourly_returns(follower)
        residuals: list[float | None] = [None] * len(btc)
        betas: list[float | None] = [None] * len(btc)
        correlations: list[float | None] = [None] * len(btc)
        for j in range(len(btc)):
            if j < 336 or j < 6:
                continue
            x = [float(v) for v in btc_r[j - 335 : j + 1] if v is not None]
            y = [float(v) for v in follower_r[j - 335 : j + 1] if v is not None]
            if len(x) != 336 or len(y) != 336:
                continue
            stats = _covariance_slope_and_corr(x, y)
            if stats is None:
                continue
            beta, corr = stats
            betas[j], correlations[j] = beta, corr
            residuals[j] = (follower[j].close / follower[j - 6].close - 1.0) - beta * (
                btc[j].close / btc[j - 6].close - 1.0
            )
        for i in range(len(btc)):
            current = residuals[i]
            beta = betas[i]
            corr = correlations[i]
            if current is None or beta is None or corr is None or corr < 0.60 or i < 720:
                continue
            prior = residuals[i - 720 : i]
            if any(value is None for value in prior):
                continue
            ref = [float(value) for value in prior if value is not None]
            std = population_std(ref)
            if std <= 0.0:
                continue
            z = (current - fmean(ref)) / std
            if abs(z) < 2.0:
                continue
            entry_i, exit_i = i + 1, i + 7
            if exit_i >= len(btc):
                continue
            direction = -_sign(current)
            follower_return = follower[exit_i].open / follower[entry_i].open - 1.0
            btc_return = btc[exit_i].open / btc[entry_i].open - 1.0
            signed_follower = direction
            signed_btc = -direction * beta
            gross_notional = 1.0 + abs(beta)
            gross_return = (signed_follower * follower_return + signed_btc * btc_return) / gross_notional
            trade = Trade(
                "DISC-RESIDUAL-REV-001-v1",
                follower_name,
                btc[i].timestamp,
                btc[entry_i].timestamp,
                btc[exit_i].timestamp,
                gross_return,
                gross_notional,
            )
            _append_nonoverlap(trades, trade, busy)
    return sorted(trades, key=lambda t: (t.entry_time, t.instrument_key))


def signed_volume_drift_trades(histories: Mapping[str, Sequence[Bar]]) -> list[Trade]:
    h = validate_histories(histories)
    trades: list[Trade] = []
    busy: dict[str, datetime] = {}
    for instrument, bars in h.items():
        signed: list[float | None] = [None] * len(bars)
        tr = [_true_range(bars, i) for i in range(len(bars))]
        aggregates: list[float | None] = [None] * len(bars)
        for j in range(len(bars)):
            if j < 720:
                continue
            med = type7_quantile([b.quote_volume for b in bars[j - 720 : j]], 0.5)
            if med <= 0.0:
                continue
            signed[j] = _sign(bars[j].close - bars[j].open) * bars[j].quote_volume / med
            if j >= 3 and all(signed[k] is not None for k in range(j - 3, j + 1)):
                aggregates[j] = sum(float(signed[k]) for k in range(j - 3, j + 1))
        for i in range(len(bars)):
            agg = aggregates[i]
            if agg is None or agg == 0.0 or i < 720 or tr[i] is None:
                continue
            prior_aggs = aggregates[i - 720 : i]
            prior_tr = tr[i - 720 : i]
            if any(v is None for v in prior_aggs) or any(v is None for v in prior_tr):
                continue
            if abs(agg) < type7_quantile([abs(float(v)) for v in prior_aggs if v is not None], 0.90):
                continue
            direction = _sign(agg)
            body_signs = [_sign(bars[k].close - bars[k].open) for k in range(i - 3, i + 1)]
            if sum(sign == direction for sign in body_signs) < 3:
                continue
            width = bars[i].high - bars[i].low
            if width <= 0.0:
                continue
            close_location = (bars[i].close - bars[i].low) / width
            if direction > 0 and close_location < 0.80:
                continue
            if direction < 0 and close_location > 0.20:
                continue
            if float(tr[i]) > type7_quantile([float(v) for v in prior_tr if v is not None], 0.90):
                continue
            _append_nonoverlap(
                trades,
                _fixed_hold_trade("DISC-SIGNED-VOLUME-DRIFT-001-v1", instrument, bars, i, direction, 3),
                busy,
            )
    return sorted(trades, key=lambda t: (t.entry_time, t.instrument_key))


def lowvol_drift_reversion_trades(histories: Mapping[str, Sequence[Bar]]) -> list[Trade]:
    h = validate_histories(histories)
    trades: list[Trade] = []
    busy: dict[str, datetime] = {}
    for instrument, bars in h.items():
        moves = [_simple_return(bars, i, 8) for i in range(len(bars))]
        tr = [_true_range(bars, i) for i in range(len(bars))]
        for i in range(len(bars)):
            move = moves[i]
            if move is None or move == 0.0 or i < 720 or i < 7:
                continue
            prior_moves = moves[i - 720 : i]
            prior_tr = tr[i - 720 : i]
            if any(v is None for v in prior_moves) or any(v is None for v in prior_tr):
                continue
            if abs(move) < type7_quantile([abs(float(v)) for v in prior_moves if v is not None], 0.80):
                continue
            qv_mean = fmean([bars[k].quote_volume for k in range(i - 7, i + 1)])
            qv_median = type7_quantile([b.quote_volume for b in bars[i - 720 : i]], 0.5)
            if qv_mean > 0.60 * qv_median:
                continue
            recent_tr = [tr[k] for k in range(i - 7, i + 1)]
            if any(v is None for v in recent_tr):
                continue
            if max(float(v) for v in recent_tr if v is not None) >= type7_quantile(
                [float(v) for v in prior_tr if v is not None], 0.70
            ):
                continue
            _append_nonoverlap(
                trades,
                _fixed_hold_trade("DISC-LOWVOL-DRIFT-REV-001-v1", instrument, bars, i, -_sign(move), 6),
                busy,
            )
    return sorted(trades, key=lambda t: (t.entry_time, t.instrument_key))


def weekend_normalization_trades(histories: Mapping[str, Sequence[Bar]]) -> list[Trade]:
    h = validate_histories(histories)
    trades: list[Trade] = []
    for instrument, bars in h.items():
        by_time = {bar.timestamp: idx for idx, bar in enumerate(bars)}
        for i, sunday in enumerate(bars):
            ts = sunday.timestamp
            if ts.weekday() != 6 or ts.hour != 23:
                continue
            friday_ts = ts - timedelta(days=2, hours=1)
            friday_i = by_time.get(friday_ts)
            monday0_i = by_time.get(ts + timedelta(hours=1))
            monday12_i = by_time.get(ts + timedelta(hours=13))
            if friday_i is None or monday0_i is None or monday12_i is None:
                continue
            weekend_return = sunday.close / bars[friday_i].close - 1.0
            if abs(weekend_return) < 0.0125:
                continue
            weekend_volumes = [bars[k].quote_volume for k in range(friday_i + 1, i + 1)]
            friday_date = friday_ts.date()
            prior_dates = []
            cursor = friday_date - timedelta(days=1)
            while len(prior_dates) < 20:
                if cursor.weekday() < 5:
                    prior_dates.append(cursor)
                cursor -= timedelta(days=1)
            prior_set = set(prior_dates)
            weekday_pool = [bar.quote_volume for bar in bars if bar.timestamp.date() in prior_set]
            if len(weekday_pool) != 20 * 24:
                continue
            if type7_quantile(weekend_volumes, 0.5) > 0.80 * type7_quantile(weekday_pool, 0.5):
                continue
            direction = -_sign(weekend_return)
            gross = direction * (bars[monday12_i].open / bars[monday0_i].open - 1.0)
            if bars[monday12_i].timestamp >= PROTECTED_START:
                continue
            trades.append(
                Trade(
                    "DISC-WEEKEND-NORMALIZE-001-v1",
                    instrument,
                    ts,
                    bars[monday0_i].timestamp,
                    bars[monday12_i].timestamp,
                    gross,
                )
            )
    return sorted(trades, key=lambda t: (t.entry_time, t.instrument_key))


def moderatevol_autocorr_trades(histories: Mapping[str, Sequence[Bar]]) -> list[Trade]:
    h = validate_histories(histories)
    trades: list[Trade] = []
    busy: dict[str, datetime] = {}
    for instrument, bars in h.items():
        hourly = _hourly_returns(bars)
        rv: list[float | None] = [None] * len(bars)
        for j in range(len(bars)):
            if j < 24:
                continue
            window = hourly[j - 23 : j + 1]
            if any(v is None for v in window):
                continue
            rv[j] = population_std([float(v) for v in window if v is not None])
        for i in range(len(bars)):
            if i < 2160 or i < 3 or rv[i] is None:
                continue
            last3 = hourly[i - 2 : i + 1]
            if any(v is None or v == 0.0 for v in last3):
                continue
            signs = {_sign(float(v)) for v in last3 if v is not None}
            if len(signs) != 1:
                continue
            direction = next(iter(signs))
            prior_rv = rv[i - 2160 : i]
            if any(v is None for v in prior_rv):
                continue
            rv_values = [float(v) for v in prior_rv if v is not None]
            current_rv = float(rv[i])
            if not (type7_quantile(rv_values, 0.35) <= current_rv <= type7_quantile(rv_values, 0.70)):
                continue
            qv_ref = [b.quote_volume for b in bars[i - 720 : i]]
            if len(qv_ref) != 720:
                continue
            if not (type7_quantile(qv_ref, 0.40) <= bars[i].quote_volume <= type7_quantile(qv_ref, 0.90)):
                continue
            _append_nonoverlap(
                trades,
                _fixed_hold_trade("DISC-MODERATEVOL-AUTOCORR-001-v1", instrument, bars, i, direction, 3),
                busy,
            )
    return sorted(trades, key=lambda t: (t.entry_time, t.instrument_key))


def range_auction_reversion_trades(histories: Mapping[str, Sequence[Bar]]) -> list[Trade]:
    h = validate_histories(histories)
    trades: list[Trade] = []
    busy: dict[str, datetime] = {}
    for instrument, bars in h.items():
        tr = [_true_range(bars, i) for i in range(len(bars))]
        for i in range(len(bars)):
            if i < 720 or i < 48 or i < 24:
                continue
            prior = bars[i - 48 : i]
            prior_high = max(b.high for b in prior)
            prior_low = min(b.low for b in prior)
            width = prior_high - prior_low
            if width <= 0.0:
                continue
            position = (bars[i].close - prior_low) / width
            if position >= 0.90:
                direction = -1
            elif position <= 0.10:
                direction = 1
            else:
                continue
            denom = sum(abs(bars[k].close - bars[k - 1].close) for k in range(i - 23, i + 1))
            if denom <= 0.0:
                continue
            efficiency = abs(bars[i].close - bars[i - 24].close) / denom
            if efficiency > 0.25:
                continue
            if bars[i].quote_volume > type7_quantile([b.quote_volume for b in bars[i - 720 : i]], 0.60):
                continue
            tr14 = tr[i - 13 : i + 1]
            if len(tr14) != 14 or any(v is None for v in tr14):
                continue
            atr = fmean([float(v) for v in tr14 if v is not None])
            entry_i = i + 1
            max_exit_i = entry_i + 6
            if max_exit_i >= len(bars):
                continue
            entry_time = bars[entry_i].timestamp
            if entry_time >= PROTECTED_START:
                continue
            prior_busy = busy.get(instrument)
            if prior_busy is not None and entry_time < prior_busy:
                continue
            midpoint = (prior_high + prior_low) / 2.0
            entry_open = bars[entry_i].open
            stop = entry_open - atr if direction > 0 else entry_open + atr
            exit_i = max_exit_i
            reasons: tuple[str, ...] = ("max_hold",)
            for k in range(entry_i, max_exit_i):
                midpoint_hit = bars[k].close >= midpoint if direction > 0 else bars[k].close <= midpoint
                stop_hit = bars[k].low <= stop if direction > 0 else bars[k].high >= stop
                if midpoint_hit or stop_hit:
                    exit_i = k + 1
                    flags = []
                    if midpoint_hit:
                        flags.append("midpoint")
                    if stop_hit:
                        flags.append("stop")
                    reasons = tuple(flags)
                    break
            if bars[exit_i].timestamp >= PROTECTED_START:
                continue
            gross = direction * (bars[exit_i].open / entry_open - 1.0)
            trade = Trade(
                "DISC-RANGE-AUCTION-REV-001-v1",
                instrument,
                bars[i].timestamp,
                entry_time,
                bars[exit_i].timestamp,
                gross,
                1.0,
                reasons,
            )
            trades.append(trade)
            busy[instrument] = trade.exit_time
    return sorted(trades, key=lambda t: (t.entry_time, t.instrument_key))


_BUILDERS = {
    "DISC-RESIDUAL-REV-001-v1": residual_reversion_trades,
    "DISC-SIGNED-VOLUME-DRIFT-001-v1": signed_volume_drift_trades,
    "DISC-LOWVOL-DRIFT-REV-001-v1": lowvol_drift_reversion_trades,
    "DISC-WEEKEND-NORMALIZE-001-v1": weekend_normalization_trades,
    "DISC-MODERATEVOL-AUTOCORR-001-v1": moderatevol_autocorr_trades,
    "DISC-RANGE-AUCTION-REV-001-v1": range_auction_reversion_trades,
}


def build_trades(candidate_id: str, histories: Mapping[str, Sequence[Bar]]) -> list[Trade]:
    try:
        builder = _BUILDERS[candidate_id]
    except KeyError as exc:
        raise ValueError("candidate is not Stage-1 authorized") from exc
    return builder(histories)


def cluster_independent_events(trades: Iterable[Trade]) -> list[IndependentEvent]:
    ordered = sorted(trades, key=lambda t: (t.entry_time, t.exit_time, t.instrument_key))
    if not ordered:
        return []
    events: list[IndependentEvent] = []
    group: list[Trade] = [ordered[0]]
    cluster_exit = ordered[0].exit_time
    for trade in ordered[1:]:
        if trade.entry_time < cluster_exit:
            group.append(trade)
            cluster_exit = max(cluster_exit, trade.exit_time)
        else:
            events.append(IndependentEvent(group[0].entry_time, cluster_exit, tuple(group)))
            group = [trade]
            cluster_exit = trade.exit_time
    events.append(IndependentEvent(group[0].entry_time, cluster_exit, tuple(group)))
    return events


def _partition_trades(trades: Iterable[Trade], start: datetime, end: datetime) -> list[Trade]:
    return [
        trade
        for trade in trades
        if start <= trade.signal_time <= end
        and start <= trade.entry_time <= end
        and start <= trade.exit_time <= end
    ]


def _profit_factor(values: Sequence[float]) -> float:
    gains = sum(v for v in values if v > 0.0)
    losses = -sum(v for v in values if v < 0.0)
    if gains <= 0.0:
        return 0.0
    if losses <= 0.0:
        return math.inf
    return gains / losses


def summarize_events(events: Sequence[IndependentEvent]) -> PartitionSummary:
    if not events:
        return PartitionSummary(0, None, None, None, None, None, None, 0.0, False)
    base = [event.return_at_cost(24.0) for event in events]
    medium = [event.return_at_cost(48.0) for event in events]
    stress = [event.return_at_cost(72.0) for event in events]
    positive_pool = sum(value for value in base if value > 0.0)
    worst_loss_abs = max(((-value) for value in base if value < 0.0), default=0.0)
    if len(base) > 1:
        best_i = max(range(len(base)), key=base.__getitem__)
        leave_best = fmean(value for i, value in enumerate(base) if i != best_i)
    else:
        leave_best = None
    return PartitionSummary(
        independent_events=len(events),
        mean_24bps=fmean(base),
        mean_48bps=fmean(medium),
        mean_72bps=fmean(stress),
        profit_factor_24bps=_profit_factor(base),
        leave_best_mean_24bps=leave_best,
        worst_loss_abs_24bps=worst_loss_abs,
        positive_pool_24bps=positive_pool,
        catastrophic_tail_pass_24bps=positive_pool > 0.0 and worst_loss_abs <= 0.50 * positive_pool,
    )


def _event_half_mean(events: Sequence[IndependentEvent], start: datetime, end: datetime) -> float | None:
    eligible = [event for event in events if start <= event.entry_time and event.exit_time <= end]
    if not eligible:
        return None
    return fmean(event.return_at_cost(24.0) for event in eligible)


def evaluate_stage1(candidate_id: str, trades: Iterable[Trade]) -> Stage1Result:
    if candidate_id not in CANDIDATE_IDS:
        raise ValueError("candidate is not Stage-1 authorized")
    all_trades = list(trades)
    if any(trade.candidate_id != candidate_id for trade in all_trades):
        raise ValueError("mixed candidate trades are forbidden")
    train_events = cluster_independent_events(_partition_trades(all_trades, TRAIN_START, TRAIN_END))
    validation_events = cluster_independent_events(
        _partition_trades(all_trades, VALIDATION_START, VALIDATION_END)
    )
    train = summarize_events(train_events)
    validation = summarize_events(validation_events)
    half_means = tuple(_event_half_mean(validation_events, start, end) for start, end in VALIDATION_HALVES)
    gates = {
        "minimum_training_events": train.independent_events >= 40,
        "minimum_validation_events": validation.independent_events >= 20,
        "positive_24bps_training": train.mean_24bps is not None and train.mean_24bps > 0.0,
        "positive_24bps_validation": validation.mean_24bps is not None and validation.mean_24bps > 0.0,
        "profit_factor_training": train.profit_factor_24bps is not None and train.profit_factor_24bps > 1.0,
        "profit_factor_validation": validation.profit_factor_24bps is not None and validation.profit_factor_24bps > 1.0,
        "positive_72bps_training": train.mean_72bps is not None and train.mean_72bps > 0.0,
        "positive_72bps_validation": validation.mean_72bps is not None and validation.mean_72bps > 0.0,
        "validation_half_1_positive": half_means[0] is not None and half_means[0] > 0.0,
        "validation_half_2_positive": half_means[1] is not None and half_means[1] > 0.0,
        "leave_best_training_positive": train.leave_best_mean_24bps is not None and train.leave_best_mean_24bps > 0.0,
        "leave_best_validation_positive": validation.leave_best_mean_24bps is not None and validation.leave_best_mean_24bps > 0.0,
        "catastrophic_tail_training": train.catastrophic_tail_pass_24bps,
        "catastrophic_tail_validation": validation.catastrophic_tail_pass_24bps,
    }
    if not gates["minimum_training_events"] or not gates["minimum_validation_events"]:
        classification = "INCONCLUSIVE_POWER"
    elif all(gates.values()):
        classification = "PASS_STAGE1_DEVELOPMENT_ONLY"
    else:
        classification = "FAIL_ECONOMIC_OR_ROBUSTNESS_GATE"
    return Stage1Result(
        candidate_id=candidate_id,
        classification=classification,
        raw_trade_count=len(all_trades),
        training=train,
        validation=validation,
        validation_half_means_24bps=(half_means[0], half_means[1]),
        gate_results=gates,
    )


def run_synthetic_or_caller_supplied_stage1(
    candidate_id: str, histories: Mapping[str, Sequence[Bar]]
) -> Stage1Result:
    """Build and evaluate a candidate from caller-supplied development-safe bars.

    This function deliberately does not know a repository dataset path.  That keeps
    the pre-integration implementation phase physically unable to open protected or
    real Cohort evidence on its own.  Every result from this runner is explicitly
    TEST_ONLY_UNTRUSTED and cannot become canonical Stage-1 evidence.
    """
    return evaluate_stage1(candidate_id, build_trades(candidate_id, histories))
