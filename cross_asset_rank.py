"""Timestamp-safe cross-sectional relative-strength research (ACC-002).

This module is deliberately research-only. It ranks a liquid crypto universe using
features available at each timestamp, then evaluates forward cross-sectional rank
IC and top-minus-bottom spread on chronological train/validation/untouched OOS
segments. Split boundaries are purged by the forward horizon and observations are
sampled at non-overlapping horizons to reduce leakage/autocorrelation inflation.
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
    cost_stress_multipliers: tuple[float, ...] = (1.0, 1.5, 2.0, 3.0)
    non_overlapping_evaluation: bool = True


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
    returns = [_pct(closes[idx - lb], closes[idx]) for lb in lookbacks]
    one_bar = [_pct(closes[j - 1], closes[j]) for j in range(idx - max(lookbacks) + 1, idx + 1)]
    vol = _stdev(one_bar) or 1e-9
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


def purged_split_ranges(n: int, forward_bars: int) -> dict[str, tuple[int, int]]:
    if n < 5:
        raise ValueError("insufficient panel for chronological splits")
    train_boundary = max(1, int(n * 0.60))
    validation_boundary = max(train_boundary + 1, int(n * 0.80))
    validation_boundary = min(validation_boundary, n)
    purge = max(1, int(forward_bars))

    train_end = max(0, train_boundary - purge)
    validation_end = max(train_boundary, validation_boundary - purge)
    if train_end <= 0 or validation_end <= train_boundary or validation_boundary >= n:
        raise ValueError("insufficient panel after split purge")
    return {
        "train": (0, train_end),
        "validation": (train_boundary, validation_end),
        "untouched_oos": (validation_boundary, n),
    }


def score_segment(panel: list[dict], start: int, end: int, config: CrossAssetConfig) -> dict:
    stride = max(1, config.forward_bars if config.non_overlapping_evaluation else 1)
    stress_grid = tuple(sorted({float(x) for x in config.cost_stress_multipliers if float(x) >= 1.0}))
    if not stress_grid:
        raise ValueError("cost stress grid must contain multiplier >= 1")
    sampled = panel[start:end:stride]
    ics: list[float] = []
    spreads: list[float] = []
    for item in sampled:
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
        spreads.append(top - bottom)

    stress_metrics = {}
    for multiplier in stress_grid:
        cost = (config.round_trip_cost_bps * multiplier) / 10000.0
        net = [spread - cost for spread in spreads]
        stress_metrics[str(multiplier)] = {
            "cost_multiplier": multiplier,
            "round_trip_cost_bps": config.round_trip_cost_bps * multiplier,
            "mean_net_top_minus_bottom": mean(net) if net else None,
            "positive_net_spread_rate": sum(x > 0 for x in net) / len(net) if net else 0.0,
            "cumulative_net_spread": sum(net),
        }

    base = stress_metrics[str(min(stress_grid))]
    return {
        "timestamps": len(sampled),
        "raw_range_observations": max(0, end - start),
        "evaluation_stride": stride,
        "mean_rank_ic": mean(ics) if ics else None,
        "positive_rank_ic_rate": sum(x > 0 for x in ics) / len(ics) if ics else 0.0,
        "mean_gross_top_minus_bottom": mean(spreads) if spreads else None,
        "mean_net_top_minus_bottom": base["mean_net_top_minus_bottom"],
        "positive_net_spread_rate": base["positive_net_spread_rate"],
        "cumulative_net_spread": base["cumulative_net_spread"],
        "cost_stress": stress_metrics,
    }


def evaluate_pre_oos(panel: list[dict], config: CrossAssetConfig = CrossAssetConfig()) -> dict:
    """Return only train+validation metrics for candidate selection.

    This function intentionally does not calculate untouched-OOS metrics, so model
    or parameter selection can be completed before the holdout is opened.
    """
    if not panel:
        raise ValueError("empty panel")
    ranges = purged_split_ranges(len(panel), config.forward_bars)
    train = score_segment(panel, *ranges["train"], config)
    validation = score_segment(panel, *ranges["validation"], config)
    return {
        "lookbacks": list(config.lookbacks),
        "forward_bars": config.forward_bars,
        "split_ranges": {"train": list(ranges["train"]), "validation": list(ranges["validation"])},
        "train": train,
        "validation": validation,
        "untouched_oos_opened": False,
    }


def evaluate_untouched_oos(panel: list[dict], config: CrossAssetConfig = CrossAssetConfig()) -> dict:
    """Open the untouched holdout for exactly one preselected configuration."""
    if not panel:
        raise ValueError("empty panel")
    ranges = purged_split_ranges(len(panel), config.forward_bars)
    oos = score_segment(panel, *ranges["untouched_oos"], config)
    stress_grid = tuple(sorted({float(x) for x in config.cost_stress_multipliers if float(x) >= 1.0}))
    worst = oos["cost_stress"][str(max(stress_grid))]
    research_pass = bool(
        oos["timestamps"] >= 20
        and (oos["mean_rank_ic"] or 0.0) > 0.0
        and (worst["mean_net_top_minus_bottom"] or 0.0) > 0.0
        and worst["positive_net_spread_rate"] >= 0.50
    )
    return {
        "range": list(ranges["untouched_oos"]),
        "metrics": oos,
        "passes_acc002_research_gate": research_pass,
        "gate_uses_max_cost_stress": True,
        "untouched_oos_opened": True,
    }


def evaluate_panel(panel: list[dict], config: CrossAssetConfig = CrossAssetConfig()) -> dict:
    """Compatibility wrapper for a single already-fixed configuration."""
    pre = evaluate_pre_oos(panel, config)
    oos = evaluate_untouched_oos(panel, config)
    return {
        "research_only": True,
        "live_approved": False,
        "trade_authority": False,
        "lookbacks": list(config.lookbacks),
        "forward_bars": config.forward_bars,
        "purge_bars": config.forward_bars,
        "non_overlapping_evaluation": config.non_overlapping_evaluation,
        "evaluation_stride": max(1, config.forward_bars if config.non_overlapping_evaluation else 1),
        "round_trip_cost_bps": config.round_trip_cost_bps,
        "cost_stress_multipliers": list(config.cost_stress_multipliers),
        "split_ranges": {**pre["split_ranges"], "untouched_oos": oos["range"]},
        "splits": {"train": pre["train"], "validation": pre["validation"], "untouched_oos": oos["metrics"]},
        "passes_acc002_research_gate": oos["passes_acc002_research_gate"],
        "gate_uses_max_cost_stress": True,
    }
