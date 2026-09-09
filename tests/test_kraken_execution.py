import math

import kraken_execution as k


def test_official_conservative_spot_taker_schedule():
    assert k.kraken_taker_fee_bps("BTC-USDT", "tier1") == 80.0
    assert k.kraken_taker_fee_bps("ETH-USDT", "tier3") == 38.0
    assert k.kraken_taker_fee_bps("BTC-USDT", "pro5") == 5.0


def test_quote_stablecoin_still_uses_spot_crypto_schedule():
    assert k.kraken_taker_fee_bps("BTC-USDT", "tier1") == 80.0
    assert k.kraken_taker_fee_bps("ETH-USDC", "tier1") == 80.0


def test_stablecoin_base_uses_stable_fx_schedule():
    assert k.kraken_taker_fee_bps("USDT-USD", "tier1") == 20.0
    assert k.kraken_taker_fee_bps("USDC-USDT", "tier1") == 20.0


def test_unknown_fee_tier_fails_closed():
    try:
        k.kraken_taker_fee_bps("BTC-USDT", "mystery")
    except ValueError as exc:
        assert "unverified_kraken_fee_tier" in str(exc)
    else:
        raise AssertionError("unknown tier must fail closed")


def test_kraken_full_depth_vwap_and_fee(monkeypatch):
    book = {
        "asks": [["100", "5", "0"], ["101", "10", "0"]],
        "bids": [["99", "5", "0"], ["98", "10", "0"]],
    }
    monkeypatch.setattr(k, "_fetch_depth", lambda base, quote: ("BTCUSDT", book))
    result = k.simulate_kraken_market_fill("BTC-USDT", "LONG", 1000.0, "tier1")
    assert result.executable is True
    assert result.raw_vwap is not None
    assert result.fill_price is not None
    assert result.fill_price > result.raw_vwap
    assert math.isclose(result.fill_price / result.raw_vwap, 1.008, rel_tol=1e-9)
    assert result.fee_bps == 80.0
    assert result.levels_used >= 2


def test_kraken_sell_fill_charges_fee_conservatively(monkeypatch):
    book = {
        "asks": [["101", "10", "0"]],
        "bids": [["100", "10", "0"]],
    }
    monkeypatch.setattr(k, "_fetch_depth", lambda base, quote: ("BTCUSDT", book))
    result = k.simulate_kraken_market_fill("BTC-USDT", "SHORT", 500.0, "tier1")
    assert result.executable is True
    assert result.raw_vwap == 100.0
    assert result.fill_price == 99.2


def test_insufficient_visible_depth_fails_closed(monkeypatch):
    book = {"asks": [["100", "1", "0"]], "bids": [["99", "1", "0"]]}
    monkeypatch.setattr(k, "_fetch_depth", lambda base, quote: ("BTCUSDT", book))
    result = k.simulate_kraken_market_fill("BTC-USDT", "LONG", 1000.0, "tier1")
    assert result.executable is False
    assert result.reason == "insufficient_kraken_visible_depth"
    assert result.fill_price is None
