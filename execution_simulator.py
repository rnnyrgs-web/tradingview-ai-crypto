"""Current-snapshot execution simulation for research/paper decisions.

Never treats current order-book state as historical evidence and never invents
hidden liquidity. A simulation is usable only when at least two reliable
exchange books show complete fills at a supported notional tier.
"""

from dataclasses import dataclass
import math


@dataclass(frozen=True)
class ExecutionSimulation:
    executable: bool
    reason: str
    requested_notional: float
    supported_notional: float | None
    fill_price: float | None
    worst_slippage_bps: float | None
    source_count: int
    fee_bps: float


def _finite_positive(value):
    try:
        return math.isfinite(float(value)) and float(value) > 0
    except (TypeError, ValueError):
        return False


def simulate_market_fill(order_book: dict, direction: str, requested_notional: float, fee_bps: float = 0.0) -> ExecutionSimulation:
    direction = str(direction or "").upper()
    if direction not in {"LONG", "SHORT"} or not _finite_positive(requested_notional):
        return ExecutionSimulation(False, "invalid_request", float(requested_notional or 0.0), None, None, None, 0, float(fee_bps or 0.0))
    requested = float(requested_notional)
    fee = float(fee_bps or 0.0)
    if not math.isfinite(fee) or fee < 0:
        return ExecutionSimulation(False, "invalid_fee", requested, None, None, None, 0, 0.0)
    if not isinstance(order_book, dict) or order_book.get("reliable") is not True:
        return ExecutionSimulation(False, "unreliable_cross_exchange_book", requested, None, None, None, 0, fee)

    side = "buy" if direction == "LONG" else "sell"
    by_tier = {}
    for exchange in order_book.get("exchanges") or []:
        if exchange.get("reliable") is not True:
            continue
        profile = exchange.get("live_fill_slippage") or {}
        if profile.get("available") is not True or profile.get("historical") is not False:
            continue
        for estimate in profile.get("estimates") or []:
            tier = estimate.get("quote_notional")
            if not _finite_positive(tier):
                continue
            tier = float(tier)
            fill = estimate.get(side) or {}
            if fill.get("complete_fill") is not True:
                continue
            vwap = fill.get("vwap")
            slippage = fill.get("slippage_bps_vs_mid")
            if not _finite_positive(vwap):
                continue
            try:
                slippage = float(slippage)
            except (TypeError, ValueError):
                continue
            if not math.isfinite(slippage) or slippage < 0:
                continue
            by_tier.setdefault(tier, []).append((float(vwap), slippage))

    supported = sorted(t for t, rows in by_tier.items() if t >= requested and len(rows) >= 2)
    if not supported:
        return ExecutionSimulation(False, "insufficient_independent_visible_depth", requested, None, None, None, 0, fee)

    tier = supported[0]
    rows = by_tier[tier]
    # Use the worst independently observed execution price, not the most favorable.
    raw_fill = max(v for v, _ in rows) if direction == "LONG" else min(v for v, _ in rows)
    worst_slippage = max(s for _, s in rows)
    fee_fraction = fee / 10000.0
    fill_price = raw_fill * (1.0 + fee_fraction if direction == "LONG" else 1.0 - fee_fraction)
    return ExecutionSimulation(
        True,
        "ok_conservative_current_snapshot",
        requested,
        tier,
        fill_price,
        worst_slippage,
        len(rows),
        fee,
    )
