"""Bounded research runner for the FFriZz-inspired secondary shadow system.

The runner intentionally remains separate from production opportunities and paper
trading. It scans a bounded liquid universe, computes current shadow signals,
performs fixed-rule chronological diagnostics, and can persist only genuine
SHADOW_BUY/SHADOW_SELL forecasts to the canonical prediction ledger so their
future outcomes can be resolved without granting any trade authority.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from db import insert_prediction_ledger
from ffrizz_secondary_signals import HORIZON_ORDER, HORIZON_PROFILES, chronological_backtest, score_shadow_signal
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


def _int_env(name, default, low, high):
    return max(low, min(int(os.getenv(name, str(default))), high))


def _finite_positive(value):
    try:
        value = float(value)
    except (TypeError, ValueError):
        return None
    return value if value > 0 else None


def _iso(dt):
    return dt.astimezone(timezone.utc).isoformat()


def _bucket_start(now, horizon):
    """Return an immutable full-horizon UTC bucket start for non-overlap."""
    seconds = int(HORIZON_DELTAS[horizon].total_seconds())
    epoch = int(now.astimezone(timezone.utc).timestamp())
    floored = epoch - (epoch % seconds)
    return datetime.fromtimestamp(floored, tz=timezone.utc)


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
    usable = [row for row in rows if int(row.get("signals") or 0) > 0]
    total = sum(int(row.get("signals") or 0) for row in usable)
    if not usable or total <= 0:
        return {"signals": 0, "accuracy": None, "mean_net_pct": None}
    weighted_wins = sum(float(row.get("accuracy") or 0.0) * int(row.get("signals") or 0) for row in usable)
    weighted_net = sum(float(row.get("mean_net_pct") or 0.0) * int(row.get("signals") or 0) for row in usable)
    return {
        "signals": total,
        "accuracy": weighted_wins / total,
        "mean_net_pct": weighted_net / total,
    }


def build_forward_ledger_rows(report, *, generated_at=None):
    """Build one eligible forecast per symbol/horizon/full-horizon bucket.

    WAIT rows are deliberately excluded. Re-running inside the same full-horizon
    bucket produces the same scan_id, allowing the canonical ledger's duplicate
    protection to prevent overlapping pseudo-independent evidence. The deadline
    is always one exact full horizon after the first forecast observation.
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
        scan_id = f"ffrizz:{SYSTEM_ID}:{horizon}:{int(bucket.timestamp())}"
        due_at = now + HORIZON_DELTAS[horizon]
        for signal in horizon_result.get("current_shadow_signals") or []:
            action = str(signal.get("action") or "WAIT").upper()
            direction = str(signal.get("direction") or "").upper()
            entry = _finite_positive(signal.get("entry_price"))
            symbol = str(signal.get("symbol") or "").strip()
            if action not in PERSIST_ACTIONS or direction not in {"LONG", "SHORT"} or not symbol or entry is None:
                continue
            families = signal.get("families") if isinstance(signal.get("families"), list) else []
            calibration = {
                "source_system": SYSTEM_ID,
                "research_only": True,
                "shadow_only": True,
                "trade_authority": False,
                "promotion_authority": False,
                "bar": signal.get("bar"),
                "raw_score": signal.get("score"),
                "independent_family_agreement": signal.get("independent_family_agreement"),
                "available_family_count": signal.get("available_family_count"),
                "families": families,
                "forecast_bucket_started_at": _iso(bucket),
                "forecast_generated_at": _iso(now),
                "historical_oi_backfill_used": False,
            }
            rows.append({
                "scan_id": scan_id,
                "symbol": symbol,
                "horizon": horizon,
                "direction": direction,
                "entry_price": entry,
                "score": float(signal.get("score") or 0.0),
                "market_regime": None,
                "strategy_identity": _strategy_identity(horizon),
                "action_at_forecast": action,
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
                {"symbol": item["symbol"], "signals": item["signals"], "accuracy": item["accuracy"], "mean_net_pct": item["mean_net_pct"]}
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
        "evidence_warning": "Diagnostic backtests are not promotion evidence. Any apparent edge must enter the canonical chronological development/validation/untouched-OOS, robustness, multiple-testing and genuine-forward chain before production consideration.",
    }
    ledger_rows = build_forward_ledger_rows(report, generated_at=generated_at)
    if persist and ledger_rows:
        insert_prediction_ledger(ledger_rows)
    report["forward_evidence"] = {
        "persistence_requested": bool(persist),
        "eligible_shadow_forecasts": len(ledger_rows),
        "non_overlapping_full_horizon_buckets": True,
        "wait_rows_persisted": False,
        "historical_oi_backfill_used": False,
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
