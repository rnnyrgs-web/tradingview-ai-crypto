import market_data


def _ticker(symbol, bid, ask):
    return {
        "instId": symbol,
        "last": "100",
        "open24h": "100",
        "bidPx": str(bid),
        "askPx": str(ask),
        "volCcy24h": "1000000",
    }


def test_build_universe_rejects_crossed_quotes(monkeypatch):
    monkeypatch.setattr(
        market_data,
        "get_spot_tickers",
        lambda: [
            _ticker("CROSSED-USDT", 101, 99),
            _ticker("VALID-USDT", 99.99, 100.01),
        ],
    )
    monkeypatch.setattr(market_data, "MIN_QUOTE_VOLUME", 0)
    monkeypatch.setattr(market_data, "UNIVERSE_SIZE", 10)

    symbols = [row["symbol"] for row in market_data.build_universe()]

    assert symbols == ["VALID-USDT"]
