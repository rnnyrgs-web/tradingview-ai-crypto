"""Restrictive-only production risk gates inspired by market-microstructure principles.

These gates never create trade authority. They can only preserve an already-valid
candidate or force WAIT / block new paper positions when execution, portfolio,
market, or system conditions are unsafe.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import math


MAX_PORTFOLIO_DRAWDOWN_PCT = 10.0
MAX_CONSECUTIVE_LOSSES = 4
LOSS_STREAK_COOLDOWN_SECONDS = 24 * 60 * 60
MAX_SAME_DIRECTION_POSITIONS = 3
MAX_SINGLE_TRADE_SPREAD_BPS = 35.0
MAX_VISIBLE_SLIPPAGE_BPS = 25.0
GLOBAL_WIDE_SPREAD_BPS = 100.0
GLOBAL_VOL_SHOCK_24H_PCT = 20.0
MIN_MARKET_SNAPSHOT_VALID_RATIO = 0.80
MAX_HEALTH_AGE_SECONDS = 45 * 60
MAX_SCAN_ERROR_RATIO = 0.35
MIN_DEEP_SCAN_COVERAGE_RATIO = 0.40


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


def _parse_time(value):
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except (TypeError, ValueError):
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def assess_execution_risk(candidate: dict, direction: str, quote_notional: float = 5000.0) -> RiskGateDecision:
    """Reject execution conditions that can plausibly erase a forecast edge."""
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
    """Detect broad market/data/system stress and force global WAIT when triggered."""
    reasons = []
    metrics = {}
    rows = list(candidates or [])

    if rows:
        valid_changes = [abs(float(c["change_24h_pct"])) for c in rows if isinstance(c, dict) and _finite(c.get("change_24h_pct"))]
        valid_spreads = [float(c["spread_bps"]) for c in rows if isinstance(c, dict) and _finite(c.get("spread_bps")) and float(c["spread_bps"]) >= 0]
        reliable_consensus = sum(
            isinstance(c, dict) and isinstance(c.get("market_consensus"), dict)
            and c["market_consensus"].get("reliable") in {True, False}
            for c in rows
        )
        metrics["market_rows"] = len(rows)
        metrics["valid_change_ratio"] = len(valid_changes) / len(rows)
        metrics["valid_spread_ratio"] = len(valid_spreads) / len(rows)
        metrics["valid_consensus_ratio"] = reliable_consensus / len(rows)
        if len(rows) >= 5 and min(
            metrics["valid_change_ratio"], metrics["valid_spread_ratio"], metrics["valid_consensus_ratio"]
        ) < MIN_MARKET_SNAPSHOT_VALID_RATIO:
            reasons.append("incomplete_or_corrupt_market_snapshot")

        shock_count = sum(x >= GLOBAL_VOL_SHOCK_24H_PCT for x in valid_changes)
        metrics["vol_shock_count"] = shock_count
        if len(valid_changes) >= 5 and shock_count / len(valid_changes) >= 0.40:
            reasons.append("broad_market_volatility_shock")

        wide_count = sum(x >= GLOBAL_WIDE_SPREAD_BPS for x in valid_spreads)
        metrics["wide_spread_count"] = wide_count
        if len(valid_spreads) >= 5 and wide_count / len(valid_spreads) >= 0.30:
            reasons.append("broad_liquidity_stress")

        disagreements = sum(
            isinstance(c, dict) and (c.get("market_consensus") or {}).get("reason") == "exchange_price_disagreement"
            for c in rows
        )
        metrics["exchange_disagreement_count"] = disagreements
        if disagreements >= 2:
            reasons.append("cross_exchange_data_instability")

    if health is not None:
        if not isinstance(health, dict):
            reasons.append("malformed_system_health")
        else:
            last_scan = health.get("last_scan")
            if last_scan is not None:
                if not isinstance(last_scan, dict):
                    reasons.append("malformed_system_health")
                else:
                    if last_scan.get("ok") is False:
                        reasons.append("production_scan_unhealthy")
                    observed = _parse_time(last_scan.get("at"))
                    if observed is None:
                        reasons.append("malformed_system_health")
                    else:
                        age = max(0.0, (datetime.now(timezone.utc) - observed).total_seconds())
                        metrics["health_age_seconds"] = round(age, 3)
                        if age > MAX_HEALTH_AGE_SECONDS:
                            reasons.append("stale_system_health")

                    universe = last_scan.get("universe_count")
                    deep = last_scan.get("deep_scanned")
                    scan_errors = last_scan.get("scan_error_count")
                    if not all(isinstance(x, int) and x >= 0 for x in (universe, deep, scan_errors)):
                        reasons.append("malformed_system_health")
                    elif universe > 0:
                        coverage = deep / universe
                        metrics["deep_scan_coverage_ratio"] = coverage
                        if coverage < MIN_DEEP_SCAN_COVERAGE_RATIO:
                            reasons.append("deep_scan_coverage_collapse")
                        denominator = max(1, deep + scan_errors)
                        error_ratio = scan_errors / denominator
                        metrics["scan_error_ratio"] = error_ratio
                        if error_ratio > MAX_SCAN_ERROR_RATIO:
                            reasons.append("excessive_scan_failures")

            recent_errors = health.get("recent_error_count")
            if not isinstance(recent_errors, int) or recent_errors < 0:
                reasons.append("malformed_system_health")
            elif recent_errors >= 10:
                reasons.append("repeated_system_errors")

    return RiskGateDecision(bool(reasons), tuple(sorted(set(reasons))), metrics)


def assess_portfolio_risk(account: dict, open_trades: list[dict], stats: dict) -> RiskGateDecision:
    """Fail closed on abnormal drawdown, active loss-streak cooldown, or concentrated direction.

    A raw consecutive-loss count cannot be a permanent latch: if all new positions are
    blocked, a future winning trade can never occur to reset that count. Therefore a
    four-loss streak triggers a conservative 24-hour cooling-off period measured from
    the most recently closed trade. Missing/malformed close chronology stays blocked.
    """
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
        last_closed = _parse_time(stats.get("last_closed_at") if isinstance(stats, dict) else None)
        metrics["loss_streak_cooldown_seconds"] = LOSS_STREAK_COOLDOWN_SECONDS
        if last_closed is None:
            metrics["loss_streak_timestamp_valid"] = False
            reasons.append("repeated_loss_streak")
        else:
            metrics["loss_streak_timestamp_valid"] = True
            age_seconds = max(0.0, (datetime.now(timezone.utc) - last_closed).total_seconds())
            remaining = max(0.0, LOSS_STREAK_COOLDOWN_SECONDS - age_seconds)
            metrics["loss_streak_age_seconds"] = round(age_seconds, 3)
            metrics["loss_streak_cooldown_remaining_seconds"] = round(remaining, 3)
            metrics["loss_streak_cooldown_complete"] = remaining <= 0
            if remaining > 0:
                reasons.append("repeated_loss_streak")

    directions = [str(t.get("direction") or "").upper() for t in (open_trades or [])]
    long_count = sum(d == "LONG" for d in directions)
    short_count = sum(d == "SHORT" for d in directions)
    metrics["long_positions"] = long_count
    metrics["short_positions"] = short_count
    if max(long_count, short_count) > MAX_SAME_DIRECTION_POSITIONS:
        reasons.append("correlated_directional_concentration")

    return RiskGateDecision(bool(reasons), tuple(sorted(set(reasons))), metrics)
