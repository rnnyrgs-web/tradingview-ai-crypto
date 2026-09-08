"""Continuous ACC-002 cross-asset research runner.

Fetches a liquid spot universe once per cycle, aligns completed historical candles,
and evaluates relative-strength ranks on chronological train/validation/untouched
OOS splits with explicit round-trip costs. Output is sealed research evidence only.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from cross_asset_rank import CrossAssetConfig, build_cross_section_panel, evaluate_panel
from market_data import build_universe, get_history
from research_artifact import seal_research_payload


MIN_INDEPENDENT_OOS_SAMPLES = 20
MAX_HISTORY_BARS = 5000


def _int_env(name: str, default: int, low: int, high: int) -> int:
    return max(low, min(int(os.getenv(name, str(default))), high))


def required_history_bars(config: CrossAssetConfig, min_oos_samples: int = MIN_INDEPENDENT_OOS_SAMPLES) -> int:
    """Conservative minimum history for non-overlapping untouched-OOS observations.

    The untouched segment is ~20% of the panel and evaluation stride defaults to
    forward_bars. Requiring 5 * min_samples * forward_bars panel observations
    keeps the nominal untouched OOS large enough before purging/rounding.
    """
    panel_required = 5 * max(1, int(min_oos_samples)) * max(1, int(config.forward_bars))
    return max(config.lookbacks) + config.forward_bars + panel_required


def run() -> dict:
    universe_size = _int_env("CROSS_ASSET_UNIVERSE_SIZE", 30, 8, 60)
    requested_bars = _int_env("CROSS_ASSET_BARS", 3000, 300, MAX_HISTORY_BARS)
    bar = os.getenv("CROSS_ASSET_BAR", "1H")
    forward_bars = _int_env("CROSS_ASSET_FORWARD_BARS", 24, 1, 168)
    cost_bps = float(os.getenv("CROSS_ASSET_ROUND_TRIP_COST_BPS", "12"))

    config = CrossAssetConfig(
        forward_bars=forward_bars,
        round_trip_cost_bps=cost_bps,
        min_assets=8,
    )
    minimum_bars = required_history_bars(config)
    if minimum_bars > MAX_HISTORY_BARS:
        raise ValueError(
            f"forward horizon requires at least {minimum_bars} bars for "
            f"{MIN_INDEPENDENT_OOS_SAMPLES} independent OOS observations; "
            f"maximum supported is {MAX_HISTORY_BARS}; use a coarser bar interval"
        )
    bars = max(requested_bars, minimum_bars)

    symbols = [row["symbol"] for row in build_universe()[:universe_size]]
    histories = {}
    failures = []
    minimum_symbol_history = max(200, minimum_bars)
    for symbol in symbols:
        try:
            rows = get_history(symbol, bar=bar, bars=bars)
            if len(rows) >= minimum_symbol_history:
                histories[symbol] = rows
            else:
                failures.append({
                    "symbol": symbol,
                    "error_type": "InsufficientHistory",
                    "bars_received": len(rows),
                    "bars_required": minimum_symbol_history,
                })
        except Exception as exc:
            failures.append({"symbol": symbol, "error_type": type(exc).__name__})

    panel = build_cross_section_panel(histories, config)
    evaluation = evaluate_panel(panel, config)
    if evaluation["splits"]["untouched_oos"]["timestamps"] < MIN_INDEPENDENT_OOS_SAMPLES:
        raise ValueError("insufficient independent untouched-OOS observations after alignment")

    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "acc": "ACC-002",
        "research_only": True,
        "live_approved": False,
        "trade_authority": False,
        "source": "OKX public historical API",
        "universe_requested": universe_size,
        "universe_resolved": len(histories),
        "symbols": sorted(histories),
        "failed_symbols": failures,
        "bar": bar,
        "bars_requested_env": requested_bars,
        "bars_effective": bars,
        "minimum_history_bars": minimum_bars,
        "minimum_independent_oos_samples": MIN_INDEPENDENT_OOS_SAMPLES,
        "evaluation": evaluation,
    }
    return seal_research_payload(payload)


def main() -> None:
    payload = run()
    print(json.dumps(payload, default=str), flush=True)


if __name__ == "__main__":
    main()
