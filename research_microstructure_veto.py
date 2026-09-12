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
    if imbalance is not None and abs(imbalance) >= 0.35:
        direction = str(row.get("direction") or "").upper()
        if direction == "LONG":
            return "favorable_imbalance" if imbalance > 0 else "adverse_imbalance"
        if direction == "SHORT":
            return "favorable_imbalance" if imbalance < 0 else "adverse_imbalance"
        return "direction_unknown_imbalance"
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

    computed = {name: _metrics(bucket, cost_pct=cost_pct) for name, bucket in buckets.items()}
    normal = computed.get("normal")
    baseline_ready = bool(
        normal
        and normal["samples"] >= MIN_SAMPLES
        and normal["economic_evidence_complete"]
        and normal["after_cost_expectancy_pct"] is not None
    )
    normal_expectancy = float(normal["after_cost_expectancy_pct"]) if baseline_ready else None

    groups = []
    for name in sorted(buckets):
        metrics = computed[name]
        incremental = None
        if normal_expectancy is not None and metrics["after_cost_expectancy_pct"] is not None:
            incremental = round(float(metrics["after_cost_expectancy_pct"]) - normal_expectancy, 4)

        status = "INSUFFICIENT_EVIDENCE"
        own_ready = metrics["samples"] >= MIN_SAMPLES and metrics["economic_evidence_complete"]
        if name == "normal" and own_ready:
            status = "BASELINE_REFERENCE"
        elif own_ready and baseline_ready and incremental is not None:
            # A restrictive execution hypothesis must be economically bad in
            # absolute terms *and* worse than normal conditions. This prevents
            # attributing a generally weak strategy/regime to microstructure.
            if float(metrics["after_cost_expectancy_pct"]) <= 0.0 and incremental < 0.0:
                status = "RESTRICTIVE_VETO_CANDIDATE"
            else:
                status = "NO_VETO_EVIDENCE"

        groups.append({
            "microstructure_state": name,
            **metrics,
            "incremental_expectancy_vs_normal_pct": incremental,
            "normal_baseline_ready": baseline_ready,
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
        "normal_baseline_ready": baseline_ready,
        "groups": groups,
        "historical_orderbook_reconstruction_allowed": False,
        "missing_microstructure_policy": "insufficient_evidence",
        "trade_authority": False,
        "promotion_authority": False,
        "broker_connected": False,
    }
