import math
from dataclasses import dataclass


TOLERANCE_USD = 0.02
V2_EXECUTION_MODEL = "visible_depth_v2"


@dataclass(frozen=True)
class PaperReconciliation:
    verified: bool
    status: str
    expected_cash: float | None
    expected_equity: float | None
    expected_realized_pnl: float | None
    open_pnl: float | None
    open_notional: float | None
    cash_delta: float | None
    equity_delta: float | None
    realized_delta: float | None
    trade_mismatch_ids: tuple[int, ...]
    reasons: tuple[str, ...]

    def as_dict(self):
        return {
            "verified": self.verified,
            "status": self.status,
            "expected_cash": self.expected_cash,
            "expected_equity": self.expected_equity,
            "expected_realized_pnl": self.expected_realized_pnl,
            "open_pnl": self.open_pnl,
            "open_notional": self.open_notional,
            "cash_delta": self.cash_delta,
            "equity_delta": self.equity_delta,
            "realized_delta": self.realized_delta,
            "trade_mismatch_ids": list(self.trade_mismatch_ids),
            "reasons": list(self.reasons),
        }


def _finite(value):
    try:
        return math.isfinite(float(value))
    except (TypeError, ValueError):
        return False


def mark_pnl(direction, entry, price, quantity):
    raw = (float(price) - float(entry)) * float(quantity)
    return raw if str(direction).upper() == "LONG" else -raw


def recompute_closed_trade_pnl(trade):
    entry = float(trade["entry_price"])
    exit_price = float(trade["exit_price"])
    quantity = float(trade["quantity"])
    pnl = mark_pnl(trade["direction"], entry, exit_price, quantity)
    if str(trade.get("execution_model_version") or "legacy_v1") != V2_EXECUTION_MODEL:
        pnl -= exit_price * quantity * float(trade.get("fee_bps_one_way") or 0.0) / 10000.0
    return pnl


def _trade_mark(marks, trade_id, symbol):
    if not isinstance(marks, dict):
        return None
    # Strict paper accounting may produce a different executable liquidation
    # price for each position because visible-depth VWAP depends on size.
    for key in (trade_id, str(trade_id), f"trade:{trade_id}"):
        if key in marks:
            return marks[key]
    return marks.get(str(symbol or "").upper())


def reconcile_paper_ledger(account, trades, marks, initial_cash=100000.0, compare_persisted=True, tolerance_usd=TOLERANCE_USD):
    reasons = []
    mismatches = []
    ids = set()
    realized = 0.0
    open_notional = 0.0
    open_pnl = 0.0

    if not account or not _finite(initial_cash) or float(initial_cash) <= 0:
        return PaperReconciliation(False, "RECONCILIATION_FAILED", None, None, None, None, None, None, None, None, (), ("invalid_account_or_baseline",))

    for trade in trades or []:
        try:
            trade_id = int(trade["id"])
        except (KeyError, TypeError, ValueError):
            reasons.append("invalid_trade_id")
            continue
        if trade_id in ids:
            reasons.append("duplicate_trade_id")
            continue
        ids.add(trade_id)
        status = str(trade.get("status") or "").upper()
        if status == "CLOSED":
            try:
                expected = recompute_closed_trade_pnl(trade)
                stored = float(trade["pnl_usd"])
            except (KeyError, TypeError, ValueError):
                reasons.append(f"malformed_closed_trade:{trade_id}")
                continue
            if not math.isfinite(expected) or not math.isfinite(stored):
                reasons.append(f"nonfinite_closed_trade:{trade_id}")
                continue
            if abs(expected - stored) > tolerance_usd:
                mismatches.append(trade_id)
            realized += expected
        elif status == "OPEN":
            try:
                notional = float(trade["notional_usd"])
                entry = float(trade["entry_price"])
                quantity = float(trade["quantity"])
            except (KeyError, TypeError, ValueError):
                reasons.append(f"malformed_open_trade:{trade_id}")
                continue
            price = _trade_mark(marks, trade_id, trade.get("symbol"))
            if not _finite(price) or float(price) <= 0:
                reasons.append(f"missing_mark:{trade_id}")
                continue
            open_notional += notional
            open_pnl += mark_pnl(trade.get("direction"), entry, float(price), quantity)
        else:
            reasons.append(f"invalid_trade_status:{trade_id}")

    if mismatches:
        reasons.append("closed_trade_pnl_mismatch")

    expected_cash = float(initial_cash) + realized - open_notional
    expected_equity = float(initial_cash) + realized + open_pnl
    cash_delta = equity_delta = realized_delta = None
    if compare_persisted:
        try:
            cash_delta = float(account["cash"]) - expected_cash
            equity_delta = float(account["equity"]) - expected_equity
            realized_delta = float(account["realized_pnl"]) - realized
        except (KeyError, TypeError, ValueError):
            reasons.append("malformed_persisted_account")
        else:
            if abs(cash_delta) > tolerance_usd:
                reasons.append("cash_mismatch")
            if abs(equity_delta) > tolerance_usd:
                reasons.append("equity_mismatch")
            if abs(realized_delta) > tolerance_usd:
                reasons.append("realized_pnl_mismatch")

    verified = not reasons
    return PaperReconciliation(
        verified,
        "LEDGER_VERIFIED" if verified else "RECONCILIATION_FAILED",
        expected_cash,
        expected_equity,
        realized,
        open_pnl,
        open_notional,
        cash_delta,
        equity_delta,
        realized_delta,
        tuple(sorted(set(mismatches))),
        tuple(reasons),
    )
