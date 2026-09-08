import paper_dashboard as d


def test_live_position_matches_equity_mark_without_double_counting_entry_fee(monkeypatch):
    monkeypatch.setattr(d, "_last_price", lambda symbol: 99.0)
    trade = {
        "symbol": "TEST-USDT",
        "direction": "LONG",
        "entry_price": 100.0,
        "quantity": 10.0,
        "notional_usd": 1000.0,
        "fee_bps_one_way": 6.0,
    }
    marked = d._live_position(trade)
    assert marked["live_pnl"] == -10.0
    assert marked["live_pnl_pct"] == -1.0


def test_reconciled_totals_are_exact_identity():
    status = {"starting_capital_usd": 100000.0, "realized_pnl_usd": 2628.40}
    positions = [{"live_pnl": -357.33}, {"live_pnl": -186.68}, {"live_pnl": -5.76}, {"live_pnl": -140.71}, {"live_pnl": -418.21}]
    initial, realized, open_pnl, total_pnl, equity = d._reconciled_totals(status, positions)
    assert round(open_pnl, 2) == -1108.69
    assert round(total_pnl, 2) == 1519.71
    assert round(equity, 2) == 101519.71
    assert round(total_pnl, 2) == round(realized + open_pnl, 2)
    assert round(equity, 2) == round(initial + total_pnl, 2)
