"""Research-only prospective microstructure veto diagnostics.

Uses only timestamped microstructure fields already attached to forecast rows.
Missing data is not reconstructed. Candidate vetoes remain restrictive research
hypotheses until canonical validation/OOS/forward gates pass.
"""

from __future__ import annotations

from collections import defaultdict
from math import isfinite

from selective_precision import _independent_rows
from signal_development import objective_reference

MIN_SAMPLES = 8


def _finite(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if isfinite(value) else None


def _micro(row):
    nested = row.get("microstructure")
    return nested if isinstance(nested, dict) else {}


def _value(row, key):
    nested = _micro(row)
    return nested.get(key, row.get(key))


def _independent(rows):
    out = []
    for horizon in ("24h", "7d"):
        resolved = [r for r in (rows or []) if r.get("horizon") == horizon and r.get("resolved_at") and isinstance(r.get("correct"), bool)]
        out.extend(_independent_rows(resolved, horizon))
    return out


def _bucket(row):
    reliable = _value(row, "reliable")
    if reliable is False:
        return "unreliable"
    spread = _finite(_value(row, "spread_bps"))
    depth = _finite(_value(row, "visible_quote_depth"))
    imbalance = _finite(_value(row, "depth_imbalance"))
    if spread is None and depth is None and imbalance is None:
        return None
    if spread is not None and spread >= 35:
        return "wide_spread"
    if depth is not None and depth < 5000:
        return "thin_depth"
    if imbalance is not None and imbalance <= -0.35:
        return "ask_heavy"
    if imbalance is not None and imbalance >= 0.35:
        return "bid_heavy"
    return "normal"


def _metrics(rows, cost_pct=0.12):
    total = len(rows)
    returns = [_finite(r.get("directional_return_pct")) for r in rows]
    complete = total > 0 and all(v is not None for v in returns)
    expectancy = None
    if complete:
        expectancy = sum(v - float(cost_pct) for v in returns) / total
    precision = sum(1 for r in rows if r.get("correct") is True) / total if total else None
    return {
        "samples": total,
        "precision": round(precision, 4) if precision is not None else None,
        "after_cost_expectancy_pct": round(expectancy, 4) if expectancy is not None else None,
        "economic_evidence_complete": complete,
    }


def build_microstructure_veto(rows, *, cost_pct=0.12):
    selected = _independent(rows)
    buckets = defaultdict(list)
    observed = 0
    for row in selected:
        bucket = _bucket(row)
        if bucket is not None:
            observed += 1
            buckets[bucket].append(row)
    groups = []
    for name, bucket in sorted(buckets.items()):
        metrics = _metrics(bucket, cost_pct=cost_pct)
        status = "INSUFFICIENT_EVIDENCE"
        if metrics["samples"] >= MIN_SAMPLES and metrics["economic_evidence_complete"]:
            status = "RESTRICTIVE_VETO_CANDIDATE" if float(metrics["after_cost_expectancy_pct"]) <= 0.0 else "NO_VETO_EVIDENCE"
        groups.append({
            "microstructure_state": name,
            **metrics,
            "candidate_status": status,
            "requires_fresh_validation": True,
            "trade_authority": False,
        })
    return {
        "ok": True,
        "research_only": True,
        "objective": objective_reference("prospective-microstructure-veto", "learning_diagnostics"),
        "independent_samples": len(selected),
        "samples_with_microstructure": observed,
        "coverage": round(observed / len(selected), 4) if selected else None,
        "groups": groups,
        "historical_orderbook_reconstruction_allowed": False,
        "missing_microstructure_policy": "insufficient_evidence",
        "trade_authority": False,
        "promotion_authority": False,
        "broker_connected": False,
    }
