import pytest

import market_data


def _candle(timestamp):
    return [str(timestamp), "1", "2", "0.5", "1.5", "10", "0", "15", "1"]


def test_normalize_candles_preserves_strict_chronological_order():
    candles = market_data.normalize_candles([
        _candle(3000),
        _candle(2000),
        _candle(1000),
    ])

    assert [candle["ts"] for candle in candles] == [1000, 2000, 3000]


def test_get_history_rejects_duplicate_timestamps_instead_of_deduplicating(monkeypatch):
    monkeypatch.setattr(
        market_data,
        "okx_get",
        lambda path, params: [
            _candle(3000),
            _candle(2000),
            _candle(2000),
            _candle(1000),
        ],
    )

    with pytest.raises(ValueError, match=r"^Duplicate candle timestamp .*: 2000$"):
        market_data.get_history("BTC-USDT", bars=100)


def test_get_history_rejects_non_monotonic_timestamps(monkeypatch):
    monkeypatch.setattr(
        market_data,
        "okx_get",
        lambda path, params: [
            _candle(3000),
            _candle(1000),
            _candle(2000),
        ],
    )

    with pytest.raises(ValueError, match=r"^Non-monotonic candle timestamps .*1000 follows 2000$"):
        market_data.get_history("BTC-USDT", bars=100)


def test_live_candles_use_the_same_fail_closed_timestamp_validation(monkeypatch):
    monkeypatch.setattr(
        market_data,
        "okx_get",
        lambda path, params: [_candle(3000), _candle(1000), _candle(2000)],
    )

    with pytest.raises(ValueError, match="Non-monotonic candle timestamps"):
        market_data.get_candles("BTC-USDT")
