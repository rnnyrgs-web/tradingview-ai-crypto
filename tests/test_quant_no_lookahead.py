from copy import deepcopy

import pytest

from strategy_families import SIGNAL_FUNCTIONS


def _candles(count=100, decision_index=80):
    candles = []
    for index in range(count):
        close = 100.0 + index * 0.2
        candles.append(
            {
                "ts": index * 60_000,
                "open": close - 0.1,
                "high": close + 0.15,
                "low": close - 0.15,
                "close": close,
                "volume": 100.0,
            }
        )

    decision = candles[decision_index]
    decision["close"] += 5.0
    decision["open"] = decision["close"] - 2.0
    decision["high"] = decision["close"] + 0.2
    decision["low"] = decision["open"] - 0.2
    decision["volume"] = 1_000.0
    return candles


@pytest.mark.parametrize("family", sorted(SIGNAL_FUNCTIONS))
def test_future_candles_cannot_change_signal_at_decision_timestamp(family):
    decision_index = 80
    candles = _candles(decision_index=decision_index)
    changed = deepcopy(candles)
    decision_timestamp = candles[decision_index]["ts"]

    for index, candle in enumerate(changed[decision_index + 1 :], decision_index + 1):
        assert candle["ts"] > decision_timestamp
        scale = 10_000.0 if index % 2 else 0.01
        candle.update(
            {
                "open": scale,
                "high": scale * 1.2,
                "low": scale * 0.8,
                "close": scale * 1.1,
                "volume": scale * 1_000.0,
            }
        )

    benchmark = {candle["ts"]: 100.0 for candle in candles}
    signal = SIGNAL_FUNCTIONS[family]

    assert changed[: decision_index + 1] == candles[: decision_index + 1]
    assert signal(changed, decision_index, benchmark) == signal(
        candles, decision_index, benchmark
    )
