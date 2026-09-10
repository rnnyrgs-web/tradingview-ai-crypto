"""Fail-closed genuine-forward evidence gate for live strategy eligibility.

Historical/OOS evidence and signed promotion are necessary but not sufficient.
This module requires independent resolved forward forecasts for the exact
strategy fingerprint before production validation may approve a live action.
"""

from __future__ import annotations

import math
from datetime import timedelta

from calibration import deterioration_assessment, wilson_lower_bound
from config import BACKTEST_COST_BPS
from utils import parse_dt

MIN_FORWARD_SAMPLES = {"6h":30,"12h":30,"24h":20,"48h":20,"72h":16,"7d":12}
HORIZON_SPAN = {"6h":timedelta(hours=6),"12h":timedelta(hours=12),"24h":timedelta(hours=24),"48h":timedelta(hours=48),"72h":timedelta(hours=72),"7d":timedelta(days=7)}
MAX_FORWARD_DRAWDOWN_PCT = 12.0
FORWARD_COST_MULTIPLIER = 3.0
MIN_FORWARD_PRECISION_LOWER = 0.50


def _finite(value):
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _fingerprint(row):
    identity = row.get("strategy_identity")
    return str(identity.get("fingerprint", "")) if isinstance(identity, dict) else ""


def _stable_identity(row):
    return (str(row.get("scan_id") or ""),str(row.get("symbol") or ""),_fingerprint(row),str(row.get("direction") or ""),str(row.get("score") or ""))


def _independent_rows(rows, horizon):
    span = HORIZON_SPAN.get(horizon)
    if span is None:
        return []
    valid = []
    for row in rows:
        if not row.get("due_at") or not row.get("resolved_at"):
            continue
        try:
            due = parse_dt(row["due_at"]); resolved = parse_dt(row["resolved_at"])
        except (TypeError, ValueError, OverflowError):
            continue
        directional = _finite(row.get("directional_return_pct"))
        if directional is None or resolved < due:
            continue
        origin = due - span
        valid.append((origin, due, _stable_identity(row), row, directional))
    valid.sort(key=lambda item: (item[0], item[1], item[2]))
    selected=[]; next_allowed=None
    for origin,due,_identity,row,directional in valid:
        if next_allowed is not None and origin < next_allowed:
            continue
        selected.append((row,directional)); next_allowed=due
    return selected


def _max_drawdown_pct(net_returns):
    equity = peak = 1.0
    worst = 0.0
    for value in net_returns:
        equity *= max(0.0, 1.0 + value / 100.0)
        peak = max(peak, equity)
        if peak > 0:
            worst = max(worst, (peak - equity) / peak * 100.0)
    return worst


def assess_forward_proof(identity, horizon, resolved_rows):
    fingerprint = str((identity or {}).get("fingerprint", ""))
    minimum = MIN_FORWARD_SAMPLES.get(horizon)
    if not fingerprint or minimum is None:
        return {"passed":False,"status":"FORWARD_PROOF_UNAVAILABLE","reason":"missing_exact_identity_or_supported_horizon","independent_samples":0}
    matching=[row for row in (resolved_rows or []) if row.get("horizon")==horizon and _fingerprint(row)==fingerprint and row.get("resolved_at")]
    selected=_independent_rows(matching,horizon)
    cost_pct=BACKTEST_COST_BPS*FORWARD_COST_MULTIPLIER/100.0
    net_returns=[directional-cost_pct for _,directional in selected]
    successes=sum(value>0 for value in net_returns); sample_count=len(net_returns)
    precision=successes/sample_count if sample_count else 0.0; lower=wilson_lower_bound(successes,sample_count)
    expectancy=sum(net_returns)/sample_count if sample_count else None; drawdown=_max_drawdown_pct(net_returns) if net_returns else None
    deterioration_rows=[]
    for (row,_),net_return in zip(selected,net_returns):
        copied=dict(row); copied["correct"]=net_return>0; deterioration_rows.append(copied)
    deterioration=deterioration_assessment(deterioration_rows)
    sample_ready=sample_count>=minimum; positive_expectancy=expectancy is not None and expectancy>0; precision_pass=sample_ready and lower>=MIN_FORWARD_PRECISION_LOWER
    drawdown_pass=drawdown is not None and drawdown<=MAX_FORWARD_DRAWDOWN_PCT; deterioration_pass=not deterioration.get("deteriorating",False)
    passed=bool(sample_ready and positive_expectancy and precision_pass and drawdown_pass and deterioration_pass)
    if not sample_ready: reason="insufficient_independent_forward_samples"
    elif not positive_expectancy: reason="non_positive_after_cost_forward_expectancy"
    elif not precision_pass: reason="forward_precision_confidence_too_weak"
    elif not drawdown_pass: reason="forward_drawdown_too_high"
    elif not deterioration_pass: reason="recent_forward_deterioration"
    else: reason="forward_proof_passed"
    return {"passed":passed,"status":"FORWARD_PROOF_PASSED" if passed else "FORWARD_PROOF_BLOCKED","reason":reason,"horizon":horizon,"raw_matching_rows":len(matching),"independent_samples":sample_count,"minimum_independent_samples":minimum,"sample_sufficiency_basis":"non_overlapping_full_horizon_forecasts_reconstructed_from_due_at","after_cost_successes":successes,"after_cost_precision":round(precision,4) if sample_count else None,"after_cost_precision_95pct_lower":round(lower,4) if sample_count else None,"after_cost_expectancy_pct":round(expectancy,6) if expectancy is not None else None,"max_forward_drawdown_pct":round(drawdown,4) if drawdown is not None else None,"modeled_round_trip_cost_bps":BACKTEST_COST_BPS*FORWARD_COST_MULTIPLIER,"deterioration":deterioration,"policy":{"non_overlapping_samples_only":True,"chronology_source":"due_at_minus_horizon","precision_95pct_lower_gte":MIN_FORWARD_PRECISION_LOWER,"expectancy_after_cost_gt_pct":0.0,"max_drawdown_lte_pct":MAX_FORWARD_DRAWDOWN_PCT,"no_active_deterioration":True,"can_authorize_by_itself":False}}
