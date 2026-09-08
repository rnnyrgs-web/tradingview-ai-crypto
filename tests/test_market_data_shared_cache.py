import market_data


def _rows():
    return [
        {
            "ts": 1_900_000_000_000,
            "open": 100.0,
            "high": 101.0,
            "low": 99.0,
            "close": 100.5,
            "volume": 10.0,
            "quote_volume": 1000.0,
        }
    ]


def test_get_history_uses_shared_cache_before_network(monkeypatch):
    expected = _rows()
    market_data.clear_history_cache()
    monkeypatch.setattr(market_data, "read_shared_history", lambda *args, **kwargs: expected)

    def network_must_not_run(*args, **kwargs):
        raise AssertionError("network should not run on a valid shared-cache hit")

    monkeypatch.setattr(market_data, "okx_get", network_must_not_run)
    result = market_data.get_history("BTC-USDT", "1H", bars=100, max_bars=50000)
    assert result == expected
    assert result is not expected


def test_shared_cache_result_is_defensively_copied(monkeypatch):
    expected = _rows()
    market_data.clear_history_cache()
    monkeypatch.setattr(market_data, "read_shared_history", lambda *args, **kwargs: expected)
    result = market_data.get_history("ETH-USDT", "1H", bars=100, max_bars=50000)
    result[0]["close"] = -1
    again = market_data.get_history("ETH-USDT", "1H", bars=100, max_bars=50000)
    assert again[0]["close"] == 100.5
