from datetime import timedelta

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


def test_close_decision_hits_stop_target_and_timeout():
    base = {
        "direction": "LONG",
        "stop_loss": 95,
        "target_price": 110,
        "opened_at": (now_utc() - timedelta(hours=2)).isoformat(),
        "horizon": "24h",
    }
    assert p._close_decision(base, 94) == (95.0, "STOP")
    assert p._close_decision(base, 111) == (110.0, "TARGET")
    expired = {**base, "opened_at": (now_utc() - timedelta(hours=25)).isoformat()}
    assert p._close_decision(expired, 102) == (102, "TIME")
