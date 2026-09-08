"""Timestamp-safe cross-sectional relative-strength research (ACC-002).

This module is deliberately research-only. It ranks a liquid crypto universe using
features available at each timestamp, then evaluates forward cross-sectional rank
IC and top-minus-bottom spread on chronological train/validation/untouched OOS
segments. No future value is used in feature construction or model fitting.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import mean
from typing import Iterable


@dataclass(frozen=True)
class CrossAssetConfig:
    lookbacks: tuple[int, ...] = (4, 16, 64)
    forward_bars: int = 4
    top_fraction: float = 0.20
    round_trip_cost_bps: float = 12.0
    min_assets: int = 8


def _pct(a: float, b: float) -> float:
    if a <= 0 or b <= 0:
        raise ValueError("prices must be positive")
    return b / a - 1.0


def _stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = mean(values)
    return math.sqrt(sum((x - m) ** 2 for x in values) / (len(values) - 1))


def _rank(values: list[float]) -> list[float]:
    """Average ranks for ties, ascending, 1-based."""
    order = sorted(range(len(values)), key=values.__getitem__)
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i + 1
        while j < len(order) and values[order[j]] == values[order[i]]:
            j += 1
        avg_rank = (i + 1 + j) / 2.0
        for k in range(i, j):
            ranks[order[k]] = avg_rank
        i = j
    return ranks


def spearman_rank_ic(scores: list[float], outcomes: list[float]) -> float | None:
    if len(scores) != len(outcomes) or len(scores) < 3:
        return None
    x = _rank(scores)
    y = _rank(outcomes)
    mx, my = mean(x), mean(y)
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    dx = math.sqrt(sum((a - mx) ** 2 for a in x))
    dy = math.sqrt(sum((b - my) ** 2 for b in y))
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def normalize_histories(histories: dict[str, Iterable[dict]]) -> dict[str, dict[int, float]]:
    out: dict[str, dict[int, float]] = {}
    for symbol, rows in histories.items():
        by_ts: dict[int, float] = {}
        last_ts = None
        for row in rows:
            ts = int(row["ts"])
            close = float(row["close"])
            if ts <= 0 or close <= 0:
                raise ValueError(f"invalid candle for {symbol}")
            if last_ts is not None and ts <= last_ts:
                raise ValueError(f"non-increasing timestamp for {symbol}")
            last_ts = ts
            by_ts[ts] = close
        if by_ts:
            out[symbol] = by_ts
    return out


def _feature_for(closes: list[float], idx: int, lookbacks: tuple[int, ...]) -> float:
    """Composite relative-strength score using only closes <= idx."""
    returns = [_pct(closes[idx - lb], closes[idx]) for lb in lookbacks]
    one_bar = [_pct(closes[j - 1], closes[j]) for j in range(idx - max(lookbacks) + 1, idx + 1)]
    vol = _stdev(one_bar) or 1e-9
    # Blend multiple horizons; volatility normalization prevents the noisiest coin
    # from winning the rank solely because it has the largest raw moves.
    return mean(returns) / vol


def build_cross_section_panel(
    histories: dict[str, Iterable[dict]], config: CrossAssetConfig = CrossAssetConfig()
) -> list[dict]:
    normalized = normalize_histories(histories)
    if len(normalized) < config.min_assets:
        raise ValueError("insufficient assets")
    common_ts = sorted(set.intersection(*(set(v) for v in normalized.values())))
    warmup = max(config.lookbacks)
    if len(common_ts) <= warmup + config.forward_bars:
        raise ValueError("insufficient aligned history")

    symbols = sorted(normalized)
    closes = {s: [normalized[s][ts] for ts in common_ts] for s in symbols}
    panel = []
    for idx in range(warmup, len(common_ts) - config.forward_bars):
        rows = []
        for symbol in symbols:
            series = closes[symbol]
            score = _feature_for(series, idx, config.lookbacks)
            forward = _pct(series[idx], series[idx + config.forward_bars])
            rows.append({"symbol": symbol, "score": score, "forward_return": forward})
        panel.append({"ts": common_ts[idx], "rows": rows})
    return panel


def evaluate_panel(panel: list[dict], config: CrossAssetConfig = CrossAssetConfig()) -> dict:
    if not panel:
        raise ValueError("empty panel")
    n = len(panel)
    train_end = max(1, int(n * 0.60))
    val_end = max(train_end + 1, int(n * 0.80))
    val_end = min(val_end, n)
    split_ranges = {
        "train": (0, train_end),
        "validation": (train_end, val_end),
        "untouched_oos": (val_end, n),
    }

    def score_segment(start: int, end: int) -> dict:
        ics: list[float] = []
        spreads: list[float] = []
        net_spreads: list[float] = []
        cost = config.round_trip_cost_bps / 10000.0
        for item in panel[start:end]:
            rows = item["rows"]
            scores = [r["score"] for r in rows]
            outcomes = [r["forward_return"] for r in rows]
            ic = spearman_rank_ic(scores, outcomes)
            if ic is not None:
                ics.append(ic)
            ranked = sorted(rows, key=lambda r: r["score"])
            bucket = max(1, int(len(ranked) * config.top_fraction))
            bottom = mean([r["forward_return"] for r in ranked[:bucket]])
            top = mean([r["forward_return"] for r in ranked[-bucket:]])
            spread = top - bottom
            spreads.append(spread)
            net_spreads.append(spread - cost)
        positive_ic_rate = sum(x > 0 for x in ics) / len(ics) if ics else 0.0
        positive_net_rate = sum(x > 0 for x in net_spreads) / len(net_spreads) if net_spreads else 0.0
        return {
            "timestamps": end - start,
            "mean_rank_ic": mean(ics) if ics else None,
            "positive_rank_ic_rate": positive_ic_rate,
            "mean_gross_top_minus_bottom": mean(spreads) if spreads else None,
            "mean_net_top_minus_bottom": mean(net_spreads) if net_spreads else None,
            "positive_net_spread_rate": positive_net_rate,
            "cumulative_net_spread": sum(net_spreads),
        }

    metrics = {name: score_segment(a, b) for name, (a, b) in split_ranges.items()}
    oos = metrics["untouched_oos"]
    # Research gate only: deliberately conservative and not a live promotion gate.
    research_pass = bool(
        oos["timestamps"] >= 20
        and (oos["mean_rank_ic"] or 0.0) > 0.0
        and (oos["mean_net_top_minus_bottom"] or 0.0) > 0.0
        and oos["positive_net_spread_rate"] >= 0.50
    )
    return {
        "research_only": True,
        "live_approved": False,
        "trade_authority": False,
        "lookbacks": list(config.lookbacks),
        "forward_bars": config.forward_bars,
        "round_trip_cost_bps": config.round_trip_cost_bps,
        "splits": metrics,
        "passes_acc002_research_gate": research_pass,
    }
