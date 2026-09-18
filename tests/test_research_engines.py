import pytest

from research_engines.availability import engine_availability, require_engine
from research_engines.contract import CrossEngineContract
from research_engines.protocol import reconcile


def test_capabilities_never_grant_authority():
    state = engine_availability()
    assert {"vectorbt", "nautilus", "lean"} <= set(state)
    for engine in state.values():
        assert engine["research_only"] is True
        assert engine["trade_authority"] is False
        assert engine["promotion_authority"] is False


def test_unknown_engine_fails_closed():
    with pytest.raises(ValueError):
        require_engine("magic-profit-engine")


def test_contract_requires_frozen_identity_and_next_bar_execution():
    with pytest.raises(ValueError):
        CrossEngineContract("", "BTC-USDT", "1H", "trend", "abc", 10).canonical()
    with pytest.raises(ValueError):
        CrossEngineContract("strategy", "BTC-USDT", "1H", "trend", "data", 10, 0).canonical()


def test_reconciliation_requires_all_engines_same_contract():
    good = {
        "ok": True,
        "contract_fingerprint": "same",
        "metrics": {"trades": 10, "avg_trade_pct": 0.1, "max_drawdown_pct": 2.0},
    }
    result = reconcile({"vectorbt": good, "nautilus": good})
    assert result["ok"] is False
    assert result["status"] == "WAIT_RESEARCH_ONLY"
    assert result["missing_engines"] == ["lean"]

    result = reconcile({"vectorbt": good, "nautilus": good, "lean": {**good, "contract_fingerprint": "different"}})
    assert result["ok"] is False
    assert result["same_contract"] is False
