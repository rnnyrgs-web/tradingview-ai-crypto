"""Forward shadow-evidence and real-money readiness assessment.

This module is deliberately read-only. It cannot place trades, promote a
strategy, sign evidence, or override production validation. Its purpose is to
turn the immutable prediction ledger into conservative forward-evidence gates
for later Strategy Registry / Production Risk review.
"""

from __future__ import annotations

from datetime import datetime, timezone
from math import sqrt


def _parse_dt(value):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not value:
        return None
    text = str(value).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _identity_matches(row, target_identity):
    if not target_identity:
        return True
    identity = row.get("strategy_identity") or {}
    for key in (
        "symbol",
        "production_horizon",
        "strategy_family",
        "strategy_version",
        "backtest_cost_bps",
        "research_code_sha256",
        "fingerprint",
    ):
        expected = target_identity.get(key)
        if expected not in (None, "") and identity.get(key) != expected:
            return False
    return True


def _bucket_seconds(horizon):
    return 7 * 24 * 3600 if str(horizon) == "7d" else 24 * 3600


def _independent_rows(rows, horizon):
    """Keep one resolved forecast per horizon-sized UTC evidence bucket.

    The production ledger can contain many overlapping forecasts. Counting all
    of them as independent evidence would create false confidence, so readiness
    uses at most one observation per horizon-sized time bucket.
    """
    seconds = _bucket_seconds(horizon)
    buckets = {}
    for row in rows:
        dt = _parse_dt(row.get("due_at") or row.get("resolved_at") or row.get("created_at"))
        if dt is None:
            continue
        bucket = int(dt.timestamp()) // seconds
        current = buckets.get(bucket)
        if current is None:
            buckets[bucket] = row
            continue
        current_dt = _parse_dt(current.get("resolved_at") or current.get("due_at") or current.get("created_at"))
        row_dt = _parse_dt(row.get("resolved_at") or row.get("due_at") or row.get("created_at"))
        if row_dt and (current_dt is None or row_dt > current_dt):
            buckets[bucket] = row
    return [buckets[k] for k in sorted(buckets)]


def _wilson_lower_bound(wins, total, z=1.959963984540054):
    if total <= 0:
        return 0.0
    p = wins / total
    denominator = 1.0 + z * z / total
    centre = p + z * z / (2.0 * total)
    margin = z * sqrt((p * (1.0 - p) + z * z / (4.0 * total)) / total)
    return max(0.0, (centre - margin) / denominator)


def _sequence_drawdown_pct(returns):
    equity = 100.0
    peak = equity
    max_dd = 0.0
    for ret in returns:
        equity *= 1.0 + float(ret) / 100.0
        peak = max(peak, equity)
        if peak > 0:
            max_dd = max(max_dd, (peak - equity) / peak * 100.0)
    return max_dd


def assess_shadow_readiness(predictions, target_identity=None, horizon=None):
    horizon = str(horizon or (target_identity or {}).get("production_horizon") or "24h")
    usable = []
    for row in predictions or []:
        if str(row.get("horizon") or "") != horizon:
            continue
        if not _identity_matches(row, target_identity):
            continue
        try:
            ret = float(row.get("directional_return_pct"))
        except (TypeError, ValueError):
            continue
        if row.get("correct") is None:
            continue
        copy = dict(row)
        copy["directional_return_pct"] = ret
        usable.append(copy)

    independent = _independent_rows(usable, horizon)
    returns = [row["directional_return_pct"] for row in independent]
    wins = sum(1 for row in independent if bool(row.get("correct")))
    total = len(independent)
    avg_return = sum(returns) / total if total else 0.0
    sum_return = sum(returns)
    win_rate = wins / total if total else 0.0
    wilson_lb = _wilson_lower_bound(wins, total)
    drawdown = _sequence_drawdown_pct(returns)
    recent = returns[-min(5, total):]
    recent_avg = sum(recent) / len(recent) if recent else 0.0

    canary_min = 6 if horizon == "7d" else 10
    scale_min = 12 if horizon == "7d" else 30
    canary_reasons = []
    if total < canary_min:
        canary_reasons.append(f"independent_periods<{canary_min}")
    if avg_return <= 0:
        canary_reasons.append("shadow_expectancy<=0")
    if win_rate <= 0.50:
        canary_reasons.append("shadow_win_rate<=50pct")
    if drawdown > 20.0:
        canary_reasons.append("shadow_sequence_drawdown>20pct")
    if recent and recent_avg <= 0:
        canary_reasons.append("recent_shadow_expectancy<=0")

    scale_reasons = list(canary_reasons)
    if total < scale_min:
        scale_reasons.append(f"independent_periods<{scale_min}_for_scale")
    if wilson_lb < 0.50:
        scale_reasons.append("wilson_95pct_lower_bound<50pct")
    if drawdown > 15.0:
        scale_reasons.append("shadow_sequence_drawdown>15pct_for_scale")

    return {
        "research_only": True,
        "trade_authority": False,
        "horizon": horizon,
        "raw_resolved_forecasts": len(usable),
        "independent_periods": total,
        "independence_policy": "at_most_one_resolved_forecast_per_horizon_sized_utc_bucket",
        "wins": wins,
        "win_rate_pct": round(win_rate * 100.0, 2),
        "wilson_95pct_lower_bound_pct": round(wilson_lb * 100.0, 2),
        "avg_directional_return_pct": round(avg_return, 5),
        "sum_directional_return_pct": round(sum_return, 5),
        "recent_avg_directional_return_pct": round(recent_avg, 5),
        "sequence_drawdown_pct": round(drawdown, 3),
        "eligible_for_tiny_canary_review": not canary_reasons,
        "tiny_canary_reasons": canary_reasons,
        "eligible_for_scale_review": not scale_reasons,
        "scale_reasons": scale_reasons,
        "note": (
            "Forward ledger evidence is an additional gate only. Tiny-canary or scale review still requires "
            "full research/OOS/robustness, Strategy Registry approval, Production Risk approval and live validation."
        ),
    }


def canary_review_decision(live_validation, shadow_assessment):
    """Combine existing promotion validation with shadow evidence, without authority."""
    reasons = []
    if not getattr(live_validation, "approved", False):
        reasons.append("live_strategy_not_promoted_and_verified")
    if not shadow_assessment.get("eligible_for_tiny_canary_review"):
        reasons.extend(shadow_assessment.get("tiny_canary_reasons") or ["shadow_readiness_failed"])
    return {
        "research_only": True,
        "trade_authority": False,
        "eligible_for_production_risk_canary_review": not reasons,
        "reasons": reasons,
        "canary_execution_enabled": False,
        "note": "This decision cannot execute capital. Production Risk must separately authorize and implement any canary.",
    }
