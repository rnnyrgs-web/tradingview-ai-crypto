"""Fail-closed cross-engine trade/equity reconciliation."""
from __future__ import annotations

from .evidence import finite_number, validate_trades


REQUIRED_METRICS = (
    "trades", "avg_trade_pct", "max_drawdown_pct", "return_pct",
    "win_rate", "ending_equity",
)


def _valid_result(name, result, expected_contract_fingerprint):
    if not isinstance(result, dict) or result.get("ok") is not True:
        return False
    if (result.get("engine") != name or result.get("research_only") is not True
            or result.get("trade_authority") is not False
            or result.get("promotion_authority") is not False):
        return False
    fingerprint = result.get("contract_fingerprint")
    if not isinstance(fingerprint, str) or not fingerprint.strip():
        return False
    if expected_contract_fingerprint is not None and fingerprint != expected_contract_fingerprint:
        return False
    metrics = result.get("metrics")
    if not isinstance(metrics, dict) or not all(finite_number(metrics.get(k)) for k in REQUIRED_METRICS):
        return False
    trades = result.get("trades")
    try:
        validate_trades(trades)
    except ValueError:
        return False
    return (type(metrics["trades"]) is int and metrics["trades"] == len(trades)
            and 0 <= metrics["win_rate"] <= 1 and metrics["max_drawdown_pct"] >= 0)


def reconcile(
    engine_results, required=("vectorbt", "nautilus", "lean"),
    price_tolerance=1e-8, pnl_tolerance=1e-6, metric_tolerance=1e-6,
    *, expected_contract_fingerprint=None,
):
    errors = []
    if (not isinstance(required, (tuple, list)) or len(required) < 2
            or not all(isinstance(n, str) and n for n in required)
            or len(set(required)) != len(required)):
        errors.append("at least two distinct required engines must be declared")
        required = ()
    if not isinstance(engine_results, dict):
        errors.append("engine results must be an object")
        engine_results = {}
    if not all(finite_number(t) and t >= 0 for t in (price_tolerance, pnl_tolerance, metric_tolerance)):
        errors.append("reconciliation tolerances must be finite and nonnegative")
    if expected_contract_fingerprint is not None and (
        not isinstance(expected_contract_fingerprint, str) or not expected_contract_fingerprint.strip()
    ):
        errors.append("expected contract fingerprint must be nonempty")

    missing = [n for n in required if n not in engine_results]
    invalid = [n for n in required if not _valid_result(
        n, engine_results.get(n), expected_contract_fingerprint,
    )]
    ids = {engine_results[n]["contract_fingerprint"] for n in required if n not in invalid}
    mismatches = []
    if not errors and not missing and not invalid and len(ids) == 1:
        base = engine_results[required[0]]
        for name in required[1:]:
            other = engine_results[name]
            if len(base["trades"]) != len(other["trades"]):
                mismatches.append(f"{name}:trade_count")
                continue
            for i, (a, b) in enumerate(zip(base["trades"], other["trades"])):
                for key in ("direction", "entry_ts", "exit_ts"):
                    if a[key] != b[key]:
                        mismatches.append(f"{name}:trade[{i}].{key}")
                for key in ("entry_price", "exit_price", "size", "fees", "pnl"):
                    tolerance = pnl_tolerance if key in ("fees", "pnl") else price_tolerance
                    if abs(a[key] - b[key]) > tolerance:
                        mismatches.append(f"{name}:trade[{i}].{key}")
            for key in REQUIRED_METRICS:
                if abs(base["metrics"][key] - other["metrics"][key]) > metric_tolerance:
                    mismatches.append(f"{name}:metric.{key}")

    ok = not errors and not missing and not invalid and len(ids) == 1 and not mismatches
    return {
        "ok": ok, "research_only": True, "trade_authority": False,
        "promotion_authority": False, "missing_engines": missing,
        "invalid_engines": invalid, "same_contract": len(ids) == 1 and not invalid,
        "mismatches": mismatches, "errors": errors,
        "status": "COMPARABLE_RESEARCH_EVIDENCE" if ok else "WAIT_RESEARCH_ONLY",
        "note": "Agreement is corroboration only; untouched-OOS and genuine forward gates still apply.",
    }
