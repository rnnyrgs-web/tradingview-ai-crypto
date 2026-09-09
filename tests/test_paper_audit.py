from datetime import timedelta
from types import SimpleNamespace

import paper_audit as audit
import paper_trading as p
from utils import now_utc


def _account(cash=100000.0, equity=100000.0, realized=0.0):
    return {"cash": cash, "equity": equity, "realized_pnl": realized}


def test_legacy_closed_trade_is_recomputed_from_recorded_fills():
    trade = {
        "id": 1,
        "status": "CLOSED",
        "direction": "LONG",
        "entry_price": 100.0,
        "exit_price": 110.0,
        "quantity": 2.0,
        "fee_bps_one_way": 6.0,
        "notional_usd": 200.0,
        "pnl_usd": 20.0 - 110.0 * 2.0 * 6.0 / 10000.0,
        "execution_model_version": "legacy_v1",
    }
    expected = trade["pnl_usd"]
    result = audit.reconcile_paper_ledger(
        _account(100000.0 + expected, 100000.0 + expected, expected),
        [trade],
        {},
    )
    assert result.verified is True
    assert result.status == "LEDGER_VERIFIED"
    assert abs(result.expected_realized_pnl - expected) < 1e-9


def test_v2_closed_trade_does_not_double_charge_fee_inclusive_fills():
    trade = {
        "id": 2,
        "status": "CLOSED",
        "direction": "SHORT",
        "entry_price": 99.94,
        "exit_price": 89.95,
        "quantity": 5.0,
        "fee_bps_one_way": 6.0,
        "notional_usd": 499.7,
        "pnl_usd": (99.94 - 89.95) * 5.0,
        "execution_model_version": audit.V2_EXECUTION_MODEL,
    }
    expected = trade["pnl_usd"]
    result = audit.reconcile_paper_ledger(
        _account(100000.0 + expected, 100000.0 + expected, expected),
        [trade],
        {},
    )
    assert result.verified is True
    assert abs(result.expected_realized_pnl - expected) < 1e-9


def test_shadow_accountant_detects_cached_account_mismatch():
    trade = {
        "id": 3,
        "status": "CLOSED",
        "direction": "LONG",
        "entry_price": 100.0,
        "exit_price": 105.0,
        "quantity": 1.0,
        "fee_bps_one_way": 0.0,
        "notional_usd": 100.0,
        "pnl_usd": 5.0,
        "execution_model_version": "legacy_v1",
    }
    result = audit.reconcile_paper_ledger(_account(100006.0, 100006.0, 6.0), [trade], {})
    assert result.verified is False
    assert result.status == "RECONCILIATION_FAILED"
    assert "cash_mismatch" in result.reasons
    assert "equity_mismatch" in result.reasons
    assert "realized_pnl_mismatch" in result.reasons


def test_shadow_accountant_fails_closed_when_open_mark_is_missing():
    trade = {
        "id": 4,
        "status": "OPEN",
        "symbol": "BTC-USDT",
        "direction": "LONG",
        "entry_price": 100.0,
        "quantity": 2.0,
        "notional_usd": 200.0,
    }
    result = audit.reconcile_paper_ledger(_account(), [trade], {})
    assert result.verified is False
    assert "missing_mark:4" in result.reasons


def test_signal_freshness_rejects_missing_stale_and_future_signals():
    now = now_utc()
    assert p._signal_freshness({}, now) == (False, "missing_signal_timestamp")
    stale = {"generated_at": (now - timedelta(seconds=p.MAX_SIGNAL_AGE_SECONDS + 1)).isoformat()}
    assert p._signal_freshness(stale, now) == (False, "stale_signal")
    future = {"generated_at": (now + timedelta(minutes=1)).isoformat()}
    assert p._signal_freshness(future, now) == (False, "future_signal_timestamp")
    fresh = {"generated_at": (now - timedelta(minutes=1)).isoformat()}
    assert p._signal_freshness(fresh, now) == (True, "fresh")


def test_v2_exit_requires_current_size_aware_execution_and_caps_target(monkeypatch):
    simulation = SimpleNamespace(
        executable=True,
        reason="ok_conservative_current_snapshot",
        fill_price=112.0,
        supported_notional=5000.0,
        worst_slippage_bps=9.0,
        source_count=2,
    )
    monkeypatch.setattr(p, "_last_price", lambda symbol: 112.0)
    monkeypatch.setattr(p, "get_order_book_intelligence", lambda base: {"reliable": True})
    monkeypatch.setattr(p, "simulate_market_fill", lambda *args: simulation)
    trade = {
        "symbol": "BTC-USDT",
        "direction": "LONG",
        "entry_price": 100.0,
        "target_price": 110.0,
        "quantity": 10.0,
        "fee_bps_one_way": 6.0,
    }
    _, fill, pnl, evidence = p._v2_exit(trade, 111.0, "TARGET")
    assert fill < 110.0
    assert round(fill, 5) == round(110.0 * (1.0 - 6.0 / 10000.0), 5)
    assert pnl == (fill - 100.0) * 10.0
    assert evidence["exit_source_count"] == 2
