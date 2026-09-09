"""Research-only attribution of resolved forecast mistakes to falsifiable buckets."""

from __future__ import annotations

from collections import Counter
from math import isfinite

from selective_precision import _independent_rows
from signal_development import objective_reference


def _finite(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if isfinite(value) else None


def _independent(rows):
    out = []
    for horizon in ("24h", "7d"):
        resolved = [r for r in (rows or []) if r.get("horizon") == horizon and r.get("resolved_at") and isinstance(r.get("correct"), bool)]
        out.extend(_independent_rows(resolved, horizon))
    return out


def _micro(row):
    value = row.get("microstructure")
    return value if isinstance(value, dict) else {}


def _reason(row):
    if row.get("correct") is True:
        return "correct"
    directional_return = _finite(row.get("directional_return_pct"))
    if directional_return is not None and directional_return > 0:
        return "label_or_payoff_mismatch_review"
    if row.get("data_quality_ok") is False or row.get("stale_data") is True:
        return "data_quality_or_staleness"
    if row.get("strategy_deteriorating") is True or row.get("deterioration_state") in {"DETERIORATING", "FAIL"}:
        return "strategy_deterioration"
    regime = str(row.get("market_regime") or "unknown").upper()
    expected_regime = str(row.get("strategy_expected_regime") or "").upper()
    if expected_regime and regime != "UNKNOWN" and expected_regime != regime:
        return "regime_mismatch"
    m = _micro(row)
    spread = _finite(m.get("spread_bps", row.get("spread_bps")))
    depth = _finite(m.get("visible_quote_depth", row.get("visible_quote_depth")))
    if spread is not None and spread >= 35:
        return "execution_spread_stress"
    if depth is not None and depth <= 1000:
        return "thin_visible_liquidity"
    score = _finite(row.get("score"))
    if score is not None and score >= 80:
        return "high_confidence_false_positive"
    if row.get("cross_asset_shock") is True or row.get("market_shock") is True:
        return "cross_asset_market_shock"
    return "unexplained_directional_error"


def build_error_attribution(rows):
    selected = _independent(rows)
    errors = [row for row in selected if row.get("correct") is False]
    counts = Counter(_reason(row) for row in errors)
    priorities = []
    for reason, count in counts.most_common():
        priorities.append({
            "reason": reason,
            "independent_error_samples": count,
            "share_of_errors": round(count / len(errors), 4) if errors else None,
            "next_test": f"Predeclare a restrictive or alternative hypothesis for {reason} and validate chronologically on fresh independent evidence.",
            "trade_authority": False,
        })
    return {
        "ok": True,
        "research_only": True,
        "objective": objective_reference("resolved-error-attribution", "learning_diagnostics"),
        "independent_samples": len(selected),
        "independent_errors": len(errors),
        "attribution_counts": dict(counts),
        "research_priorities": priorities,
        "policy": "Attribution proposes falsifiable research questions only; ambiguous cases remain unexplained rather than fabricated.",
        "trade_authority": False,
        "promotion_authority": False,
        "automatic_strategy_mutation": False,
    }
