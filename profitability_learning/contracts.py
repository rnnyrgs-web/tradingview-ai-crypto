"""Versioned JSON contracts and deterministic identities for learning evidence."""
from __future__ import annotations

from datetime import datetime, timezone
from hashlib import sha256
import json
import math

DEVELOPMENT = {"DEVELOPMENT", "TRAINING"}
SPLITS = DEVELOPMENT | {"CHRONOLOGICAL_VALIDATION", "RELEASED_OOS", "FORWARD"}
COSTS = ("fees", "spread", "slippage", "funding_carry")
SAFE = {"research_only": True, "trade_authority": False, "promotion_authority": False,
        "automatic_execution_authority": False, "broker_connected": False}
MAX_TRADES = 100_000


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False)


def fingerprint(value):
    return sha256(canonical(value).encode()).hexdigest()


def number(value, name, *, minimum=None):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    try:
        good = math.isfinite(value)
    except OverflowError:
        good = False
    if not good or (minimum is not None and value < minimum):
        raise ValueError(f"{name} must be finite and >= {minimum}")
    return float(value)


def integer(value, name, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError(f"{name} must be an integer in [{low}, {high}]")
    return value


def text(value, name):
    if not isinstance(value, str) or not value.strip() or len(value) > 4096:
        raise ValueError(f"{name} must be nonempty bounded text")
    return value


def timestamp(value):
    try:
        dt = datetime.fromisoformat(text(value, "timestamp"))
    except (ValueError, TypeError) as exc:
        raise ValueError("invalid timestamp") from exc
    if dt.tzinfo is None:
        raise ValueError("timezone required")
    return dt.astimezone(timezone.utc)


def validate_strategy(strategy):
    if not isinstance(strategy, dict):
        raise ValueError("strategy must be an object")
    for name in ("mechanism", "timeframe", "execution_rule"):
        text(strategy.get(name), name)
    assets = strategy.get("assets")
    if not isinstance(assets, list) or not assets or len(assets) != len(set(assets)):
        raise ValueError("distinct assets required")
    for asset in assets:
        text(asset, "asset")
    components = strategy.get("components")
    if not isinstance(components, list) or not 1 <= len(components) <= 24:
        raise ValueError("1..24 strategy components required")
    for c in components:
        if not isinstance(c, dict) or set(c) != {"kind", "rule", "parameters", "economic_reason"}:
            raise ValueError("invalid component schema")
        for key in ("kind", "rule", "economic_reason"):
            text(c.get(key), key)
        if not isinstance(c["parameters"], dict):
            raise ValueError("component parameters must be an object")
        canonical(c)
    if len({fingerprint(c) for c in components}) != len(components):
        raise ValueError("duplicate components")
    return strategy


def validate_contract(c):
    if not isinstance(c, dict) or c.get("schema_version") != 1:
        raise ValueError("unknown contract schema")
    validate_strategy(c.get("strategy"))
    if c.get("strategy_fingerprint") != fingerprint(c["strategy"]):
        raise ValueError("strategy fingerprint mismatch")
    for key in ("family", "dataset_id", "provenance_ref", "cost_model"):
        text(c.get(key), key)
    digest = c.get("dataset_sha256")
    if not isinstance(digest, str) or len(digest) != 64 or any(x not in "0123456789abcdef" for x in digest):
        raise ValueError("dataset SHA256 required")
    if c.get("split") not in SPLITS:
        raise ValueError("unknown or protected split")
    start, end = timestamp(c.get("start")), timestamp(c.get("end"))
    frozen, observed = timestamp(c.get("frozen_at")), timestamp(c.get("outcomes_observed_at"))
    retrospective = c.get("retrospective_development_only") is True
    if retrospective:
        if c["split"] not in DEVELOPMENT | {"CHRONOLOGICAL_VALIDATION"}:
            raise ValueError("retrospective evidence is restricted to development splits")
        if c.get("historical_outcomes_inspected_before_freeze") is not False:
            raise ValueError("retrospective evidence requires an outcome-inspection disclosure")
        if c.get("historical_reuse_classification") != "EXPLORATORY_DEVELOPMENT_ONLY":
            raise ValueError("retrospective evidence requires exploratory-only classification")
        if not start < end <= frozen <= observed:
            raise ValueError("retrospective contract chronology invalid")
    elif not frozen < start < end <= observed:
        raise ValueError("contract freeze / observation chronology invalid")
    if c["split"] == "RELEASED_OOS":
        text(c.get("release_ref"), "independent OOS release reference")
    for flag in ("no_external_flows", "closed_portfolio", "point_in_time_verified"):
        if c.get(flag) is not True:
            raise ValueError(f"{flag} must be true")
    if number(c.get("initial_capital"), "initial_capital", minimum=0) <= 0:
        raise ValueError("positive initial capital required")
    integer(c.get("minimum_events"), "minimum_events", 2, MAX_TRADES)
    integer(c.get("search_budget"), "search_budget", 1, 256)
    for key in ("max_feature_age_seconds", "purge_seconds", "embargo_seconds"):
        number(c.get(key), key, minimum=0)
    dimensions = c.get("mining_dimensions")
    if not isinstance(dimensions, list) or len(dimensions) > 8 or len(dimensions) != len(set(dimensions)):
        raise ValueError("bounded distinct mining dimensions required")
    for dimension in dimensions:
        text(dimension, "dimension")
    ids = {fingerprint(x) for x in c["strategy"]["components"]}
    ablations = c.get("ablation_components")
    if not isinstance(ablations, list) or len(ablations) != len(set(ablations)) or not set(ablations) <= ids:
        raise ValueError("invalid predeclared ablation components")
    pairs = c.get("interaction_pairs")
    if not isinstance(pairs, list) or len(pairs) > 16:
        raise ValueError("invalid interaction pairs")
    for pair in pairs:
        if not isinstance(pair, list) or len(pair) != 2 or len(set(pair)) != 2 or not set(pair) <= set(ablations):
            raise ValueError("interaction must reference two ablated components")
    return c


def experiment_id(c):
    # Observation time isn't identity; changing it must not evade idempotency.
    return fingerprint({k: v for k, v in c.items() if k != "outcomes_observed_at"})


def net_pnl(trade):
    return trade["gross_pnl"] - sum(trade["costs"].values())


def validate_experiment(e):
    if not isinstance(e, dict):
        raise ValueError("experiment must be an object")
    c = validate_contract(e.get("contract"))
    if e.get("status") not in {"PASSED", "REJECTED", "INCONCLUSIVE", "INFRA_DATA_FAILURE"}:
        raise ValueError("invalid experiment status")
    reasons = e.get("failure_reasons")
    if not isinstance(reasons, list) or (e["status"] != "PASSED" and not reasons):
        raise ValueError("failed experiment requires interpretable reasons")
    for reason in reasons:
        text(reason, "failure reason")
    if e["status"] == "INFRA_DATA_FAILURE":
        if e.get("trades") or e.get("equity"):
            raise ValueError("infrastructure failure cannot carry economic evidence")
        return e
    trades, equity = e.get("trades"), e.get("equity")
    if not isinstance(trades, list) or len(trades) > MAX_TRADES:
        raise ValueError("invalid trade list")
    if not isinstance(equity, list) or not 2 <= len(equity) <= MAX_TRADES * 2:
        raise ValueError("reconciled equity series required")
    start, end = timestamp(c["start"]), timestamp(c["end"])
    seen = set()
    for t in trades:
        tid = text(t.get("trade_id"), "trade_id")
        if tid in seen:
            raise ValueError("duplicate trade")
        seen.add(tid)
        text(t.get("event_id"), "event_id")
        decision, entry, exit_at = (timestamp(t.get(k)) for k in ("decision_at", "entry_at", "exit_at"))
        if not start <= decision <= entry < exit_at <= end:
            raise ValueError("trade chronology outside declared window")
        number(t.get("gross_pnl"), "gross_pnl")
        number(t.get("notional"), "notional", minimum=0)
        if not isinstance(t.get("costs"), dict) or set(t["costs"]) != set(COSTS):
            raise ValueError("explicit fees/spread/slippage/funding_carry required")
        for key in COSTS:
            number(t["costs"][key], key, minimum=None if key == "funding_carry" else 0)
        if t.get("asset") not in c["strategy"]["assets"] or t.get("timeframe") != c["strategy"]["timeframe"]:
            raise ValueError("trade asset/timeframe outside contract")
        if t.get("direction") not in {"LONG", "SHORT"}:
            raise ValueError("invalid trade direction")
        features = t.get("features")
        if not isinstance(features, dict) or len(features) > 64:
            raise ValueError("bounded point-in-time feature map required")
        for name, feature in features.items():
            text(name, "feature name")
            if not isinstance(feature, dict) or set(feature) != {"value", "available_at"}:
                raise ValueError("feature value and availability required")
            text(feature["value"], "categorical feature value")
            age = (decision - timestamp(feature["available_at"])).total_seconds()
            if not 0 <= age <= c["max_feature_age_seconds"]:
                raise ValueError("future or stale pre-trade feature")
    previous, insolvent = None, False
    for row in equity:
        at = timestamp(row.get("timestamp"))
        nav = number(row.get("nav"), "nav", minimum=0)
        number(row.get("gross_exposure"), "gross_exposure", minimum=0)
        if not start <= at <= end or (previous is not None and at <= previous):
            raise ValueError("equity chronology invalid")
        if insolvent and nav > 0:
            raise ValueError("insolvent NAV cannot recover without external flows")
        insolvent = insolvent or nav == 0
        previous = at
    if timestamp(equity[0]["timestamp"]) != start or timestamp(equity[-1]["timestamp"]) != end:
        raise ValueError("equity must cover full contract window")
    capital = c["initial_capital"]
    tolerance = max(1e-8, capital * 1e-9)
    if abs(equity[0]["nav"] - capital) > tolerance or abs(equity[-1]["nav"] - capital - sum(net_pnl(t) for t in trades)) > tolerance:
        raise ValueError("equity/trade net P&L reconciliation failed")
    if equity[0]["gross_exposure"] or equity[-1]["gross_exposure"]:
        raise ValueError("closed portfolio requires flat endpoints")
    return e


def independent_blocks(trades):
    """Conservatively combine overlapping event intervals, including same event IDs."""
    by_event = {}
    for t in trades:
        by_event.setdefault(t["event_id"], []).append(t)
    spans = sorted((min(timestamp(t["entry_at"]) for t in rows),
                    max(timestamp(t["exit_at"]) for t in rows), key)
                   for key, rows in by_event.items())
    blocks = []
    end = None
    for start, stop, key in spans:
        if end is None or start > end:
            blocks.append([])
        blocks[-1].extend(by_event[key])
        end = max(end, stop) if end else stop
    return blocks
