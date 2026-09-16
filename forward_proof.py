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
from strategy_contract import CONTRACT_SCHEMA_VERSION, StrategyContract
from utils import parse_dt

MIN_FORWARD_SAMPLES = {"6h":30,"12h":30,"24h":20,"48h":20,"72h":16,"7d":12}
HORIZON_SPAN = {"6h":timedelta(hours=6),"12h":timedelta(hours=12),"24h":timedelta(hours=24),"48h":timedelta(hours=48),"72h":timedelta(hours=72),"7d":timedelta(days=7)}
MAX_FORWARD_DRAWDOWN_PCT = 12.0
FORWARD_COST_MULTIPLIER = 3.0
MIN_FORWARD_PRECISION_LOWER = 0.50
FORWARD_PROVENANCE_FIELDS = (
    "strategy_fingerprint",
    "signal_id",
    "experiment_id",
    "hypothesis_id",
    "git_sha",
    "dataset_id",
    "dataset_sha256",
    "strategy_contract_sha256",
    "decision_timestamp",
    "symbol",
    "direction",
    "entry_reference",
    "expected_horizon",
    "expected_move_pct",
    "stop_rule",
    "exit_rule",
)


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


def _validated_frozen_contract(frozen: dict) -> tuple[StrategyContract, dict]:
    if not isinstance(frozen, dict) or frozen.get("frozen") is not True:
        raise RuntimeError("forward shadow requires a frozen strategy contract")
    if frozen.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        raise RuntimeError("forward shadow received unsupported strategy contract schema")
    payload = frozen.get("payload")
    if not isinstance(payload, dict):
        raise RuntimeError("forward shadow strategy contract payload missing")
    contract = StrategyContract.from_mapping(payload)
    if frozen.get("fingerprint") != contract.fingerprint():
        raise RuntimeError("forward shadow strategy contract seal is invalid")
    return contract, payload


def build_forward_decision_record(
    frozen_contract: dict,
    gate_result: dict,
    *,
    signal_id: str,
    decision_timestamp: str,
    symbol: str,
    direction: str,
    entry_reference: float,
    expected_horizon: str,
    expected_move_pct: float,
    stop_rule,
    exit_rule,
) -> dict:
    """Create the immutable decision-time record that starts genuine forward evidence.

    Independent reproduction must already have passed: the central lifecycle therefore
    must be FORWARD_PENDING. OOS_PASS alone is insufficient and cannot open forward
    collection. This helper never grants real-money authority.
    """
    gate_result = gate_result if isinstance(gate_result, dict) else {}
    if gate_result.get("state") != "FORWARD_PENDING":
        raise RuntimeError("forward shadow requires central state FORWARD_PENDING")
    blockers = set(gate_result.get("blocking_gates") or [])
    if blockers - {"genuine_forward"}:
        raise RuntimeError("forward shadow has unresolved pre-forward validation gates")
    if gate_result.get("real_money_trade_authority") is not False:
        raise RuntimeError("forward shadow cannot carry real-money trade authority")

    contract, payload = _validated_frozen_contract(frozen_contract)
    signal_id = str(signal_id or "").strip()
    timestamp = str(decision_timestamp or "").strip()
    symbol = str(symbol or "").strip().upper()
    direction = str(direction or "").strip().upper()
    horizon = str(expected_horizon or "").strip()
    entry = _finite(entry_reference)
    move = _finite(expected_move_pct)
    if not all((signal_id, timestamp, symbol, horizon)) or direction not in {"LONG", "SHORT"}:
        raise RuntimeError("forward decision identity is incomplete")
    if entry is None or entry <= 0 or move is None:
        raise RuntimeError("forward decision economics are invalid")

    return {
        "strategy_fingerprint": contract.fingerprint(),
        "signal_id": signal_id,
        "experiment_id": str(payload["experiment_id"]),
        "hypothesis_id": str(payload["hypothesis_id"]),
        "git_sha": str(payload["git_sha"]),
        "dataset_id": str(payload["dataset_id"]),
        "dataset_sha256": str(payload["dataset_sha256"]),
        "strategy_contract_sha256": contract.fingerprint(),
        "decision_timestamp": timestamp,
        "symbol": symbol,
        "direction": direction,
        "entry_reference": entry,
        "expected_horizon": horizon,
        "expected_move_pct": move,
        "stop_rule": stop_rule,
        "exit_rule": exit_rule,
        "outcome_status": "PENDING",
        "real_money_trade_authority": False,
    }


def assert_forward_provenance_unchanged(existing: dict, proposed: dict) -> None:
    if not isinstance(existing, dict) or not isinstance(proposed, dict):
        raise RuntimeError("forward provenance records must be objects")
    changed = [field for field in FORWARD_PROVENANCE_FIELDS if proposed.get(field) != existing.get(field)]
    if changed:
        raise RuntimeError(f"forward provenance changed: {changed}")


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
