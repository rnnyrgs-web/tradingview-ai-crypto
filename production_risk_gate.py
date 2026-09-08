"""Restrictive-only production risk gates inspired by market-microstructure principles.

These gates never create trade authority. They can only preserve an already-valid
candidate or force WAIT / block new paper positions when execution, portfolio,
market, or system conditions are unsafe.
"""

from __future__ import annotations

from dataclasses import dataclass
import math


MAX_PORTFOLIO_DRAWDOWN_PCT = 10.0
MAX_CONSECUTIVE_LOSSES = 4
MAX_SAME_DIRECTION_POSITIONS = 3
MAX_SINGLE_TRADE_SPREAD_BPS = 35.0
MAX_VISIBLE_SLIPPAGE_BPS = 25.0
GLOBAL_WIDE_SPREAD_BPS = 100.0
GLOBAL_VOL_SHOCK_24H_PCT = 20.0


@dataclass(frozen=True)
class RiskGateDecision:
    blocked: bool
    reasons: tuple[str, ...]
    metrics: dict

    @property
    def allows_existing_authority(self) -> bool:
        return not self.blocked


def _finite(value) -> bool:
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def assess_execution_risk(candidate: dict, direction: str, quote_notional: float = 5000.0) -> RiskGateDecision:
    """Reject execution conditions that can plausibly erase a forecast edge.

    Uses only contemporaneous observable microstructure. It does not infer hidden
    liquidity and does not interpret order-book imbalance as alpha.
    """
    reasons = []
    metrics = {"quote_notional": float(quote_notional)}
    direction = str(direction or "").upper()
    if direction not in {"LONG", "SHORT"}:
        return RiskGateDecision(True, ("invalid_direction",), metrics)

    consensus = candidate.get("market_consensus") or {}
    if consensus.get("reliable") is not True:
        reasons.append("market_consensus_unreliable")

    spread = candidate.get("spread_bps")
    if not _finite(spread) or float(spread) < 0:
        reasons.append("invalid_spread")
    else:
        metrics["spread_bps"] = float(spread)
        if float(spread) > MAX_SINGLE_TRADE_SPREAD_BPS:
            reasons.append("spread_too_wide")

    book = candidate.get("order_book") or {}
    if book.get("reliable") is not True:
        reasons.append("order_book_unreliable")
    if book.get("direction_disagreement") is True:
        reasons.append("cross_exchange_book_disagreement")

    estimates = []
    for exchange in book.get("exchanges") or []:
        live = exchange.get("live_fill_slippage") or {}
        for estimate in live.get("estimates") or []:
            if _finite(estimate.get("quote_notional")) and abs(float(estimate["quote_notional"]) - quote_notional) < 1e-6:
                estimates.append(estimate)

    side = "buy" if direction == "LONG" else "sell"
    complete_slippage = []
    incomplete = 0
    for estimate in estimates:
        fill = estimate.get(side) or {}
        if fill.get("complete_fill") is not True:
            incomplete += 1
            continue
        slip = fill.get("slippage_bps_vs_mid")
        if _finite(slip) and float(slip) >= 0:
            complete_slippage.append(float(slip))

    metrics["complete_slippage_sources"] = len(complete_slippage)
    metrics["incomplete_visible_depth_sources"] = incomplete
    if estimates and not complete_slippage:
        reasons.append("insufficient_visible_depth")
    elif complete_slippage:
        worst = max(complete_slippage)
        metrics["worst_visible_slippage_bps"] = worst
        if worst > MAX_VISIBLE_SLIPPAGE_BPS:
            reasons.append("visible_slippage_too_high")

    return RiskGateDecision(bool(reasons), tuple(sorted(set(reasons))), metrics)


def assess_global_market_risk(candidates: list[dict], health: dict | None = None) -> RiskGateDecision:
    """Detect broad market/data/system stress and force a global WAIT when triggered."""
    reasons = []
    metrics = {}
    rows = list(candidates or [])

    if rows:
        valid_changes = [abs(float(c["change_24h_pct"])) for c in rows if _finite(c.get("change_24h_pct"))]
        shock_count = sum(x >= GLOBAL_VOL_SHOCK_24H_PCT for x in valid_changes)
        metrics["vol_shock_count"] = shock_count
        if len(valid_changes) >= 5 and shock_count / len(valid_changes) >= 0.40:
            reasons.append("broad_market_volatility_shock")

        valid_spreads = [float(c["spread_bps"]) for c in rows if _finite(c.get("spread_bps")) and float(c["spread_bps"]) >= 0]
        wide_count = sum(x >= GLOBAL_WIDE_SPREAD_BPS for x in valid_spreads)
        metrics["wide_spread_count"] = wide_count
        if len(valid_spreads) >= 5 and wide_count / len(valid_spreads) >= 0.30:
            reasons.append("broad_liquidity_stress")

        disagreements = sum((c.get("market_consensus") or {}).get("reason") == "exchange_price_disagreement" for c in rows)
        metrics["exchange_disagreement_count"] = disagreements
        if disagreements >= 2:
            reasons.append("cross_exchange_data_instability")

    if health:
        last_scan = health.get("last_scan") or {}
        if last_scan and last_scan.get("ok") is False:
            reasons.append("production_scan_unhealthy")
        recent_errors = health.get("recent_error_count")
        if isinstance(recent_errors, int) and recent_errors >= 10:
            reasons.append("repeated_system_errors")

    return RiskGateDecision(bool(reasons), tuple(sorted(set(reasons))), metrics)


def assess_portfolio_risk(account: dict, open_trades: list[dict], stats: dict) -> RiskGateDecision:
    """Fail closed on abnormal drawdown, repeated losses, or concentrated direction."""
    reasons = []
    metrics = {}
    required = ("initial_cash", "equity", "peak_equity", "max_drawdown_pct")
    if not account or any(not _finite(account.get(k)) for k in required):
        return RiskGateDecision(True, ("malformed_portfolio_state",), metrics)

    initial = float(account["initial_cash"])
    equity = float(account["equity"])
    peak = float(account["peak_equity"])
    stored_dd = float(account["max_drawdown_pct"])
    if initial <= 0 or peak <= 0 or equity < 0:
        return RiskGateDecision(True, ("malformed_portfolio_state",), metrics)

    live_dd = max(0.0, (peak - equity) / peak * 100.0)
    drawdown = max(stored_dd, live_dd)
    metrics["drawdown_pct"] = drawdown
    if drawdown >= MAX_PORTFOLIO_DRAWDOWN_PCT:
        reasons.append("portfolio_drawdown_limit")

    consecutive_losses = int(stats.get("consecutive_losses") or 0) if isinstance(stats, dict) else 0
    metrics["consecutive_losses"] = consecutive_losses
    if consecutive_losses >= MAX_CONSECUTIVE_LOSSES:
        reasons.append("repeated_loss_streak")

    directions = [str(t.get("direction") or "").upper() for t in (open_trades or [])]
    long_count = sum(d == "LONG" for d in directions)
    short_count = sum(d == "SHORT" for d in directions)
    metrics["long_positions"] = long_count
    metrics["short_positions"] = short_count
    if max(long_count, short_count) > MAX_SAME_DIRECTION_POSITIONS:
        reasons.append("correlated_directional_concentration")

    return RiskGateDecision(bool(reasons), tuple(sorted(set(reasons))), metrics)
