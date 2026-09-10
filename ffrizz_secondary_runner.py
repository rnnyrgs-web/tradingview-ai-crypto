"""Bounded research runner for the FFriZz-inspired secondary shadow system.

The runner intentionally remains separate from production opportunities and paper
trading. It scans a bounded liquid universe, computes current shadow signals,
and performs fixed-rule chronological diagnostics so the research factory can
learn which FFriZz-derived concepts deserve deeper canonical validation.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from ffrizz_secondary_signals import HORIZON_ORDER, HORIZON_PROFILES, chronological_backtest, score_shadow_signal
from market_data import build_universe, get_derivatives_history, get_history


MAX_UNIVERSE_SIZE = 20
DEFAULT_UNIVERSE_SIZE = 12
HISTORY_BARS = {"1H": 900, "4H": 900}


def _int_env(name, default, low, high):
    return max(low, min(int(os.getenv(name, str(default))), high))


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


def run():
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
            signal.update({"symbol": symbol, "base": base})
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

    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "system": "FFRIZZ_SECONDARY_V1",
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


def main():
    report = run()
    path = os.getenv("FFRIZZ_SECONDARY_SUMMARY_PATH", "").strip()
    if path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(report, sort_keys=True, separators=(",", ":")), encoding="utf-8")
    print(json.dumps(report, sort_keys=True, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()
