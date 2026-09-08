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


def _int_env(name: str, default: int, low: int, high: int) -> int:
    return max(low, min(int(os.getenv(name, str(default))), high))


def run() -> dict:
    universe_size = _int_env("CROSS_ASSET_UNIVERSE_SIZE", 30, 8, 60)
    bars = _int_env("CROSS_ASSET_BARS", 1200, 300, 5000)
    bar = os.getenv("CROSS_ASSET_BAR", "1H")
    forward_bars = _int_env("CROSS_ASSET_FORWARD_BARS", 24, 1, 168)
    cost_bps = float(os.getenv("CROSS_ASSET_ROUND_TRIP_COST_BPS", "12"))

    symbols = [row["symbol"] for row in build_universe()[:universe_size]]
    histories = {}
    failures = []
    for symbol in symbols:
        try:
            rows = get_history(symbol, bar=bar, bars=bars)
            if len(rows) >= 200:
                histories[symbol] = rows
            else:
                failures.append({"symbol": symbol, "error_type": "InsufficientHistory"})
        except Exception as exc:
            failures.append({"symbol": symbol, "error_type": type(exc).__name__})

    config = CrossAssetConfig(
        forward_bars=forward_bars,
        round_trip_cost_bps=cost_bps,
        min_assets=8,
    )
    panel = build_cross_section_panel(histories, config)
    evaluation = evaluate_panel(panel, config)
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
        "bars_requested": bars,
        "evaluation": evaluation,
    }
    return seal_research_payload(payload)


def main() -> None:
    payload = run()
    print(json.dumps(payload, default=str), flush=True)


if __name__ == "__main__":
    main()
