from strategy_families import _regime, _select_pre_oos_regimes


def _candles(prices, spread=0.003):
    rows = []
    for i, price in enumerate(prices):
        rows.append({
            "ts": i,
            "open": price,
            "high": price * (1.0 + spread),
            "low": price * (1.0 - spread),
            "close": price,
            "volume": 1000.0,
        })
    return rows


def test_regime_is_causal_and_ignores_future_candles():
    prices = [100.0 + i * 0.25 for i in range(100)]
    candles = _candles(prices)
    baseline = _regime(candles, 80)

    modified = list(candles)
    for i in range(81, len(modified)):
        modified[i] = dict(modified[i])
        modified[i]["open"] *= 8.0
        modified[i]["high"] *= 8.0
        modified[i]["low"] *= 8.0
        modified[i]["close"] *= 8.0

    assert _regime(modified, 80) == baseline


def test_regime_distinguishes_trend_direction():
    rising = _candles([100.0 + i * 0.35 for i in range(120)])
    falling = _candles([150.0 - i * 0.35 for i in range(120)])
    assert _regime(rising, 110) == "TREND_UP"
    assert _regime(falling, 110) == "TREND_DOWN"


def test_pre_oos_regime_selection_rejects_unproven_states():
    train_records = (
        [{"return_pct": 0.4, "regime": "TREND_UP"}] * 5
        + [{"return_pct": -0.4, "regime": "RANGE"}] * 5
    )
    validation_records = (
        [{"return_pct": 0.3, "regime": "TREND_UP"}] * 4
        + [{"return_pct": -0.2, "regime": "RANGE"}] * 4
    )

    selected, evidence = _select_pre_oos_regimes(train_records, validation_records)

    assert "TREND_UP" in selected
    assert "RANGE" not in selected
    assert evidence["TREND_UP"]["passed_pre_oos"] is True
    assert evidence["RANGE"]["passed_pre_oos"] is False
