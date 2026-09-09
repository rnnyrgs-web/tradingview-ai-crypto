from datetime import timedelta
from types import SimpleNamespace

import pytest

import paper_trading as p
from utils import now_utc


def test_paper_constants_are_hypothetical_and_bounded():
    assert p.INITIAL_CASH == 100000.0
    assert p.RISK_PER_TRADE_PCT <= 0.5
    assert p.MAX_OPEN_POSITIONS <= 5
    assert p.MAX_NOTIONAL_PCT <= 20.0


def test_directional_mark_pnl():
    assert p._mark_pnl("LONG", 100, 110, 2) == 20
    assert p._mark_pnl("SHORT", 100, 90, 2) == 20
    assert p._mark_pnl("SHORT", 100, 110, 2) == -20


def test_consistent_profitability_requires_real_sample_and_risk_controls():
    good = {
        "closed_trades": 30,
        "net_pnl_usd": 5000,
        "profit_factor": 1.3,
        "last_20_pnl_usd": 1200,
    }
    assert p._consistent(good, 8.0) is True
    assert p._consistent({**good, "closed_trades": 29}, 8.0) is False
    assert p._consistent({**good, "profit_factor": 1.19}, 8.0) is False
    assert p._consistent(good, 10.01) is False
    assert p._consistent({**good, "last_20_pnl_usd": -1}, 8.0) is False


def test_close_decision_uses_intrabar_extremes_and_stop_wins_ambiguity():
    base = {
        "direction": "LONG",
        "stop_loss": 95,
        "target_price": 110,
        "opened_at": (now_utc() - timedelta(hours=2)).isoformat(),
        "horizon": "24h",
    }
    assert p._close_decision(base, {"low": 94, "high": 103, "close": 102}) == (95, "STOP")
    assert p._close_decision(base, {"low": 99, "high": 111, "close": 105}) == (110, "TARGET")
    assert p._close_decision(base, {"low": 94, "high": 111, "close": 108}) == (95, "STOP")
    short = {**base, "direction": "SHORT", "stop_loss": 105, "target_price": 90}
    assert p._close_decision(short, {"low": 96, "high": 106, "close": 101}) == (105, "STOP")
    assert p._close_decision(short, {"low": 89, "high": 101, "close": 95}) == (90, "TARGET")
    assert p._close_decision(short, {"low": 89, "high": 106, "close": 100}) == (105, "STOP")
    expired = {**base, "opened_at": (now_utc() - timedelta(hours=25)).isoformat()}
    assert p._close_decision(expired, {"low": 100, "high": 104, "close": 102}) == (102, "TIME")


def test_paper_fill_requires_current_size_aware_execution_evidence(monkeypatch):
    monkeypatch.setattr(p, "_last_price", lambda symbol: 100.0)
    monkeypatch.setattr(p, "get_order_book_intelligence", lambda base: {"reliable": True})
    simulation = SimpleNamespace(
        executable=True,
        reason="ok_conservative_current_snapshot",
        fill_price=100.25,
        supported_notional=5000.0,
        worst_slippage_bps=12.0,
        source_count=2,
    )
    monkeypatch.setattr(p, "simulate_market_fill", lambda book, direction, requested, fee: simulation)
    market, fill, evidence = p._paper_fill_price("BTC-USDT", "LONG", 4000.0)
    assert market == 100.0
    assert fill == 100.25
    assert evidence.source_count == 2


def test_paper_fill_fails_closed_without_execution_evidence(monkeypatch):
    monkeypatch.setattr(p, "_last_price", lambda symbol: 100.0)
    monkeypatch.setattr(p, "get_order_book_intelligence", lambda base: {"reliable": False})
    monkeypatch.setattr(
        p,
        "simulate_market_fill",
        lambda *args: SimpleNamespace(executable=False, reason="insufficient_independent_visible_depth", fill_price=None),
    )
    with pytest.raises(RuntimeError, match="Execution evidence unavailable"):
        p._paper_fill_price("BTC-USDT", "LONG", 4000.0)


def test_liquidation_mark_uses_full_position_and_opposite_side(monkeypatch):
    calls = []
    monkeypatch.setattr(p, "_last_price", lambda symbol: 50.0)
    monkeypatch.setattr(
        p,
        "_paper_fill_price",
        lambda symbol, side, notional: calls.append((symbol, side, notional)) or (50.0, 49.5, SimpleNamespace(source_count=2, worst_slippage_bps=8.0)),
    )
    fill, evidence = p._liquidation_mark({"symbol": "TEST-USDT", "direction": "LONG", "quantity": 20})
    assert fill == 49.5
    assert calls == [("TEST-USDT", "SHORT", 1000.0)]
    assert evidence.source_count == 2


def test_v2_stop_fill_never_benefits_from_recovery(monkeypatch):
    sim = SimpleNamespace(supported_notional=5000.0, worst_slippage_bps=5.0, source_count=2)
    monkeypatch.setattr(p, "_paper_fill_price", lambda *args: (102.0, 102.0, sim))
    trade = {"symbol": "BTC-USDT", "direction": "LONG", "entry_price": 100.0, "stop_loss": 95.0, "target_price": 110.0, "quantity": 10.0, "fee_bps_one_way": 6.0}
    _, fill, pnl, _ = p._v2_exit(trade, 95.0, "STOP")
    assert fill < 95.0
    assert pnl < -50.0


def test_persistent_account_requires_immutable_100k_start():
    valid = {
        "initial_cash": 100000.0,
        "cash": 90000.0,
        "equity": 101000.0,
        "realized_pnl": 500.0,
        "peak_equity": 102000.0,
        "max_drawdown_pct": 1.0,
    }
    p._validate_persistent_account(valid)
    with pytest.raises(RuntimeError, match="immutable"):
        p._validate_persistent_account({**valid, "initial_cash": 50000.0})
    with pytest.raises(RuntimeError, match="finite"):
        p._validate_persistent_account({**valid, "equity": float("nan")})


def test_cross_horizon_opposing_symbol_exposure_is_suppressed():
    open_trades = [{"symbol": "BTC-USDT", "horizon": "24h", "direction": "LONG"}]
    assert p._has_opposing_symbol_exposure(open_trades, "BTC-USDT", "SHORT") is True
    assert p._has_opposing_symbol_exposure(open_trades, "BTC-USDT", "LONG") is False
    assert p._has_opposing_symbol_exposure(open_trades, "ETH-USDT", "SHORT") is False


def test_opposing_symbol_exposure_fails_closed_on_invalid_candidate():
    assert p._has_opposing_symbol_exposure([], "", "LONG") is True
    assert p._has_opposing_symbol_exposure([], "BTC-USDT", "WAIT") is True
