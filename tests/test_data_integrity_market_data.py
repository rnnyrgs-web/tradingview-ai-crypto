import pytest

import market_data


def candle(ts, confirm="1"):
    return [str(ts), "10", "11", "9", "10.5", "2", "20", "21", confirm]


def test_normalize_rejects_duplicate_timestamps():
    with pytest.raises(ValueError, match="duplicated"):
        market_data.normalize_candles([candle(1_800_000), candle(1_800_000)])


def test_normalize_rejects_non_monotonic_input():
    with pytest.raises(ValueError, match="newest-first"):
        market_data.normalize_candles([candle(1_800_000), candle(900_000), candle(1_350_000)])


def test_normalize_rejects_malformed_ohlc_and_missing_candle():
    malformed = candle(1_800_000)
    malformed[2] = "not-a-price"
    with pytest.raises(ValueError, match="numeric"):
        market_data.normalize_candles([malformed])

    with pytest.raises(ValueError, match="missing"):
        market_data.normalize_candles(
            [candle(1_800_000), candle(900_000)], bar="15m"
        )


def test_get_candles_rejects_stale_response(monkeypatch):
    now_ms = 2_000_000
    monkeypatch.setattr(market_data.time, "time", lambda: now_ms / 1000)
    monkeypatch.setattr(
        market_data,
        "okx_get",
        lambda *_args, **_kwargs: [candle(now_ms - 4 * 900_000)],
    )
    with pytest.raises(ValueError, match="stale"):
        market_data.get_candles("BTC-USDT", bar="15m", limit=1)
