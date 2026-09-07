"""ACC-001 untouched-OOS execution robustness evidence.

Current order-book slippage is never backfilled as historical fact. It is used
only to inform explicitly conservative round-trip cost stress applied to the
same untouched holdout trade path selected by training-only walk-forward logic.
"""

from backtest import (
    _score_history,
    _validate_timestamps,
    execution_cost_scenarios,
    summarize_returns,
    walk_forward,
)
from config import BACKTEST_COST_BPS
from market_data import get_history, get_order_book_intelligence


def _base_symbol(symbol):
    return str(symbol).upper().split("-")[0]


def snapshot_round_trip_slippage_bps(order_book, quote_notional=5000.0):
    """Extract conservative current round-trip slippage from reliable books.

    Requires two reliable exchange sources with complete fills at the requested
    notional. The largest observed one-way buy/sell slippage is doubled. This is
    a current stress anchor only, not historical execution evidence.
    """
    if not isinstance(order_book, dict) or not order_book.get("research_only"):
        return {"available": False, "reason": "missing_research_only_snapshot"}
    if not order_book.get("reliable") or int(order_book.get("live_slippage_source_count") or 0) < 2:
        return {"available": False, "reason": "insufficient_reliable_live_slippage_sources"}

    requested = float(quote_notional)
    source_slippages = []
    for exchange in order_book.get("exchanges") or []:
        if not exchange.get("reliable"):
            continue
        profile = exchange.get("live_fill_slippage") or {}
        if not profile.get("available") or profile.get("historical") is not False:
            continue
        matched = None
        for estimate in profile.get("estimates") or []:
            if abs(float(estimate.get("quote_notional") or 0.0) - requested) < 1e-9:
                matched = estimate
                break
        if not matched:
            continue
        sides = [matched.get("buy") or {}, matched.get("sell") or {}]
        if not all(x.get("available") and x.get("complete_fill") for x in sides):
            continue
        worst_one_way = max(float(x.get("slippage_bps_vs_mid") or 0.0) for x in sides)
        source_slippages.append({
            "exchange": exchange.get("exchange"),
            "worst_one_way_slippage_bps": worst_one_way,
        })

    if len(source_slippages) < 2:
        return {"available": False, "reason": "incomplete_fill_or_missing_notional"}

    worst_one_way = max(x["worst_one_way_slippage_bps"] for x in source_slippages)
    return {
        "available": True,
        "reason": "ok_current_snapshot_stress_anchor",
        "historical": False,
        "quote_notional": requested,
        "source_count": len(source_slippages),
        "sources": source_slippages,
        "worst_one_way_slippage_bps": worst_one_way,
        "observed_round_trip_slippage_bps": worst_one_way * 2.0,
    }


def execution_stress_costs(snapshot_anchor=None, base_cost_bps=BACKTEST_COST_BPS):
    """Build deterministic historical stress costs without inventing history."""
    costs = set(execution_cost_scenarios(base_cost_bps))
    if snapshot_anchor and snapshot_anchor.get("available"):
        observed = max(float(base_cost_bps), float(snapshot_anchor["observed_round_trip_slippage_bps"]))
        costs.update(round(observed * multiplier, 4) for multiplier in (1.0, 1.5, 2.0))
    return tuple(sorted(costs))


def evaluate_execution_oos(symbol, bar="15m", bars=5000, quote_notional=5000.0, order_book=None):
    """Compare the untouched holdout across conservative execution-cost stress.

    Threshold selection is delegated to the existing training-only walk-forward
    routine. The same holdout path is then rescored at each cost level; only the
    cost deduction changes. Current slippage can expand the stress grid but is
    never assigned to any historical timestamp.
    """
    wf = walk_forward(symbol, bar=bar, bars=bars)
    selected = wf.get("selected_threshold")
    if selected is None:
        return {
            "research_only": True,
            "ok": True,
            "symbol": symbol,
            "bar": bar,
            "message": "No viable training threshold; execution OOS comparison unavailable",
        }

    snapshot = order_book if order_book is not None else get_order_book_intelligence(_base_symbol(symbol))
    anchor = snapshot_round_trip_slippage_bps(snapshot, quote_notional=quote_notional)
    costs = execution_stress_costs(anchor)

    history = get_history(symbol, bar, bars)
    if len(history) < 1000:
        raise RuntimeError("Need at least 1000 candles for execution OOS robustness")
    _validate_timestamps(history)
    holdout = history[int(len(history) * 0.8):]

    scenarios = {}
    for cost_bps in costs:
        returns = _score_history(holdout, bar, selected, cost_bps)
        scenarios[str(cost_bps)] = {
            "cost_bps_round_trip": cost_bps,
            **summarize_returns(returns),
        }

    base_key = str(round(float(BACKTEST_COST_BPS), 4))
    max_key = str(max(costs))
    max_stress = scenarios[max_key]
    return {
        "research_only": True,
        "ok": True,
        "symbol": symbol,
        "bar": bar,
        "selected_threshold_from_training_only": selected,
        "holdout_candles": len(holdout),
        "current_snapshot_anchor": anchor,
        "historical_slippage_available": False,
        "historical_slippage_reason": "current_order_book_snapshot_not_backfilled_into_history",
        "same_trade_path_policy": True,
        "scenarios": scenarios,
        "base_scenario": scenarios.get(base_key),
        "max_stress_cost_bps": max(costs),
        "positive_expectancy_at_max_stress": max_stress["avg_trade_pct"] > 0,
        "positive_sum_at_max_stress": max_stress["sum_net_returns_pct"] > 0,
        "note": (
            "Untouched holdout is rescored on the same selected trade path. Current live slippage only "
            "expands conservative cost stress; it is not treated as historical slippage or promotion authority."
        ),
    }
