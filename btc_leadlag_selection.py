"""Deterministic exploratory screen for DISC-BTC-LEADLAG-001-v1.

Only purged training and chronological-validation history is scored. The final
20% historical OOS tail and genuine-forward evidence remain locked.
"""
from __future__ import annotations

import argparse
import copy
import gzip
import json
import math
import os
import statistics
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from profitability_learning.analytics import analyze
from profitability_learning.contracts import COSTS, fingerprint, net_pnl
from research_artifact import seal_research_payload, sha256_hex
from volatility_breakout_selection import LOCKED_OOS, _split_bounds

ROOT = Path(__file__).resolve().parent
CONTRACT_PATH = ROOT / "orchestration" / "disc_btc_leadlag_001.json"
DATASET_PATH = ROOT / "orchestration/evidence/liquidity_meanrev_001_cache/dataset.json.gz"
FROZEN_CONTRACT_SHA256 = "8d991f723c65a583b1d3188aa7f4f77493d08cfd198ee6aa4be508294d770989"
FROZEN_DATASET_SHA256 = "047c098bb2957557f8344ca30c32339ecac01b5067ae424b147d21c9e9caaf9f"
FROZEN_AT = "2026-09-19T08:47:59+00:00"
DEFAULT_GENERATED_AT = datetime(2026, 9, 19, 10, 0, tzinfo=timezone.utc)
HOUR_MS = 3_600_000


def _iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).isoformat()


def _validate_contract(contract: dict[str, Any]) -> dict[str, Any]:
    payload = dict(contract)
    payload.pop("contract_sha256", None)
    payload.pop("contract_fingerprint_definition", None)
    if sha256_hex(payload) != contract.get("contract_sha256") or contract.get("contract_sha256") != FROZEN_CONTRACT_SHA256:
        raise RuntimeError("selection contract fingerprint mismatch")
    if contract.get("fingerprint_id") != "DISC-BTC-LEADLAG-001-v1":
        raise RuntimeError("unexpected lead-lag fingerprint")
    if contract.get("chronology", {}).get("untouched_oos") != "LOCKED":
        raise RuntimeError("untouched OOS must remain locked")
    if contract.get("source", {}).get("asset_substitution_allowed") is not False:
        raise RuntimeError("asset substitution is forbidden")
    if contract.get("search_breadth", {}).get("parameter_optimization_allowed") is not False:
        raise RuntimeError("parameter optimization is forbidden")
    if contract.get("sequential_reuse_control", {}).get("reused_history_can_support_promotion") is not False:
        raise RuntimeError("reused history cannot support promotion")
    return contract


def _load_contract(path: Path = CONTRACT_PATH) -> dict[str, Any]:
    return _validate_contract(json.loads(path.read_text(encoding="utf-8")))


def _validate_row(raw: dict[str, Any]) -> dict[str, float | int]:
    try:
        row = {"ts": int(raw["ts"]), **{key: float(raw[key]) for key in ("open", "high", "low", "close", "volume", "quote_volume")}}
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError("malformed history row") from exc
    values = [float(row[key]) for key in ("open", "high", "low", "close", "volume", "quote_volume")]
    if row["ts"] <= 0 or row["ts"] % HOUR_MS or not all(math.isfinite(value) for value in values):
        raise ValueError("timestamps must be finite UTC hourly grid values")
    if min(float(row[key]) for key in ("open", "high", "low", "close")) <= 0 or row["volume"] < 0 or row["quote_volume"] < 0:
        raise ValueError("impossible market value")
    if row["high"] < max(row["open"], row["close"], row["low"]) or row["low"] > min(row["open"], row["close"], row["high"]):
        raise ValueError("impossible OHLC ordering")
    return row


def _validate_histories(histories: dict[str, list[dict[str, Any]]], contract: dict[str, Any], *, exact_dataset: bool) -> dict[str, list[dict[str, float | int]]]:
    required = list(contract["source"]["required_instruments"])
    if set(histories) != set(required):
        raise ValueError("exact required instrument set is mandatory")
    clean: dict[str, list[dict[str, float | int]]] = {}
    timestamps: list[int] | None = None
    for asset in required:
        rows = [_validate_row(row) for row in histories[asset]]
        ts = [int(row["ts"]) for row in rows]
        if any(b - a != HOUR_MS for a, b in zip(ts, ts[1:])):
            raise ValueError("missing, duplicate, or non-hourly timestamp")
        if timestamps is None:
            timestamps = ts
        elif ts != timestamps:
            raise ValueError("histories must have exact common timestamps")
        clean[asset] = rows
    if exact_dataset:
        source = contract["source"]
        if len(required) * len(timestamps or []) != int(source["normalized_row_count"]):
            raise ValueError("frozen dataset row count mismatch")
        if not timestamps or _iso(timestamps[0]) != source["coverage_start_utc"] or _iso(timestamps[-1]) != source["coverage_end_utc"]:
            raise ValueError("frozen dataset coverage mismatch")
    return clean


def _returns(rows: list[dict[str, float | int]]) -> list[float | None]:
    return [None] + [float(rows[i]["close"]) / float(rows[i - 1]["close"]) - 1 for i in range(1, len(rows))]


def _signal(histories: dict[str, list[dict[str, float | int]]], i: int, follower: str, contract: dict[str, Any], *, gap_min: float, baseline: bool = False, returns_cache: dict[str, list[float | None]] | None = None) -> dict[str, Any]:
    rule = contract["primary_rule"]
    window = int(rule["trailing_window_bars"])
    if i < window + 1:
        return {"eligible": False, "reason": "WARMUP"}
    btc = histories["BTC-USDT-SWAP"]
    follower_rows = histories[follower]
    returns_cache = returns_cache or {"BTC-USDT-SWAP": _returns(btc), follower: _returns(follower_rows)}
    btc_returns, follower_returns = returns_cache["BTC-USDT-SWAP"], returns_cache[follower]
    x = [float(value) for value in btc_returns[i - window:i]]
    y = [float(value) for value in follower_returns[i - window:i]]
    sigma = statistics.stdev(x)
    btc_return = float(btc_returns[i])
    if sigma <= 0 or not (abs(btc_return) > float(rule["leader_impulse_absolute_return_floor"]) and abs(btc_return) > float(rule["leader_impulse_sigma_multiple"]) * sigma):
        return {"eligible": False, "reason": "NO_BTC_IMPULSE"}
    direction = 1 if btc_return > 0 else -1
    regime_closes = [float(row["close"]) for row in btc[i - 167:i + 1]]
    regime = "BULL" if float(btc[i]["close"]) >= statistics.mean(regime_closes) else "BEAR"
    if baseline:
        return {"eligible": True, "direction": "LONG" if direction > 0 else "SHORT", "direction_value": direction, "btc_return": btc_return, "sigma": sigma, "beta": None, "follower_return": None, "gap": None, "regime": regime}
    denominator = sum(value * value for value in x)
    if denominator <= 0:
        return {"eligible": False, "reason": "ZERO_BETA_DENOMINATOR"}
    beta = sum(a * b for a, b in zip(x, y)) / denominator
    follower_return = float(follower_returns[i])
    gap = direction * (beta * btc_return - follower_return)
    result = {
        "eligible": True,
        "direction": "LONG" if direction > 0 else "SHORT",
        "direction_value": direction,
        "btc_return": btc_return,
        "sigma": sigma,
        "beta": beta,
        "follower_return": follower_return,
        "gap": gap,
        "regime": regime,
    }
    if not float(rule["follower_beta_min"]) <= beta <= float(rule["follower_beta_max"]):
        return {**result, "eligible": False, "reason": "BETA_OUTSIDE_RANGE"}
    if direction * follower_return < -0.005:
        return {**result, "eligible": False, "reason": "OPPOSITE_MOVE_GUARD"}
    if gap < gap_min:
        return {**result, "eligible": False, "reason": "UNDERREACTION_GAP"}
    return result


def _learning_strategy(contract: dict[str, Any], gap_min: float, baseline: bool) -> dict[str, Any]:
    rule = contract["primary_rule"]
    components = [
        {"kind": "leader_impulse", "rule": "completed BTC hourly return exceeds fixed absolute and trailing-sigma floors", "parameters": {"absolute_floor": rule["leader_impulse_absolute_return_floor"], "sigma_multiple": rule["leader_impulse_sigma_multiple"], "window": rule["trailing_window_bars"]}, "economic_reason": "BTC is the predeclared price-discovery leader."},
        {"kind": "execution", "rule": "next follower open entry and fixed six-hour exit", "parameters": {"holding_bars": rule["holding_period_bars"]}, "economic_reason": "Avoid same-bar execution and cap the diffusion horizon."},
    ]
    if not baseline:
        components.insert(1, {"kind": "underreaction", "rule": "through-origin beta-implied follower gap", "parameters": {"gap_min": gap_min, "beta_min": rule["follower_beta_min"], "beta_max": rule["follower_beta_max"]}, "economic_reason": "Test incremental delayed follower price discovery."})
    return {"mechanism": "BTC-to-follower delayed price discovery", "assets": list(contract["source"]["fixed_follower_instruments"]), "timeframe": "1H", "execution_rule": "NEXT_OPEN_FIXED_6H", "components": components}


def _experiment_contract(contract: dict[str, Any], histories: dict[str, list[dict[str, float | int]]], start: int, end: int, split: str, generated_at: datetime, gap_min: float, baseline: bool) -> dict[str, Any]:
    strategy = _learning_strategy(contract, gap_min, baseline)
    ablations = ([fingerprint(component) for component in strategy["components"]
                  if component["kind"] == "underreaction"] if not baseline else [])
    return {
        "schema_version": 1, "strategy": strategy, "strategy_fingerprint": fingerprint(strategy),
        "family": "cross-asset delayed price discovery", "dataset_id": "OKX-BTC-ETH-SOL-1H-20260919",
        "dataset_sha256": FROZEN_DATASET_SHA256, "split": split, "initial_capital": 100000.0,
        "cost_model": "fixed 20bps round trip multiplied by stress; explicit fee/spread/slippage/carry",
        "provenance_ref": "orchestration/disc_btc_leadlag_001.json",
        "minimum_events": 12 if split == "TRAINING" else 5, "search_budget": 2,
        "mining_dimensions": [], "ablation_components": ablations, "interaction_pairs": [],
        "start": _iso(int(histories["BTC-USDT-SWAP"][start]["ts"])), "end": _iso(int(histories["BTC-USDT-SWAP"][end - 1]["ts"])),
        "frozen_at": FROZEN_AT, "outcomes_observed_at": generated_at.astimezone(timezone.utc).isoformat(),
        "retrospective_development_only": True, "historical_outcomes_inspected_before_freeze": False,
        "historical_reuse_classification": "EXPLORATORY_DEVELOPMENT_ONLY", "no_external_flows": True,
        "closed_portfolio": True, "point_in_time_verified": True, "max_feature_age_seconds": 0,
        "purge_seconds": 24 * 3600, "embargo_seconds": 24 * 3600,
    }


def _simulate_segment(histories: dict[str, list[dict[str, float | int]]], start: int, end: int, contract: dict[str, Any], *, split: str, gap_min: float, baseline: bool, cost_multiplier: float, generated_at: datetime, signal_cache: dict[tuple[int, str], dict[str, Any]] | None = None) -> dict[str, Any]:
    learning_contract = _experiment_contract(contract, histories, start, end, split, generated_at, gap_min, baseline)
    followers = list(contract["source"]["fixed_follower_instruments"])
    component_bps = contract["costs"]["base_component_bps_round_trip"]
    capital = float(learning_contract["initial_capital"])
    active: dict[str, dict[str, Any]] = {}
    returns_cache = {asset: _returns(rows) for asset, rows in histories.items()}
    trades: list[dict[str, Any]] = []
    equity = [{"timestamp": learning_contract["start"], "nav": capital, "gross_exposure": 0.0}]

    def marks(index: int, use_open: bool = False) -> tuple[float, float]:
        unrealized = exposure = 0.0
        price_key = "open" if use_open else "close"
        for follower, position in active.items():
            price = float(histories[follower][index][price_key])
            signed = position["direction_value"] * position["notional"] * (price / position["entry_price"] - 1)
            unrealized += signed
            exposure += abs(position["notional"] * price / position["entry_price"])
        return capital + unrealized, exposure

    for index in range(start + 1, end):
        # Eligibility is decided at the previous completed close.  A position
        # that is still open then cannot make a new signal eligible merely
        # because it exits at the following entry open.
        active_at_decision = set(active)
        for follower in sorted(list(active)):
            position = active[follower]
            if position["exit_index"] != index:
                continue
            exit_price = float(histories[follower][index]["open"])
            gross = position["direction_value"] * position["notional"] * (exit_price / position["entry_price"] - 1)
            costs = {key: position["notional"] * float(component_bps[key]) * cost_multiplier / 10_000 for key in COSTS}
            exit_cost = sum(costs.values()) - position["entry_cost"]
            capital += gross - exit_cost
            trade = {key: value for key, value in position.items() if key not in {"direction_value", "entry_price", "exit_index", "entry_cost"}}
            trade.update(exit_at=_iso(int(histories[follower][index]["ts"])), gross_pnl=gross, costs=costs)
            trades.append(trade)
            del active[follower]

        signal_index = index - 1
        candidates = []
        if signal_index >= max(start, int(contract["chronology"]["minimum_warmup_bars"])):
            for follower in followers:
                if (follower in active_at_decision or follower in active
                        or index + int(contract["primary_rule"]["holding_period_bars"]) >= end):
                    continue
                signal = signal_cache[(signal_index, follower)] if signal_cache is not None else _signal(histories, signal_index, follower, contract, gap_min=gap_min, baseline=baseline, returns_cache=returns_cache)
                if signal.get("eligible"):
                    candidates.append((follower, signal))
        decision_nav, current_exposure = marks(index, use_open=True)
        notional = decision_nav * float(contract["portfolio_economics"]["per_position_nav_fraction"])
        capacity = int(contract["portfolio_economics"]["max_concurrent_positions"]) - len(active)
        max_gross = decision_nav * float(contract["portfolio_economics"]["max_gross_exposure_nav_fraction"])
        for follower, signal in candidates[:max(0, capacity)]:
            if current_exposure + notional > max_gross + 1e-9:
                continue
            entry_price = float(histories[follower][index]["open"])
            entry_cost = notional * (float(component_bps["fees"]) + float(component_bps["spread"]) + float(component_bps["slippage"])) * cost_multiplier / 20_000
            capital -= entry_cost
            current_exposure += notional
            decision_at = _iso(int(histories["BTC-USDT-SWAP"][signal_index]["ts"]))
            entry_at = _iso(int(histories[follower][index]["ts"]))
            event_id = f"BTC-USDT-SWAP|{decision_at}|BTC_{signal['direction']}"
            active[follower] = {
                "trade_id": f"{split}|{follower}|{decision_at}|{gap_min:g}|{cost_multiplier:g}",
                "event_id": event_id, "decision_at": decision_at, "entry_at": entry_at,
                "asset": follower, "timeframe": "1H", "direction": signal["direction"], "notional": notional,
                "features": {name: {"value": value, "available_at": decision_at} for name, value in {
                    "regime": signal["regime"], "beta_band": "OMITTED" if signal["beta"] is None else f"{signal['beta']:.6f}",
                    "gap_band": "OMITTED" if signal["gap"] is None else f"{signal['gap']:.6f}", "btc_direction": signal["direction"],
                }.items()},
                "direction_value": signal["direction_value"], "entry_price": entry_price,
                "exit_index": index + int(contract["primary_rule"]["holding_period_bars"]), "entry_cost": entry_cost,
            }
        nav, exposure = marks(index)
        equity.append({"timestamp": _iso(int(histories["BTC-USDT-SWAP"][index]["ts"])), "nav": nav, "gross_exposure": exposure})
    if active:
        raise RuntimeError("segment ended with open positions")
    status = "PASSED" if len(trades) >= 2 else "REJECTED"
    return {"contract": learning_contract, "status": status, "failure_reasons": [] if status == "PASSED" else ["INSUFFICIENT_INDEPENDENT_EVENTS"], "trades": trades, "equity": equity}


def _trade_metrics(experiment: dict[str, Any], *, follower: str | None = None, half: int | None = None, regime: str | None = None) -> dict[str, Any]:
    rows = experiment["trades"]
    if follower is not None:
        rows = [trade for trade in rows if trade["asset"] == follower]
    if half is not None:
        midpoint = (datetime.fromisoformat(experiment["contract"]["start"]) + (datetime.fromisoformat(experiment["contract"]["end"]) - datetime.fromisoformat(experiment["contract"]["start"])) / 2)
        rows = [trade for trade in rows if (datetime.fromisoformat(trade["decision_at"]) < midpoint) == (half == 1)]
    if regime is not None:
        rows = [trade for trade in rows if trade["features"]["regime"]["value"] == regime]
    values = [net_pnl(trade) / trade["notional"] * 10_000 for trade in rows]
    gains, losses = sum(max(0.0, value) for value in values), abs(sum(min(0.0, value) for value in values))
    return {"trades": len(values), "mean_net_bps": sum(values) / len(values) if values else None, "profit_factor": (gains / losses if losses else None), "profit_factor_unbounded": bool(gains and not losses), "total_net_bps_additive": sum(values)}


def _gate(selection: dict[str, Any], contract: dict[str, Any]) -> tuple[bool, list[str]]:
    reasons: list[str] = []
    followers = contract["source"]["fixed_follower_instruments"]
    primary = selection["variants"]["primary_50bps"]["3x"]
    baseline = selection["variants"]["baseline"]["3x"]
    for follower in followers:
        train, validation = primary["training"]["followers"][follower], primary["validation"]["followers"][follower]
        base = baseline["validation"]["followers"][follower]
        checks = [(train["trades"] >= 12, "TRAIN_SAMPLE"), (validation["trades"] >= 5, "VALIDATION_SAMPLE"), (train["mean_net_bps"] is not None and train["mean_net_bps"] > 0, "TRAIN_EXPECTANCY"), (validation["mean_net_bps"] is not None and validation["mean_net_bps"] > 0, "VALIDATION_EXPECTANCY"), (validation["profit_factor_unbounded"] or (validation["profit_factor"] is not None and validation["profit_factor"] > 1), "VALIDATION_PROFIT_FACTOR"), (validation["mean_net_bps"] is not None and base["mean_net_bps"] is not None and validation["mean_net_bps"] >= base["mean_net_bps"], "INCREMENTAL_VALUE")]
        reasons.extend(f"{follower}:{name}" for ok, name in checks if not ok)
    pooled_train, pooled_validation = primary["training"]["pooled"], primary["validation"]["pooled"]
    pooled_base = baseline["validation"]["pooled"]
    checks = [(pooled_train["trades"] >= 24, "POOLED_TRAIN_SAMPLE"), (pooled_validation["trades"] >= 10, "POOLED_VALIDATION_SAMPLE"), (pooled_train["mean_net_bps"] is not None and pooled_train["mean_net_bps"] > 0, "POOLED_TRAIN_EXPECTANCY"), (pooled_validation["mean_net_bps"] is not None and pooled_validation["mean_net_bps"] > 0, "POOLED_VALIDATION_EXPECTANCY"), (pooled_validation["profit_factor_unbounded"] or (pooled_validation["profit_factor"] is not None and pooled_validation["profit_factor"] > 1), "POOLED_VALIDATION_PROFIT_FACTOR"), (pooled_validation["mean_net_bps"] is not None and pooled_base["mean_net_bps"] is not None and pooled_validation["mean_net_bps"] >= pooled_base["mean_net_bps"], "POOLED_INCREMENTAL_VALUE")]
    reasons.extend(name for ok, name in checks if not ok)
    for name in ("sensitivity_35bps", "sensitivity_65bps"):
        variant = selection["variants"][name]["3x"]
        for segment in ("training", "validation"):
            metric = variant[segment]["pooled"]
            floor = 16 if segment == "training" else 6
            if metric["trades"] < floor or metric["mean_net_bps"] is None or metric["mean_net_bps"] <= 0:
                reasons.append(f"{name}:{segment.upper()}_FALSIFIER")
    for half in ("first_half", "second_half"):
        metric = primary["validation"][half]
        if metric["mean_net_bps"] is None or metric["mean_net_bps"] <= -20:
            reasons.append(f"VALIDATION_{half.upper()}_INSTABILITY")
    for regime in ("BULL", "BEAR"):
        metric = primary["validation"]["regimes"][regime]
        if metric["trades"] >= 5 and (metric["mean_net_bps"] is None or metric["mean_net_bps"] <= -60):
            reasons.append(f"{regime}_REGIME_CATASTROPHIC")
    return not reasons, reasons


def evaluate_selection_from_histories(histories: dict[str, list[dict[str, Any]]], *, contract: dict[str, Any] | None = None, generated_at: datetime | None = None) -> dict[str, Any]:
    contract = _load_contract() if contract is None else _validate_contract(contract)
    generated_at = generated_at or DEFAULT_GENERATED_AT
    base = {"hypothesis_id": contract["hypothesis_id"], "fingerprint_id": contract["fingerprint_id"], "contract_sha256": contract["contract_sha256"], "research_only": True, "trade_authority": False, "promotion_authority": False, "automatic_execution_authority": False, "broker_connected": False, "untouched_oos": dict(LOCKED_OOS), "untouched_oos_opened": False, "genuine_forward_opened": False}
    try:
        clean = _validate_histories(histories, contract, exact_dataset=False)
        minimum = int(contract["source"]["minimum_history_bars_per_instrument"])
        if len(next(iter(clean.values()))) < minimum:
            raise ValueError(f"INSUFFICIENT_HISTORY:{len(next(iter(clean.values())))}<{minimum}")
        bounds = _split_bounds(len(next(iter(clean.values()))), contract)
    except (ValueError, StopIteration) as exc:
        pre_oos_pass = False
        return {**base, "data_integrity_ok": False, "data_errors": [str(exc)],
                "variants": {}, "screen_status": "INSUFFICIENT_EVIDENCE",
                "economic_pre_oos_pass": pre_oos_pass,
                "failure_reasons": ["DATA_INTEGRITY_OR_HISTORY"]}
    variants = {"baseline": (0.0, True), "sensitivity_35bps": (0.0035, False), "primary_50bps": (0.005, False), "sensitivity_65bps": (0.0065, False)}
    output: dict[str, Any] = {}
    rich: dict[str, Any] = {}
    baseline_training: dict[str, Any] | None = None
    for name, (gap, baseline) in variants.items():
        returns_cache = {asset: _returns(rows) for asset, rows in clean.items()}
        signal_cache = {
            (index, follower): _signal(clean, index, follower, contract, gap_min=gap, baseline=baseline, returns_cache=returns_cache)
            for index in range(max(int(contract["chronology"]["minimum_warmup_bars"]), bounds["train_start"]), bounds["validation_end"])
            for follower in contract["source"]["fixed_follower_instruments"]
        }
        output[name] = {}
        for multiplier in contract["costs"]["stress_multipliers"]:
            by_segment = {}
            for segment, split, start_key, end_key in (("training", "TRAINING", "train_start", "train_end"), ("validation", "CHRONOLOGICAL_VALIDATION", "validation_start", "validation_end")):
                experiment = _simulate_segment(clean, bounds[start_key], bounds[end_key], contract, split=split, gap_min=gap, baseline=baseline, cost_multiplier=float(multiplier), generated_at=generated_at, signal_cache=signal_cache)
                metrics = {"pooled": _trade_metrics(experiment), "followers": {follower: _trade_metrics(experiment, follower=follower) for follower in contract["source"]["fixed_follower_instruments"]}, "first_half": _trade_metrics(experiment, half=1), "second_half": _trade_metrics(experiment, half=2), "regimes": {regime: _trade_metrics(experiment, regime=regime) for regime in ("BULL", "BEAR")}}
                by_segment[segment] = metrics
                if name == "primary_50bps" and float(multiplier) == 3.0:
                    rich[segment] = {"experiment": experiment}
                elif name == "baseline" and segment == "training" and float(multiplier) == 3.0:
                    baseline_training = experiment
            output[name][f"{float(multiplier):g}x"] = by_segment
    provisional = {"variants": output}
    passed, reasons = _gate(provisional, contract)
    for segment in rich.values():
        segment["experiment"]["status"] = "PASSED" if passed else "REJECTED"
        segment["experiment"]["failure_reasons"] = [] if passed else list(reasons)
        segment["analysis"] = analyze(segment["experiment"])
    if baseline_training is None:
        raise RuntimeError("missing frozen baseline ablation evidence")
    return {**base, "data_integrity_ok": True, "data_errors": [], "bounds": bounds,
            "variants": output, "rich_primary_max_stress": rich,
            "learning_artifacts": {"training_baseline_experiment": baseline_training},
            "screen_status": "EXPLORATORY_SCREEN_SURVIVES" if passed else "PRE_OOS_FAIL",
            "economic_pre_oos_pass": passed, "failure_reasons": reasons,
            "reused_history_can_support_promotion": False,
            "exact_next_action": ("Freeze genuine-forward observation strictly after 2026-09-19T03:00:00+00:00; require 20 independent BTC events and 8 trades per follower before review." if passed else "Record this exact fingerprint as rejected pre-OOS and pivot to a materially distinct mechanism without tuning v1.")}


def _training_ablation(selection: dict[str, Any]) -> dict[str, Any]:
    full = copy.deepcopy(selection["rich_primary_max_stress"]["training"]["experiment"])
    baseline = copy.deepcopy(selection["learning_artifacts"]["training_baseline_experiment"])
    contract = copy.deepcopy(full["contract"])
    omitted = list(contract["ablation_components"])
    if len(omitted) != 1:
        raise ValueError("exactly the frozen underreaction component may be ablated")
    full["contract"] = {**copy.deepcopy(contract), "ablation_components": [],
                        "interaction_pairs": []}
    baseline_strategy = baseline["contract"]["strategy"]
    baseline["contract"] = {
        **copy.deepcopy(contract),
        "strategy": baseline_strategy,
        "strategy_fingerprint": fingerprint(baseline_strategy),
        "ablation_components": [],
        "interaction_pairs": [],
    }
    return {
        "schema_version": 1,
        "contract": contract,
        "variants": [
            {"omitted": [], "experiment": full},
            {"omitted": omitted, "experiment": baseline},
        ],
        "research_only": True,
        "trade_authority": False,
        "promotion_authority": False,
        "automatic_execution_authority": False,
        "broker_connected": False,
    }


def persist_selection(selection: dict[str, Any]) -> dict[str, Any]:
    """Persist evaluator completion through the shared Phase-1 learning hook."""
    from profitability_learning.runtime import complete_experiment, factory_feedback

    training = selection["rich_primary_max_stress"]["training"]["experiment"]
    validation = selection["rich_primary_max_stress"]["validation"]["experiment"]
    return {
        "training": complete_experiment(training, ablation=_training_ablation(selection)),
        "validation": complete_experiment(validation),
        "factory_feedback": factory_feedback(),
        "research_only": True,
        "trade_authority": False,
        "promotion_authority": False,
        "automatic_execution_authority": False,
        "broker_connected": False,
    }


def _load_frozen_dataset(path: Path = DATASET_PATH) -> dict[str, Any]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        dataset = json.load(handle)
    if sha256_hex(dataset) != FROZEN_DATASET_SHA256:
        raise RuntimeError("frozen dataset identity mismatch")
    contract = _load_contract()
    if dataset.get("source") != "OKX /api/v5/market/history-candles" or dataset.get("bar") != "1H" or dataset.get("fixed_instruments") != contract["source"]["required_instruments"]:
        raise RuntimeError("frozen dataset provenance mismatch")
    _validate_histories(dataset["histories"], contract, exact_dataset=True)
    return dataset


def run(generated_at: datetime | None = None) -> dict[str, Any]:
    generated_at = generated_at or datetime.now(timezone.utc)
    dataset = _load_frozen_dataset()
    contract = _load_contract()
    selection = evaluate_selection_from_histories(dataset["histories"], contract=contract, generated_at=generated_at)
    manifest = {"normalized_rows_sha256": FROZEN_DATASET_SHA256, "row_count": sum(len(rows) for rows in dataset["histories"].values()), "per_instrument": {asset: {"rows": len(rows), "sha256": sha256_hex(rows), "start": _iso(int(rows[0]["ts"])), "end": _iso(int(rows[-1]["ts"]))} for asset, rows in sorted(dataset["histories"].items())}}
    payload = {"generated_at": generated_at.astimezone(timezone.utc).isoformat(), "contract_sha256": contract["contract_sha256"], "dataset_manifest": manifest, "selection": selection, "scientific_interpretation": ("The exact reused-history screen survived every frozen pre-OOS gate, but is exploratory only and cannot support promotion." if selection["economic_pre_oos_pass"] else "The exact frozen fingerprint failed at least one predeclared pre-OOS gate; no rescue or tuning is authorized."), "candidate_returns_inspected": True, "untouched_oos_opened": False, "genuine_forward_opened": False, "trade_authority": False, "promotion_authority": False}
    return seal_research_payload(payload)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", default="btc_leadlag_selection.json")
    parser.add_argument("--memory-db", required=True,
                        help="Existing initialized profitability-learning SQLite database")
    parser.add_argument("--generated-at", required=True,
                        help="UTC timestamp when the frozen outcomes were first evaluated")
    args = parser.parse_args()
    from profitability_learning.memory import Memory
    Memory(args.memory_db, create=False)
    os.environ["PROFITABILITY_LEARNING_DB"] = args.memory_db
    envelope = run(datetime.fromisoformat(args.generated_at))
    persistence = persist_selection(envelope["payload"]["selection"])
    output = Path(args.output)
    if output.suffix == ".gz":
        with gzip.open(output, "wt", encoding="utf-8") as handle:
            json.dump(envelope, handle, sort_keys=True, separators=(",", ":"), allow_nan=False)
    else:
        output.write_text(json.dumps(envelope, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    result = envelope["payload"]["selection"]
    print(json.dumps({"fingerprint_id": result["fingerprint_id"],
                      "screen_status": result["screen_status"],
                      "economic_pre_oos_pass": result["economic_pre_oos_pass"],
                      "untouched_oos_opened": result["untouched_oos_opened"],
                      "training_experiment_id": persistence["training"]["experiment_id"],
                      "validation_experiment_id": persistence["validation"]["experiment_id"],
                      "persistence_status": persistence["training"]["persistence_status"]},
                     sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
