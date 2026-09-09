import math

import kraken_execution as ke


def test_short_liquidation_uses_two_leg_usd_bridge_when_direct_pair_missing(monkeypatch):
    books = {
        ("FET", "USDT"): RuntimeError("kraken_pair_unavailable"),
        ("FET", "USD"): (
            "FETUSD",
            {
                "bids": [[0.1800, 50000], [0.1790, 50000]],
                "asks": [[0.1810, 50000]],
            },
        ),
        ("USDT", "USD"): (
            "USDTUSD",
            {
                "bids": [[0.9998, 50000]],
                "asks": [[1.0002, 50000], [1.0003, 50000]],
            },
        ),
    }

    def fake_fetch_depth(base, quote, count=500):
        value = books[(base, quote)]
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(ke, "_fetch_depth", fake_fetch_depth)
    result = ke.simulate_kraken_market_fill("FET-USDT", "SHORT", 7200.0, "tier1")

    assert result.executable is True
    assert result.reason == "ok_kraken_usd_bridge_visible_depth_taker"
    assert result.source_count == 2
    assert result.fill_price is not None and 0 < result.fill_price < 0.18
    assert result.raw_vwap is not None and result.raw_vwap > result.fill_price
    assert result.fee_bps == 100.0  # 80 bps crypto leg + 20 bps stable/FX leg
    assert result.levels_used >= 2
    assert result.supported_notional is not None and result.supported_notional >= 7200.0
    assert math.isfinite(result.worst_slippage_bps)


def test_long_entry_does_not_use_usd_bridge(monkeypatch):
    def fake_fetch_depth(base, quote, count=500):
        raise RuntimeError("kraken_pair_unavailable")

    monkeypatch.setattr(ke, "_fetch_depth", fake_fetch_depth)
    result = ke.simulate_kraken_market_fill("FET-USDT", "LONG", 7200.0, "tier1")

    assert result.executable is False
    assert result.reason == "kraken_pair_unavailable"
    assert result.source_count == 1


def test_usd_bridge_fails_closed_when_second_leg_has_insufficient_depth(monkeypatch):
    books = {
        ("FET", "USDT"): RuntimeError("kraken_pair_unavailable"),
        ("FET", "USD"): (
            "FETUSD",
            {"bids": [[0.18, 100000]], "asks": [[0.181, 100000]]},
        ),
        ("USDT", "USD"): (
            "USDTUSD",
            {"bids": [[0.9998, 10]], "asks": [[1.0002, 10]]},
        ),
    }

    def fake_fetch_depth(base, quote, count=500):
        value = books[(base, quote)]
        if isinstance(value, Exception):
            raise value
        return value

    monkeypatch.setattr(ke, "_fetch_depth", fake_fetch_depth)
    result = ke.simulate_kraken_market_fill("FET-USDT", "SHORT", 7200.0, "tier1")

    assert result.executable is False
    assert result.reason == "insufficient_kraken_visible_depth_usd_bridge_leg2"
    assert result.source_count == 2
