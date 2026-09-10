import math

import kraken_execution as k


def _depth(base, quote):
    if (base, quote) == ("MINA", "USDT"):
        raise RuntimeError("kraken_pair_unavailable")
    if (base, quote) == ("USDT", "USD"):
        return "USDTUSD", {
            "bids": [["1.0000", "20000", "0"]],
            "asks": [["1.0001", "20000", "0"]],
        }
    if (base, quote) == ("MINA", "USD"):
        return "MINAUSD", {
            "bids": [["0.099", "200000", "0"]],
            "asks": [["0.100", "200000", "0"]],
        }
    raise RuntimeError("unexpected_pair")


def test_long_entry_can_use_fully_visible_kraken_usd_bridge(monkeypatch):
    monkeypatch.setattr(k, "_fetch_depth", _depth)

    result = k.simulate_kraken_market_fill("MINA-USDT", "LONG", 1000.0, "tier1")

    assert result.executable is True
    assert result.reason == "ok_kraken_usd_bridge_visible_depth_taker_entry"
    assert result.source_count == 2
    assert result.fee_bps == 100.0
    assert math.isclose(result.raw_vwap, 0.1, rel_tol=1e-12)
    assert result.fill_price > result.raw_vwap
    assert math.isclose(result.fill_price, 0.1 * 1.008 / 0.998, rel_tol=1e-12)
    assert result.supported_notional is not None
    assert result.supported_notional >= 1000.0


def test_usd_bridge_entry_fails_closed_if_second_leg_has_insufficient_depth(monkeypatch):
    def shallow_depth(base, quote):
        if (base, quote) == ("MINA", "USDT"):
            raise RuntimeError("kraken_pair_unavailable")
        if (base, quote) == ("USDT", "USD"):
            return "USDTUSD", {"bids": [["1.0", "20000", "0"]], "asks": [["1.0", "20000", "0"]]}
        if (base, quote) == ("MINA", "USD"):
            return "MINAUSD", {"asks": [["0.1", "100", "0"]], "bids": [["0.099", "100", "0"]]}
        raise RuntimeError("unexpected_pair")

    monkeypatch.setattr(k, "_fetch_depth", shallow_depth)
    result = k.simulate_kraken_market_fill("MINA-USDT", "LONG", 1000.0, "tier1")

    assert result.executable is False
    assert result.reason == "insufficient_kraken_visible_depth_usd_bridge_leg2"
    assert result.fill_price is None


def test_non_bridge_quote_still_fails_closed_when_direct_market_is_missing(monkeypatch):
    monkeypatch.setattr(k, "_fetch_depth", lambda *args: (_ for _ in ()).throw(RuntimeError("kraken_pair_unavailable")))

    result = k.simulate_kraken_market_fill("MINA-EUR", "LONG", 1000.0, "tier1")

    assert result.executable is False
    assert result.reason == "kraken_pair_unavailable"
