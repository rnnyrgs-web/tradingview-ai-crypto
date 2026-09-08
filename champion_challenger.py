"""Research-only champion/challenger strategy weighting.

This module never grants live authority. It only ranks strategies that already
passed the existing sealed repeated-OOS evidence gates.
"""

from __future__ import annotations

from math import isfinite


def _num(value, default=0.0):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if isfinite(number) else default


def _run_quality(run):
    validation = run.get("validation") or {}
    holdout = run.get("holdout_test") or {}
    val_exp = max(0.0, _num(validation.get("avg_trade_pct")))
    oos_exp = max(0.0, _num(holdout.get("avg_trade_pct")))
    val_pf = max(0.0, min(_num(validation.get("profit_factor")), 4.0))
    oos_pf = max(0.0, min(_num(holdout.get("profit_factor")), 4.0))
    val_dd = max(0.0, _num(validation.get("max_drawdown_pct")))
    oos_dd = max(0.0, _num(holdout.get("max_drawdown_pct")))
    trades = max(0.0, _num(validation.get("trades"))) + max(0.0, _num(holdout.get("trades")))

    # Favor repeatable after-cost expectancy and PF, penalize drawdown, and use
    # sample size only as a bounded confidence multiplier.
    expectancy = min(val_exp, oos_exp)
    profit_factor = min(val_pf, oos_pf)
    drawdown_penalty = 1.0 / (1.0 + max(val_dd, oos_dd) / 10.0)
    sample_confidence = min(1.0, trades / 60.0)
    return expectancy * max(0.0, profit_factor - 1.0) * drawdown_penalty * sample_confidence


def _deterioration_penalty(runs):
    ordered = sorted(runs, key=lambda row: str(row.get("generated_at") or ""))
    if len(ordered) < 3:
        return 1.0
    split = max(1, len(ordered) // 2)
    early = [_run_quality(row) for row in ordered[:split]]
    recent = [_run_quality(row) for row in ordered[split:]]
    early_mean = sum(early) / len(early) if early else 0.0
    recent_mean = sum(recent) / len(recent) if recent else 0.0
    if early_mean <= 0:
        return 1.0 if recent_mean > 0 else 0.5
    ratio = recent_mean / early_mean
    if ratio >= 1.0:
        return 1.0
    if ratio <= 0.25:
        return 0.2
    return max(0.2, ratio)


def _pair_correlation(key_a, key_b, correlation_matrix):
    if key_a == key_b:
        return 1.0
    direct = correlation_matrix.get((key_a, key_b))
    reverse = correlation_matrix.get((key_b, key_a))
    value = direct if direct is not None else reverse
    if value is None:
        return 0.0
    return max(-1.0, min(1.0, _num(value)))


def build_champion_challenger(candidates, run_history, correlation_matrix=None, max_weight=0.45):
    """Return research-only ensemble weights for already-qualified candidates.

    `run_history` maps `(symbol, bar, family)` to repeated sealed run metrics.
    `correlation_matrix` is optional and maps key-pairs to return correlation.
    Missing correlations never create a bonus; structural overlap is penalized
    conservatively after preliminary scoring.
    """
    correlation_matrix = correlation_matrix or {}
    cap = min(0.60, max(0.10, _num(max_weight, 0.45)))
    scored = []

    for candidate in candidates:
        key = (candidate.get("symbol"), candidate.get("bar"), candidate.get("strategy_family"))
        if not all(key):
            continue
        runs = list(run_history.get(key) or [])
        if len(runs) < 3:
            continue
        base = sum(_run_quality(row) for row in runs) / len(runs)
        deterioration = _deterioration_penalty(runs)
        raw = base * deterioration
        scored.append({
            "key": key,
            "symbol": key[0],
            "bar": key[1],
            "strategy_family": key[2],
            "base_quality": base,
            "deterioration_penalty": deterioration,
            "raw_score": raw,
            "distinct_sealed_runs": len(runs),
        })

    scored.sort(key=lambda row: (-row["raw_score"], row["key"]))
    selected = []
    for row in scored:
        correlation_penalty = 1.0
        structural_penalty = 1.0
        for chosen in selected:
            corr = abs(_pair_correlation(row["key"], chosen["key"], correlation_matrix))
            if corr >= 0.80:
                correlation_penalty *= 0.35
            elif corr >= 0.60:
                correlation_penalty *= 0.65
            if row["symbol"] == chosen["symbol"] and row["bar"] == chosen["bar"]:
                structural_penalty *= 0.80
            if row["strategy_family"] == chosen["strategy_family"]:
                structural_penalty *= 0.90
        row["correlation_penalty"] = max(0.15, correlation_penalty)
        row["structural_overlap_penalty"] = max(0.40, structural_penalty)
        row["adjusted_score"] = row["raw_score"] * row["correlation_penalty"] * row["structural_overlap_penalty"]
        selected.append(row)

    positive = [row for row in selected if row["adjusted_score"] > 0]
    total = sum(row["adjusted_score"] for row in positive)
    if total <= 0:
        return {
            "status": "NO_QUALIFIED_ENSEMBLE",
            "champion": None,
            "members": [],
            "live_approved": False,
            "policy": "Research-only. No candidate may gain live authority from ensemble weighting.",
        }

    # Iteratively cap concentration and renormalize remaining capacity.
    remaining = positive[:]
    weights = {row["key"]: 0.0 for row in positive}
    capacity = 1.0
    while remaining and capacity > 1e-12:
        denom = sum(row["adjusted_score"] for row in remaining)
        if denom <= 0:
            break
        newly_capped = []
        for row in remaining:
            proposed = capacity * row["adjusted_score"] / denom
            if proposed > cap:
                weights[row["key"]] = cap
                newly_capped.append(row)
        if not newly_capped:
            for row in remaining:
                weights[row["key"]] = capacity * row["adjusted_score"] / denom
            capacity = 0.0
            break
        for row in newly_capped:
            remaining.remove(row)
        capacity = max(0.0, 1.0 - sum(weights.values()))

    members = []
    for row in positive:
        weight = weights.get(row["key"], 0.0)
        if weight <= 0:
            continue
        member = {k: v for k, v in row.items() if k != "key"}
        member["weight"] = round(weight, 6)
        member["role"] = "CHAMPION" if not members else "CHALLENGER"
        members.append(member)
    members.sort(key=lambda row: (-row["weight"], -row["adjusted_score"], row["symbol"], row["bar"], row["strategy_family"]))
    if members:
        members[0]["role"] = "CHAMPION"
        for member in members[1:]:
            member["role"] = "CHALLENGER"

    champion = members[0] if members else None
    return {
        "status": "RESEARCH_ENSEMBLE_READY" if champion else "NO_QUALIFIED_ENSEMBLE",
        "champion": champion,
        "members": members,
        "max_member_weight": cap,
        "live_approved": False,
        "automatic_demotion": "Recent sealed-run deterioration reduces or can eliminate research weight; it never auto-promotes.",
        "policy": "Research-only champion/challenger ranking. Strategy Registry and Production Risk approvals remain mandatory for live use.",
    }
