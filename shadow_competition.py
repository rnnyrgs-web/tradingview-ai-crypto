"""Genuine-forward champion/challenger comparison.

A challenger is compared only against the incumbent on matched independent
future periods, using exact immutable strategy fingerprints and conservative
strategy-specific execution costs. This module cannot promote, sign, or trade.
It may only recommend further Strategy Registry / Production Risk review.
"""

from __future__ import annotations

import hashlib
import math
from datetime import datetime, timedelta, timezone


MIN_MATCHED_PERIODS = {"24h": 20, "7d": 12}
HORIZON_SPAN = {"24h": timedelta(hours=24), "7d": timedelta(days=7)}
BOOTSTRAP_RESAMPLES = 500
MIN_PAIRWISE_WIN_RATE = 0.55


def _parse_dt(value):
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None
    return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)


def _fingerprint(identity):
    return str((identity or {}).get("fingerprint") or "").strip().lower()


def _cost_pct(identity):
    try:
        bps = float((identity or {}).get("backtest_cost_bps"))
    except (TypeError, ValueError):
        return None
    if not math.isfinite(bps) or bps < 0:
        return None
    return bps * 3.0 / 100.0


def _stable_identity(row):
    return (
        str(row.get("scan_id") or ""),
        str(row.get("symbol") or ""),
        str(row.get("direction") or ""),
        str(row.get("score") or ""),
    )


def _independent_map(predictions, identity, horizon):
    """Return exact due-time keyed, full-horizon non-overlapping evidence.

    Fixed UTC day/week buckets can falsely label nearly identical forecast
    windows as independent when they straddle a calendar boundary. We instead
    reconstruct each immutable forecast window as ``due_at - horizon -> due_at``
    and greedily de-overlap without inspecting its outcome. Exact ``due_at`` is
    used as the matching key so champion and challenger are compared on the same
    future endpoint rather than merely the same calendar bucket.
    """
    fp = _fingerprint(identity)
    cost = _cost_pct(identity)
    span = HORIZON_SPAN.get(horizon)
    if len(fp) != 64 or cost is None or span is None:
        return {}

    valid = []
    for row in predictions or []:
        if str(row.get("horizon") or "") != horizon:
            continue
        if _fingerprint(row.get("strategy_identity")) != fp:
            continue
        if row.get("correct") is None:
            continue
        due = _parse_dt(row.get("due_at"))
        resolved = _parse_dt(row.get("resolved_at"))
        if due is None or resolved is None or resolved < due:
            continue
        try:
            ret = float(row.get("directional_return_pct"))
        except (TypeError, ValueError):
            continue
        if not math.isfinite(ret):
            continue
        origin = due - span
        valid.append((origin, due, _stable_identity(row), ret - cost))

    valid.sort(key=lambda item: (item[0], item[1], item[2]))
    selected = {}
    covered_until = None
    for origin, due, _stable, net in valid:
        if covered_until is not None and origin < covered_until:
            continue
        selected[due.isoformat()] = {"dt": due, "net_return_pct": net}
        covered_until = due
    return selected


def _bootstrap_mean_lower(values, seed_material):
    """Deterministic SHA-256 bootstrap without pseudo-random state."""
    if not values:
        return None
    n = len(values)
    seed = str(seed_material).encode("utf-8")
    means = []
    counter = 0
    for _ in range(BOOTSTRAP_RESAMPLES):
        sample = []
        for _ in range(n):
            digest = hashlib.sha256(seed + counter.to_bytes(8, "big")).digest()
            sample.append(values[int.from_bytes(digest[:8], "big") % n])
            counter += 1
        means.append(sum(sample) / n)
    means.sort()
    return means[max(0, int(0.05 * len(means)) - 1)]


def compare_challenger(predictions, champion_identity, challenger_identity, horizon):
    horizon = str(horizon or "")
    if horizon not in MIN_MATCHED_PERIODS:
        return {"passed": False, "reasons": ["unsupported_horizon"], "trade_authority": False}
    champion_fp = _fingerprint(champion_identity)
    challenger_fp = _fingerprint(challenger_identity)
    if len(champion_fp) != 64 or len(challenger_fp) != 64 or champion_fp == challenger_fp:
        return {"passed": False, "reasons": ["invalid_or_non_distinct_fingerprints"], "trade_authority": False}

    champion = _independent_map(predictions, champion_identity, horizon)
    challenger = _independent_map(predictions, challenger_identity, horizon)
    matched_keys = sorted(set(champion) & set(challenger))
    champion_returns = [champion[k]["net_return_pct"] for k in matched_keys]
    challenger_returns = [challenger[k]["net_return_pct"] for k in matched_keys]
    differences = [c - b for c, b in zip(challenger_returns, champion_returns)]
    total = len(differences)
    reasons = []
    required = MIN_MATCHED_PERIODS[horizon]
    if total < required:
        reasons.append(f"matched_independent_periods<{required}")

    challenger_avg = sum(challenger_returns) / total if total else 0.0
    champion_avg = sum(champion_returns) / total if total else 0.0
    mean_advantage = sum(differences) / total if total else 0.0
    pairwise_wins = sum(1 for x in differences if x > 0)
    pairwise_win_rate = pairwise_wins / total if total else 0.0
    lower = _bootstrap_mean_lower(differences, f"{champion_fp}:{challenger_fp}:{horizon}:{total}") if total else None

    if challenger_avg <= 0:
        reasons.append("challenger_after_cost_expectancy<=0")
    if mean_advantage <= 0:
        reasons.append("challenger_mean_advantage<=0")
    if pairwise_win_rate < MIN_PAIRWISE_WIN_RATE:
        reasons.append("challenger_pairwise_win_rate<55pct")
    if lower is None or lower <= 0:
        reasons.append("bootstrap_5pct_mean_advantage<=0")

    return {
        "passed": not reasons,
        "reasons": reasons,
        "research_only": True,
        "trade_authority": False,
        "promotion_authority": False,
        "can_authorize_by_itself": False,
        "horizon": horizon,
        "champion_fingerprint": champion_fp,
        "challenger_fingerprint": challenger_fp,
        "matched_independent_periods": total,
        "minimum_matched_periods": required,
        "independence_policy": "matched_exact_due_at_full_horizon_non_overlapping_windows_only",
        "cost_policy": "subtract_3x_each_strategy_backtest_cost_before_pairwise_comparison",
        "champion_after_cost_mean_pct": round(champion_avg, 6),
        "challenger_after_cost_mean_pct": round(challenger_avg, 6),
        "challenger_mean_advantage_pct": round(mean_advantage, 6),
        "pairwise_win_rate_pct": round(pairwise_win_rate * 100.0, 2),
        "bootstrap_5pct_mean_advantage_pct": None if lower is None else round(lower, 6),
        "bootstrap_resamples": BOOTSTRAP_RESAMPLES,
        "eligible_for_strategy_registry_review": not reasons,
        "note": "Passing shadow competition is only a review recommendation. It cannot replace any promotion, forward-proof, or production-risk gate.",
    }
