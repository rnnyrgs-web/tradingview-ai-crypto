"""Research-only diagnostics for cross-sectional and residual signal evidence.

Only pre-forecast fields already persisted on resolved ledger rows are used. No
historical features are reconstructed and missing fields remain unavailable.
"""

from __future__ import annotations

from collections import defaultdict
from math import isfinite

from selective_precision import _independent_rows
from signal_development import objective_reference

MIN_SAMPLES = 8
FEATURES = (
    "cross_sectional_rank",
    "residual_momentum_score",
    "relative_strength_score",
    "market_breadth_score",
    "btc_beta",
)
CATEGORICAL = ("leadership_state", "breadth_state", "sector_state")


def _finite(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if isfinite(value) else None


def _independent(rows):
    out = []
    for horizon in ("24h", "7d"):
        resolved = [r for r in (rows or []) if r.get("horizon") == horizon and r.get("resolved_at") and isinstance(r.get("correct"), bool)]
        out.extend(_independent_rows(resolved, horizon))
    return out


def _numeric_band(name, value):
    value = _finite(value)
    if value is None:
        return None
    if name == "cross_sectional_rank":
        if value <= 5:
            return "top5"
        if value <= 10:
            return "top10"
        if value <= 20:
            return "top20"
        return "outside_top20"
    if name == "btc_beta":
        if value < 0.5:
            return "beta<0.5"
        if value < 1.0:
            return "beta0.5-1"
        if value < 1.5:
            return "beta1-1.5"
        return "beta>=1.5"
    if value < -0.5:
        return "strong_negative"
    if value < 0:
        return "negative"
    if value < 0.5:
        return "positive"
    return "strong_positive"


def _metrics(rows):
    total = len(rows)
    correct = sum(1 for row in rows if row.get("correct") is True)
    returns = [_finite(row.get("directional_return_pct")) for row in rows]
    complete = total > 0 and all(v is not None for v in returns)
    expectancy = sum(returns) / total if complete else None
    return {
        "samples": total,
        "precision": round(correct / total, 4) if total else None,
        "gross_directional_expectancy_pct": round(expectancy, 4) if expectancy is not None else None,
        "economic_evidence_complete": complete,
    }


def build_cross_sectional_diagnostics(rows):
    selected = _independent(rows)
    groups = []
    available_fields = set()
    for feature in FEATURES:
        buckets = defaultdict(list)
        for row in selected:
            band = _numeric_band(feature, row.get(feature))
            if band is not None:
                available_fields.add(feature)
                buckets[band].append(row)
        for band, bucket in sorted(buckets.items()):
            metrics = _metrics(bucket)
            groups.append({
                "feature": feature,
                "group": band,
                **metrics,
                "ready_for_research": metrics["samples"] >= MIN_SAMPLES,
                "requires_point_in_time_provenance": True,
                "requires_fresh_validation": True,
            })
    for feature in CATEGORICAL:
        buckets = defaultdict(list)
        for row in selected:
            value = row.get(feature)
            if value not in (None, ""):
                available_fields.add(feature)
                buckets[str(value)].append(row)
        for group, bucket in sorted(buckets.items()):
            metrics = _metrics(bucket)
            groups.append({
                "feature": feature,
                "group": group,
                **metrics,
                "ready_for_research": metrics["samples"] >= MIN_SAMPLES,
                "requires_point_in_time_provenance": True,
                "requires_fresh_validation": True,
            })
    groups.sort(key=lambda x: (not x["ready_for_research"], -x["samples"], x["feature"], x["group"]))
    return {
        "ok": True,
        "research_only": True,
        "objective": objective_reference("cross-sectional-residual-diagnostics", "learning_diagnostics"),
        "independent_samples": len(selected),
        "available_preforecast_fields": sorted(available_fields),
        "missing_fields": sorted(set(FEATURES + CATEGORICAL) - available_fields),
        "groups": groups,
        "historical_backfill_allowed": False,
        "point_in_time_required": True,
        "trade_authority": False,
        "promotion_authority": False,
    }
