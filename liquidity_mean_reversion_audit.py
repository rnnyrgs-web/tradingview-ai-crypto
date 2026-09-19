"""Descriptive audit of the original sealed selection trades, never a selector.

No network, fresh outcomes, parameter search, portfolio-return claims or OOS
metrics. Reproduce with: python liquidity_mean_reversion_audit.py --output PATH
"""
from __future__ import annotations

import argparse
import json
import statistics
from datetime import datetime, timezone
from pathlib import Path

from liquidity_mean_reversion_selection import _load_frozen_cache
from volatility_breakout_selection import _basic_metrics, _percentile


def distribution(trades, cost):
    values = [t["gross_bps"] - cost for t in trades]
    wins = [v for v in values if v > 0]
    losses = [v for v in values if v < 0]
    return {
        **_basic_metrics(trades, cost),
        "quantiles_net_bps": {str(q): _percentile(values, q) if values else None for q in (.01, .05, .25, .5, .75, .95, .99)},
        "minimum_net_bps": min(values) if values else None,
        "maximum_net_bps": max(values) if values else None,
        "sample_stddev_net_bps": statistics.stdev(values) if len(values) > 1 else None,
        "mean_win_bps": statistics.mean(wins) if wins else None,
        "mean_loss_bps": statistics.mean(losses) if losses else None,
        "wins": len(wins), "losses": len(losses), "ties": len(values) - len(wins) - len(losses),
    }


def audit():
    evidence, _ = _load_frozen_cache()
    payload = evidence["payload"]
    selection = payload["selection"]
    result = {
        "fingerprint_id": selection["fingerprint_id"],
        "contract_sha256": selection["contract_sha256"],
        "source_payload_sha256": evidence["integrity"]["payload_sha256"],
        "dataset_sha256": payload["dataset_manifest"]["normalized_rows_sha256"],
        "analysis_type": "POST_SELECTION_DESCRIPTIVE_AUDIT_OF_SAME_TRADES_NO_NEW_GATES",
        "research_only": True, "trade_authority": False, "promotion_authority": False,
        "untouched_oos_opened": False, "genuine_forward_opened": False,
        "drawdown_interpretation": "Additive trade-label bps ordered by signal time, not a capital-normalized portfolio drawdown. Concurrent correlated assets are not independent bets; no sizing, leverage or intrahold mark-to-market model exists.",
        "timestamp_interpretation": "Original signal_ts is bar OPEN; decision becomes available at signal_ts + one hour. Entry uses next bar open, and exit is six hours after entry. Execution latency is represented only by the frozen cost proxy.",
        "segments": {},
    }
    for segment in ("train", "validation"):
        trades = sorted(
            [dict(t, instrument=inst) for inst, ev in selection["primary"].items() for t in ev[segment]["trades"]],
            key=lambda t: (t["signal_ts"], t["instrument"]),
        )
        start = min(ev[segment]["start_ts"] for ev in selection["primary"].values())
        end = max(ev[segment]["end_ts"] for ev in selection["primary"].values()) + 3_600_000
        days = (end - start) / 86_400_000
        months = sorted({datetime.fromtimestamp(t["signal_ts"] / 1000, timezone.utc).strftime("%Y-%m") for t in trades})
        result["segments"][segment] = {
            "start_inclusive_utc": datetime.fromtimestamp(start / 1000, timezone.utc).isoformat(),
            "end_exclusive_utc": datetime.fromtimestamp(end / 1000, timezone.utc).isoformat(),
            "calendar_days": days,
            "trade_labels_per_30_days": len(trades) / days * 30,
            "distinct_signal_hours": len({t["signal_ts"] for t in trades}),
            "distinct_signal_dates": len({t["signal_ts"] // 86_400_000 for t in trades}),
            "cost_stress": {f"{m:g}x": distribution(trades, 20 * m) for m in (1, 1.5, 2, 3)},
            "asset_3x": {inst: distribution([t for t in trades if t["instrument"] == inst], 60) for inst in selection["primary"]},
            "direction_3x": {side: distribution([t for t in trades if t["direction"] == side], 60) for side in ("LONG", "SHORT")},
            "month_3x": {month: distribution([t for t in trades if datetime.fromtimestamp(t["signal_ts"] / 1000, timezone.utc).strftime("%Y-%m") == month], 60) for month in months},
            "regime_and_halves": {key: selection["pooled_primary"][segment][key] for key in ("regime_cost_stress", "first_half_cost_stress", "second_half_cost_stress")},
        }
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True)
    args = parser.parse_args()
    Path(args.output).write_text(json.dumps(audit(), indent=2, sort_keys=True) + "\n", encoding="utf-8")
