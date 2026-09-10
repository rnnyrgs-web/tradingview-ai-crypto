"""Bounded research runner for the FFriZz-inspired secondary shadow system.

The runner intentionally remains separate from production opportunities and paper
trading. It scans a bounded liquid universe, computes current shadow signals,
performs fixed-rule chronological diagnostics, and can persist only genuine
SHADOW_BUY/SHADOW_SELL research forecasts to the canonical prediction ledger while
keeping the canonical production action explicitly WAIT so no trade authority is
created by shadow research.
"""

from __future__ import annotations

import json
import os
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

from db import insert_prediction_ledger
from ffrizz_secondary_signals import (
    FIXED_SIGNAL_THRESHOLD,
    FIXED_STRONG_THRESHOLD,
    HORIZON_ORDER,
    HORIZON_PROFILES,
    chronological_backtest,
    score_shadow_signal,
)
from market_data import build_universe, get_derivatives_history, get_history


MAX_UNIVERSE_SIZE = 20
DEFAULT_UNIVERSE_SIZE = 12
HISTORY_BARS = {"1H": 900, "4H": 900}
HORIZON_DELTAS = {
    "6h": timedelta(hours=6),
    "12h": timedelta(hours=12),
    "24h": timedelta(hours=24),
    "48h": timedelta(hours=48),
    "72h": timedelta(hours=72),
    "7d": timedelta(days=7),
}
PERSIST_ACTIONS = {"SHADOW_BUY", "SHADOW_SELL"}
SYSTEM_ID = "FFRIZZ_SECONDARY_V1"
FFRIZZ_SCAN_NAMESPACE = uuid.UUID("339a39c5-0d99-55f4-82d5-54b9c1cda1de")


def _int_env(name, default, low, high):
    return max(low, min(int(os.getenv(name, str(default))), high))


def _finite_positive(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _finite_number(value, default=0.0):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return default
    if value != value or value in {float("inf"), float("-inf")}:
        return default
    return value


def _ledger_strength_score(value):
    """Map the signed FFriZz research score to the ledger's 0..100 strength field.

    Direction remains represented by the immutable LONG/SHORT field. The original
    signed value is preserved separately in calibration.raw_score, so this mapping
    changes no signal decision, threshold, strategy fingerprint, or trade authority.
    """
    return min(100.0, abs(_finite_number(value)))


def _iso(dt):
    return dt.astimezone(timezone.utc).isoformat()


def _bucket_start(now, horizon):
    """Return an immutable full-horizon UTC bucket start for non-overlap."""
    seconds = int(HORIZON_DELTAS[horizon].total_seconds())
    epoch = int(now.astimezone(timezone.utc).timestamp())
    floored = epoch - (epoch % seconds)
    return datetime.fromtimestamp(floored, tz=timezone.utc)


def _scan_id(horizon, bucket):
    """Return a deterministic UUID accepted by prediction_ledger.scan_id."""
    identity = f"{SYSTEM_ID}:{horizon}:{int(bucket.timestamp())}"
    return str(uuid.uuid5(FFRIZZ_SCAN_NAMESPACE, identity))


def _strategy_identity(horizon):
    return {
        "system": SYSTEM_ID,
        "version": 1,
        "horizon": horizon,
        "concept_families": ["pb_ema", "fvg", "inside_bar", "price_oi_correlation"],
        "fixed_rules": True,
        "research_only": True,
    }


def _oi_points(base):
    try:
        data = get_derivatives_history(base, limit=90)
    except Exception:
        return []
    history = data.get("open_interest_history") if isinstance(data, dict) else None
    history = history if isinstance(history, dict) else {}
    points = history.get("binance")
    return points if isinstance(points, list) else []


def _aggregate_backtests(rows):
    """Return descriptive pooled diagnostics, never independent evidence.

    Symbol-level backtests are non-overlapping within each symbol, but observations
    across crypto symbols can share the same market interval and common risk factor.
    Therefore pooled counts/accuracy must not be treated as independent samples or
    canonical validation evidence.
    """
    usable = [row for row in rows if int(row.get("signals") or 0) > 0]
    total = sum(int(row.get("signals") or 0) for row in usable)
    base = {
        "signals": total,
        "accuracy": None,
        "mean_net_pct": None,
        "descriptive_only": True,
        "cross_symbol_independence_proven": False,
        "independent_sample_count": None,
        "eligible_for_validation_evidence": False,
        "historical_oi_included": False,
        "strategy_fingerprint_matches_forward": False,
        "reason": "cross_symbol_dependence_and_historical_oi_absence",
    }
    if not usable or total <= 0:
        return base
    weighted_wins = sum(float(row.get("accuracy") or 0.0) * int(row.get("signals") or 0) for row in usable)
    weighted_net = sum(float(row.get("mean_net_pct") or 0.0) * int(row.get("signals") or 0) for row in usable)
    base.update({
        "accuracy": weighted_wins / total,
        "mean_net_pct": weighted_net / total,
    })
    return base


def _forward_abstention_diagnostics(horizon_results):
    """Explain fixed-gate WAIT outcomes without changing the strategy.

    Categories are deterministic observations of the already-predeclared decision
    rule. They are diagnostics only: no threshold is tuned, no unavailable feature
    is backfilled, and no category can authorize trading or promotion.
    """
    action_counts = {"WAIT": 0, "SHADOW_BUY": 0, "SHADOW_SELL": 0}
    wait_gate_counts = {
        "insufficient_directional_agreement": 0,
        "score_below_predeclared_threshold": 0,
        "unexpected_wait_state": 0,
    }
    family_unavailable_counts = {}
    available_family_count_distribution = {}
    horizon_counts = {}
    signals_scored = 0

    for horizon_result in horizon_results or []:
        horizon = str(horizon_result.get("horizon") or "unknown")
        h_counts = {"scored": 0, "WAIT": 0, "SHADOW_BUY": 0, "SHADOW_SELL": 0}
        for signal in horizon_result.get("current_shadow_signals") or []:
            signals_scored += 1
            h_counts["scored"] += 1
            action = str(signal.get("action") or "WAIT").upper()
            if action not in action_counts:
                action = "WAIT"
            action_counts[action] += 1
            h_counts[action] += 1

            available_count = max(0, int(signal.get("available_family_count") or 0))
            key = str(available_count)
            available_family_count_distribution[key] = available_family_count_distribution.get(key, 0) + 1
            for family in signal.get("families") or []:
                if not isinstance(family, dict) or family.get("available", True) is not False:
                    continue
                family_name = str(family.get("family") or "unknown")
                reason = str(family.get("reason") or "unavailable")
                family_key = f"{family_name}:{reason}"
                family_unavailable_counts[family_key] = family_unavailable_counts.get(family_key, 0) + 1

            if action != "WAIT":
                continue
            agreement = max(0, int(signal.get("independent_family_agreement") or 0))
            raw_score = abs(_finite_number(signal.get("score")))
            required_threshold = FIXED_STRONG_THRESHOLD if agreement < 3 else FIXED_SIGNAL_THRESHOLD
            if agreement < 2:
                wait_gate_counts["insufficient_directional_agreement"] += 1
            elif raw_score < required_threshold:
                wait_gate_counts["score_below_predeclared_threshold"] += 1
            else:
                # This bucket should stay zero under the current scorer. Keeping it
                # visible makes future scorer/diagnostic drift fail conspicuously.
                wait_gate_counts["unexpected_wait_state"] += 1
        horizon_counts[horizon] = h_counts

    return {
        "diagnostic_only": True,
        "thresholds_unchanged": True,
        "backfill_used": False,
        "signals_scored": signals_scored,
        "action_counts": action_counts,
        "wait_gate_counts": wait_gate_counts,
        "family_unavailable_counts": dict(sorted(family_unavailable_counts.items())),
        "available_family_count_distribution": dict(sorted(available_family_count_distribution.items())),
        "horizon_counts": horizon_counts,
        "fixed_signal_threshold": float(FIXED_SIGNAL_THRESHOLD),
        "fixed_strong_threshold": float(FIXED_STRONG_THRESHOLD),
        "trade_authority": False,
        "promotion_authority": False,
    }


def build_forward_ledger_rows(report, *, generated_at=None):
    """Build one eligible forecast per symbol/horizon/full-horizon bucket.

    Source WAIT rows are deliberately excluded. Re-running inside the same full-
    horizon bucket produces the same UUID scan_id, allowing the canonical ledger's
    duplicate protection to prevent overlapping pseudo-independent evidence. The
    shadow BUY/SELL decision is preserved only as research metadata; the canonical
    production action remains WAIT, matching the ledger contract and preventing a
    shadow forecast from acquiring trade authority.
    """
    now = generated_at or datetime.now(timezone.utc)
    if now.tzinfo is None:
        now = now.replace(tzinfo=timezone.utc)
    rows = []
    for horizon_result in report.get("horizon_results") or []:
        horizon = str(horizon_result.get("horizon") or "")
        if horizon not in HORIZON_DELTAS:
            continue
        bucket = _bucket_start(now, horizon)
        scan_id = _scan_id(horizon, bucket)
        due_at = now + HORIZON_DELTAS[horizon]
        for signal in horizon_result.get("current_shadow_signals") or []:
            action = str(signal.get("action") or "WAIT").upper()
            direction = str(signal.get("direction") or "").upper()
            entry = _finite_positive(signal.get("entry_price"))
            symbol = str(signal.get("symbol") or "").strip()
            if action not in PERSIST_ACTIONS or direction not in {"LONG", "SHORT"} or not symbol or entry is None:
                continue
            raw_score = float(signal.get("score") or 0.0)
            families = signal.get("families") if isinstance(signal.get("families"), list) else []
            calibration = {
                "source_system": SYSTEM_ID,
                "research_only": True,
                "shadow_only": True,
                "trade_authority": False,
                "promotion_authority": False,
                "shadow_action": action,
                "production_action_semantics": "WAIT",
                "bar": signal.get("bar"),
                "raw_score": raw_score,
                "ledger_score_semantics": "absolute_shadow_strength",
                "family_agreement_count": signal.get("independent_family_agreement"),
                "family_agreement_independence_proven": False,
                "available_family_count": signal.get("available_family_count"),
                "families": families,
                "forecast_bucket_started_at": _iso(bucket),
                "forecast_generated_at": _iso(now),
                "historical_oi_backfill_used": False,
                "historical_diagnostic_matches_forward_fingerprint": False,
            }
            rows.append({
                "scan_id": scan_id,
                "symbol": symbol,
                "horizon": horizon,
                "direction": direction,
                "entry_price": entry,
                "score": _ledger_strength_score(raw_score),
                "market_regime": None,
                "strategy_identity": _strategy_identity(horizon),
                "action_at_forecast": "WAIT",
                "due_at": _iso(due_at),
                "calibration": calibration,
            })
    return rows


def run(*, persist=True, generated_at=None):
    generated_at = generated_at or datetime.now(timezone.utc)
    if generated_at.tzinfo is None:
        generated_at = generated_at.replace(tzinfo=timezone.utc)
    universe_size = _int_env("FFRIZZ_UNIVERSE_SIZE", DEFAULT_UNIVERSE_SIZE, 4, MAX_UNIVERSE_SIZE)
    universe = build_universe()[:universe_size]
    by_bar = {}
    failures = []
    for row in universe:
        symbol = str(row.get("symbol") or "")
        if not symbol:
            continue
        by_bar[symbol] = {}
        for bar in sorted({profile["bar"] for profile in HORIZON_PROFILES.values()}):
            try:
                by_bar[symbol][bar] = get_history(symbol, bar=bar, bars=HISTORY_BARS[bar], max_bars=5000)
            except Exception as exc:
                failures.append({"symbol": symbol, "bar": bar, "error_type": type(exc).__name__})
                by_bar[symbol][bar] = []

    oi_cache = {}
    results = []
    for horizon in HORIZON_ORDER:
        bar = HORIZON_PROFILES[horizon]["bar"]
        current = []
        diagnostics = []
        for row in universe:
            symbol = str(row.get("symbol") or "")
            base = str(row.get("base") or symbol.split("-")[0])
            candles = by_bar.get(symbol, {}).get(bar) or []
            if not candles:
                continue
            oi = []
            if bar == "1H":
                if base not in oi_cache:
                    oi_cache[base] = _oi_points(base)
                oi = oi_cache[base]
            signal = score_shadow_signal(candles, oi, horizon=horizon)
            entry_price = _finite_positive((candles[-1] or {}).get("close")) if candles else None
            signal.update({"symbol": symbol, "base": base, "entry_price": entry_price})
            current.append(signal)
            diagnostics.append({"symbol": symbol, **chronological_backtest(candles, horizon=horizon)})
        current.sort(key=lambda item: abs(float(item.get("score") or 0.0)), reverse=True)
        aggregate = _aggregate_backtests(diagnostics)
        results.append({
            "horizon": horizon,
            "bar": bar,
            "current_shadow_signals": current,
            "diagnostic_backtest": aggregate,
            "symbol_diagnostics": [
                {
                    "symbol": item["symbol"],
                    "signals": item["signals"],
                    "accuracy": item["accuracy"],
                    "mean_net_pct": item["mean_net_pct"],
                    "historical_oi_included": False,
                    "strategy_fingerprint_matches_forward": False,
                    "eligible_for_validation_evidence": False,
                }
                for item in diagnostics
            ],
        })

    report = {
        "generated_at": _iso(generated_at),
        "system": SYSTEM_ID,
        "research_only": True,
        "shadow_only": True,
        "trade_authority": False,
        "paper_trade_authority": False,
        "promotion_authority": False,
        "broker_authority": False,
        "universe_requested": universe_size,
        "universe_resolved": len(universe),
        "failed_history_fetches": failures,
        "predeclared_horizons": list(HORIZON_ORDER),
        "concept_families": ["pb_ema_200_high_close_channel", "fair_value_gap", "inside_bar", "price_open_interest_correlation"],
        "source_policy": "Public FFriZz indicator concepts only; protected Pine source is not copied. Open-interest history is timestamp-aligned and remains missing when unavailable.",
        "horizon_results": results,
        "evidence_warning": "Historical OHLC-only diagnostics are descriptive and do not match the prospective FFriZz fingerprint when OI is available. Cross-symbol pooled outcomes are not independent evidence. Only canonical prospective non-overlapping resolved forecasts may enter governed validation.",
    }
    report["forward_abstention_diagnostics"] = _forward_abstention_diagnostics(results)
    ledger_rows = build_forward_ledger_rows(report, generated_at=generated_at)
    if persist and ledger_rows:
        insert_prediction_ledger(ledger_rows)
    report["forward_evidence"] = {
        "persistence_requested": bool(persist),
        "eligible_shadow_forecasts": len(ledger_rows),
        "non_overlapping_full_horizon_buckets": True,
        "wait_rows_persisted": False,
        "historical_oi_backfill_used": False,
        "historical_diagnostic_matches_forward_fingerprint": False,
        "cross_symbol_independence_assumed": False,
        "abstention_diagnostics": report["forward_abstention_diagnostics"],
        "prediction_ledger_rows": ledger_rows,
        "trade_authority": False,
        "promotion_authority": False,
    }
    return report


def main():
    report = run(persist=True)
    path = os.getenv("FFRIZZ_SECONDARY_SUMMARY_PATH", "").strip()
    if path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(report, sort_keys=True, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()
