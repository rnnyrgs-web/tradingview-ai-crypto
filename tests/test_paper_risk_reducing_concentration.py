from types import SimpleNamespace

import paper_trading as p


def _trade(direction, notional):
    return {"direction": direction, "notional_usd": notional}


def test_concentration_only_block_is_narrow():
    assert p._concentration_only_block(SimpleNamespace(blocked=True, reasons=("correlated_directional_concentration",))) is True
    assert p._concentration_only_block(SimpleNamespace(blocked=True, reasons=("correlated_directional_concentration", "portfolio_drawdown_limit"))) is False
    assert p._concentration_only_block(SimpleNamespace(blocked=False, reasons=())) is False


def test_opposite_short_must_reduce_absolute_net_directional_notional():
    open_trades = [_trade("LONG", 1000.0) for _ in range(4)]
    assert p._net_directional_notional(open_trades) == 4000.0
    assert p._candidate_reduces_net_directional_exposure(open_trades, "SHORT", 1500.0) is True
    assert p._candidate_reduces_net_directional_exposure(open_trades, "LONG", 500.0) is False
    assert p._candidate_reduces_net_directional_exposure(open_trades, "SHORT", 9000.0) is False


def test_long_can_reduce_short_concentration_symmetrically():
    open_trades = [_trade("SHORT", 1200.0) for _ in range(4)]
    assert p._net_directional_notional(open_trades) == -4800.0
    assert p._candidate_reduces_net_directional_exposure(open_trades, "LONG", 1800.0) is True
    assert p._candidate_reduces_net_directional_exposure(open_trades, "SHORT", 500.0) is False
