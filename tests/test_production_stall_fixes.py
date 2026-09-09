import config
import engine


def _candidate(symbol="SOPH-USDT", score=-5.0, entry=0.05, atr=0.02):
    return {
        "symbol": symbol,
        "horizons": {
            "24h": {"score": 1.0, "features": {"1H": {"last": entry, "atr": 0.001}}},
            "7d": {"score": score, "features": {"4H": {"last": entry, "atr": atr}}},
        },
    }


def test_unrepresentable_short_risk_fails_closed_without_dropping_safe_horizon():
    eligible, rejected = engine._preflight_opportunity_risk([_candidate()])

    assert rejected == [{"symbol": "SOPH-USDT", "horizon": "7d"}]
    assert len(eligible) == 1
    assert "24h" in eligible[0]["horizons"]
    assert "7d" not in eligible[0]["horizons"]


def test_representable_risk_is_not_filtered():
    eligible, rejected = engine._preflight_opportunity_risk([
        _candidate(score=-1.0, entry=100.0, atr=1.0)
    ])
    assert not rejected
    assert set(eligible[0]["horizons"]) == {"24h", "7d"}


def test_binance_spot_uses_public_market_data_only_host_by_default():
    assert config.BINANCE_SPOT_BASE.startswith("https://")
    assert "data-api.binance.vision" in config.BINANCE_SPOT_BASE
