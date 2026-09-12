"""Research-only clustered calibration challenger.

This module does not authorize live actions.  It estimates genuine-forward
sample strength without pretending that simultaneous crypto forecasts are
independent:

1. forecasts must be fully resolved with valid due/resolved chronology;
2. overlapping forecasts are removed independently per symbol;
3. the remaining cross-symbol observations are grouped into full-horizon time
   blocks under two alignments (0 and half a horizon);
4. each alignment uses a cluster-robust variance estimate plus a deterministic
   block bootstrap that resamples whole time blocks;
5. the more conservative alignment is reported.

The resulting ``effective_samples`` is descriptive research evidence only.
Canonical production calibration remains unchanged until this challenger is
separately validated and integrated through the normal safety gates.
"""

from __future__ import annotations

import hashlib
import math
from collections import defaultdict
from datetime import datetime, timedelta, timezone

from config import OPPORTUNITY_HORIZONS

MIN_EFFECTIVE_SAMPLES = 30
MIN_TIME_CLUSTERS = 8
BOOTSTRAP_REPLICATES = 1200
BIN_WIDTH = 10
HORIZON_SPAN = {
    "6h": timedelta(hours=6),
    "12h": timedelta(hours=12),
    "24h": timedelta(hours=24),
    "48h": timedelta(hours=48),
    "72h": timedelta(hours=72),
    "7d": timedelta(days=7),
}


def score_bin(score: float) -> tuple[int, int]:
    value = max(0.0, min(100.0, float(score)))
    lower = min(90, int(value // BIN_WIDTH) * BIN_WIDTH)
    return lower, lower + BIN_WIDTH


def _timestamp(value):
    if isinstance(value, datetime):
        dt = value
    elif isinstance(value, str) and value.strip():
        try:
            dt = datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    else:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _strategy_key(row):
    identity = row.get("strategy_identity")
    if isinstance(identity, dict):
        return str(identity.get("fingerprint") or identity.get("strategy_family") or "")
    return str(identity or "")


def _stable_key(row):
    return (
        str(row.get("symbol") or ""),
        str(row.get("scan_id") or ""),
        str(row.get("due_at") or ""),
        _strategy_key(row),
        str(row.get("direction") or ""),
        str(row.get("score") or ""),
    )


def _validated_rows(rows, horizon):
    span = HORIZON_SPAN.get(horizon)
    if span is None:
        return []
    valid = []
    for row in rows or []:
        if row.get("horizon") != horizon or not isinstance(row.get("correct"), bool):
            continue
        symbol = str(row.get("symbol") or "").strip().upper()
        due_at = _timestamp(row.get("due_at"))
        resolved_at = _timestamp(row.get("resolved_at"))
        if not symbol or due_at is None or resolved_at is None or resolved_at < due_at:
            continue
        origin = due_at - span
        valid.append({**row, "symbol": symbol, "_origin": origin, "_due": due_at})
    valid.sort(key=lambda row: (row["_origin"], row["_due"], _stable_key(row)))
    return valid


def per_symbol_non_overlapping(rows, horizon):
    """Greedily retain only non-overlapping full-horizon forecasts per symbol."""
    by_symbol = defaultdict(list)
    for row in _validated_rows(rows, horizon):
        by_symbol[row["symbol"]].append(row)

    selected = []
    for symbol in sorted(by_symbol):
        covered_until = None
        for row in by_symbol[symbol]:
            if covered_until is not None and row["_origin"] < covered_until:
                continue
            selected.append(row)
            covered_until = row["_due"]
    selected.sort(key=lambda row: (row["_origin"], row["symbol"], _stable_key(row)))
    return selected


def _cluster_rows(rows, horizon, offset_fraction):
    span = HORIZON_SPAN[horizon]
    span_seconds = span.total_seconds()
    offset_seconds = span_seconds * float(offset_fraction)
    buckets = defaultdict(list)
    for row in rows:
        origin_seconds = row["_origin"].timestamp()
        bucket = math.floor((origin_seconds - offset_seconds) / span_seconds)
        buckets[int(bucket)].append(row)
    return [buckets[key] for key in sorted(buckets)]


def _cluster_variance(clusters):
    total = sum(len(cluster) for cluster in clusters)
    if total <= 0:
        return 0.0, 0.0
    successes = sum(1 for cluster in clusters for row in cluster if row["correct"])
    p = successes / total
    g = len(clusters)
    if g <= 1:
        return p, float("inf")
    residual_squares = 0.0
    for cluster in clusters:
        s_g = sum(1 for row in cluster if row["correct"])
        n_g = len(cluster)
        residual_squares += (s_g - p * n_g) ** 2
    variance = (g / (g - 1.0)) * residual_squares / (total * total)
    return p, variance


def _effective_sample_size(p, variance, raw_n):
    if raw_n <= 0:
        return 0.0
    if not math.isfinite(variance) or variance <= 0.0 or p <= 0.0 or p >= 1.0:
        return 1.0
    value = p * (1.0 - p) / variance
    return max(1.0, min(float(raw_n), value))


def _bootstrap_seed(clusters, horizon, offset_fraction):
    material = [horizon, f"{offset_fraction:.3f}"]
    for cluster in clusters:
        material.extend("|".join(_stable_key(row)) for row in cluster)
    return hashlib.sha256("\n".join(material).encode("utf-8")).hexdigest()


def _deterministic_cluster_index(seed, replicate, draw, cluster_count):
    material = f"{seed}:{replicate}:{draw}".encode("utf-8")
    digest = hashlib.sha256(material).digest()
    return int.from_bytes(digest[:8], "big") % cluster_count


def _bootstrap_lower(clusters, horizon, offset_fraction, replicates=BOOTSTRAP_REPLICATES):
    g = len(clusters)
    if g < 2:
        return 0.0
    seed = _bootstrap_seed(clusters, horizon, offset_fraction)
    estimates = []
    for replicate in range(max(200, int(replicates))):
        successes = 0
        total = 0
        for draw in range(g):
            index = _deterministic_cluster_index(seed, replicate, draw, g)
            cluster = clusters[index]
            total += len(cluster)
            successes += sum(1 for row in cluster if row["correct"])
        estimates.append(successes / total if total else 0.0)
    estimates.sort()
    index = max(0, min(len(estimates) - 1, int(math.floor(0.025 * (len(estimates) - 1)))))
    return estimates[index]


def _alignment_assessment(rows, horizon, offset_fraction):
    clusters = _cluster_rows(rows, horizon, offset_fraction)
    p, variance = _cluster_variance(clusters)
    raw_n = sum(len(cluster) for cluster in clusters)
    n_eff = _effective_sample_size(p, variance, raw_n)
    lower = _bootstrap_lower(clusters, horizon, offset_fraction)
    return {
        "offset_fraction": offset_fraction,
        "time_clusters": len(clusters),
        "raw_symbol_nonoverlap_samples": raw_n,
        "effective_samples": round(n_eff, 3),
        "empirical_precision": round(p, 4) if raw_n else None,
        "cluster_bootstrap_95pct_lower": round(lower, 4) if raw_n else None,
        "cluster_robust_variance": round(variance, 10) if math.isfinite(variance) else None,
    }


def clustered_calibration_assessment(score, horizon, resolved, regime=None,
                                      minimum_effective_samples=MIN_EFFECTIVE_SAMPLES,
                                      minimum_time_clusters=MIN_TIME_CLUSTERS):
    """Return conservative V2 research evidence for one score-bin/horizon scope."""
    lower, upper = score_bin(score)
    comparable = [
        row for row in (resolved or [])
        if row.get("horizon") == horizon
        and lower <= float(row.get("score") or 0.0)
        and (float(row.get("score") or 0.0) < upper or upper == 100)
        and isinstance(row.get("correct"), bool)
    ]
    regime_rows = [row for row in comparable if row.get("market_regime") == regime]

    # Regime conditioning is used only after it has enough raw resolved rows to
    # avoid accidentally manufacturing apparent precision from a tiny subset.
    candidate_scope = regime_rows if len(regime_rows) >= minimum_effective_samples else comparable
    scope = "horizon_regime_score_bin" if candidate_scope is regime_rows else "horizon_score_bin"
    selected = per_symbol_non_overlapping(candidate_scope, horizon)

    alignments = [
        _alignment_assessment(selected, horizon, 0.0),
        _alignment_assessment(selected, horizon, 0.5),
    ] if horizon in HORIZON_SPAN else []

    if not alignments:
        conservative = {
            "time_clusters": 0,
            "raw_symbol_nonoverlap_samples": 0,
            "effective_samples": 0.0,
            "empirical_precision": None,
            "cluster_bootstrap_95pct_lower": None,
        }
    else:
        conservative = min(
            alignments,
            key=lambda item: (
                float(item.get("effective_samples") or 0.0),
                float(item.get("cluster_bootstrap_95pct_lower") or 0.0),
            ),
        )

    n_eff = float(conservative.get("effective_samples") or 0.0)
    clusters = int(conservative.get("time_clusters") or 0)
    ready = n_eff >= float(minimum_effective_samples) and clusters >= int(minimum_time_clusters)
    return {
        "version": "CALIBRATION_V2_CLUSTERED_RESEARCH_ONLY",
        "research_only": True,
        "trade_authority_added": False,
        "allows_live_action": False,
        "ready_for_research_comparison": bool(ready),
        "scope": scope,
        "horizon": horizon,
        "score_bin": [lower, upper],
        "raw_matching_rows": len(candidate_scope),
        "symbol_nonoverlap_samples": len(selected),
        "effective_samples": round(n_eff, 3),
        "minimum_effective_samples": int(minimum_effective_samples),
        "time_clusters": clusters,
        "minimum_time_clusters": int(minimum_time_clusters),
        "empirical_precision": conservative.get("empirical_precision"),
        "cluster_bootstrap_95pct_lower": conservative.get("cluster_bootstrap_95pct_lower"),
        "conservative_alignment_offset_fraction": conservative.get("offset_fraction"),
        "alignments": alignments,
        "sample_sufficiency_basis": "per_symbol_nonoverlap_plus_cross_asset_time_cluster_robust_effective_n",
        "production_calibration_unchanged": True,
    }


def calibration_v2_summary(resolved):
    """Research-only horizon summary; never used by the production action gate."""
    summaries = []
    for horizon in OPPORTUNITY_HORIZONS:
        rows = [row for row in (resolved or []) if row.get("horizon") == horizon and isinstance(row.get("correct"), bool)]
        selected = per_symbol_non_overlapping(rows, horizon)
        alignments = [
            _alignment_assessment(selected, horizon, 0.0),
            _alignment_assessment(selected, horizon, 0.5),
        ] if horizon in HORIZON_SPAN else []
        conservative = min(
            alignments,
            key=lambda item: (
                float(item.get("effective_samples") or 0.0),
                float(item.get("cluster_bootstrap_95pct_lower") or 0.0),
            ),
        ) if alignments else {}
        n_eff = float(conservative.get("effective_samples") or 0.0)
        cluster_count = int(conservative.get("time_clusters") or 0)
        summaries.append({
            "horizon": horizon,
            "raw_resolved_rows": len(rows),
            "symbol_nonoverlap_samples": len(selected),
            "effective_samples": round(n_eff, 3),
            "time_clusters": cluster_count,
            "empirical_precision": conservative.get("empirical_precision"),
            "cluster_bootstrap_95pct_lower": conservative.get("cluster_bootstrap_95pct_lower"),
            "ready_for_research_comparison": bool(n_eff >= MIN_EFFECTIVE_SAMPLES and cluster_count >= MIN_TIME_CLUSTERS),
        })
    return {
        "ok": True,
        "version": "CALIBRATION_V2_CLUSTERED_RESEARCH_ONLY",
        "research_only": True,
        "trade_authority_added": False,
        "production_calibration_unchanged": True,
        "policy": (
            "Per-symbol full-horizon non-overlap is preserved. Cross-symbol observations are "
            "discounted with whole-time-block cluster variance and deterministic cluster bootstrap; "
            "the worse of two horizon-block alignments is reported."
        ),
        "horizons": summaries,
    }
