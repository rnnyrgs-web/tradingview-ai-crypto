import market_data


SPOT = {
    "instId": "BTC-USDT",
    "last": "100",
    "open24h": "100",
    "bidPx": "99.99",
    "askPx": "100.01",
    "volCcy24h": "100000000",
}
PONS_TICKER = {
    "instId": "PONS-USDT-SWAP",
    "last": "1",
    "bidPx": "0.99",
    "askPx": "1.01",
    "volCcy24h": "0",
}


def test_forced_pons_is_excluded_when_instrument_is_unavailable(monkeypatch):
    monkeypatch.setattr(market_data, "get_spot_tickers", lambda: [SPOT])

    def fake_okx_get(path, params=None):
        if path == "/api/v5/public/instruments":
            return []
        raise AssertionError(f"unexpected request: {path}")

    monkeypatch.setattr(market_data, "okx_get", fake_okx_get)

    assert all(row["symbol"] != market_data.FORCED_SWAP_SYMBOL
                for row in market_data.build_universe())


def test_forced_pons_is_added_only_for_live_priced_instrument(monkeypatch):
    monkeypatch.setattr(market_data, "get_spot_tickers", lambda: [SPOT])

    def fake_okx_get(path, params=None):
        if path == "/api/v5/public/instruments":
            return [{"instId": market_data.FORCED_SWAP_SYMBOL, "state": "live"}]
        if path == "/api/v5/market/ticker":
            return [PONS_TICKER]
        raise AssertionError(f"unexpected request: {path}")

    monkeypatch.setattr(market_data, "okx_get", fake_okx_get)

    symbols = [row["symbol"] for row in market_data.build_universe()]
    assert market_data.FORCED_SWAP_SYMBOL in symbols
