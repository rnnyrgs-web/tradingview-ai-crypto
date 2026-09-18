"""Cross-engine evidence reconciliation.

Agreement between engines is a robustness check, never a promotion shortcut.
"""

from __future__ import annotations


REQUIRED_METRICS = ("trades", "avg_trade_pct", "max_drawdown_pct")


def reconcile(engine_results: dict, required=("vectorbt", "nautilus", "lean")) -> dict:
    missing = [name for name in required if name not in engine_results]
    invalid = []
    contract_ids = set()
    for name, result in engine_results.items():
        if not isinstance(result, dict) or result.get("ok") is not True:
            invalid.append(name)
            continue
        contract_id = str(result.get("contract_fingerprint") or "")
        if not contract_id:
            invalid.append(name)
            continue
        contract_ids.add(contract_id)
        metrics = result.get("metrics") or {}
        if any(metric not in metrics for metric in REQUIRED_METRICS):
            invalid.append(name)
    comparable = not missing and not invalid and len(contract_ids) == 1
    return {
        "ok": comparable,
        "research_only": True,
        "trade_authority": False,
        "promotion_authority": False,
        "missing_engines": missing,
        "invalid_engines": invalid,
        "same_contract": len(contract_ids) == 1 and bool(contract_ids),
        "status": "COMPARABLE_RESEARCH_EVIDENCE" if comparable else "WAIT_RESEARCH_ONLY",
        "note": "Cross-engine agreement is corroboration only; canonical untouched-OOS and genuine forward gates still apply.",
    }
