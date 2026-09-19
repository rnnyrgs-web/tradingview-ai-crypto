"""Point-in-time relative-impact features; missing denominators stay UNKNOWN."""

from __future__ import annotations

from profitability_learning.contracts import number, text, timestamp


RATIOS = {
    "flow_to_float": ("flow", "float"),
    "flow_to_market_cap": ("flow", "market_cap"),
    "flow_to_adv": ("flow", "adv"),
    "demand_to_liquidity": ("demand", "liquidity"),
    "issuance_to_float": ("issuance", "float"),
}


def _validate_metric(name, metric, cutoff):
    if metric is None:
        return None
    if not isinstance(metric, dict) or set(metric) != {"value", "unit", "observed_at", "available_at", "source_ref"}:
        raise ValueError(f"invalid {name} metric")
    value = number(metric["value"], name)
    text(metric["unit"], f"{name} unit")
    text(metric["source_ref"], f"{name} source")
    observed, available = timestamp(metric["observed_at"]), timestamp(metric["available_at"])
    if observed > available or available > cutoff:
        raise ValueError(f"{name} exceeds information cutoff")
    return {**metric, "value": value}


def derive_relative_impacts(metrics, *, information_cutoff):
    if not isinstance(metrics, dict):
        raise ValueError("metrics must be an object")
    cutoff = timestamp(information_cutoff)
    normalized = {name: _validate_metric(name, value, cutoff) for name, value in metrics.items()}
    result = {}
    for output, (numerator_name, denominator_name) in RATIOS.items():
        numerator, denominator = normalized.get(numerator_name), normalized.get(denominator_name)
        if numerator is None or denominator is None:
            result[output] = {"status": "UNKNOWN", "reason": "missing numerator or denominator"}
        elif numerator["unit"] != denominator["unit"]:
            result[output] = {"status": "UNKNOWN", "reason": "non-comparable units"}
        elif denominator["value"] <= 0:
            result[output] = {"status": "UNKNOWN", "reason": "non-positive denominator"}
        else:
            result[output] = {"status": "KNOWN", "value": round(numerator["value"] / denominator["value"], 12)}
    return result
