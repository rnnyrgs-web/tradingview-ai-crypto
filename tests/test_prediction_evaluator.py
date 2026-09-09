from evaluator import close_at_or_after


def test_prediction_outcome_never_uses_price_before_deadline():
    candles=[{"ts":1000,"close":10.0},{"ts":2000,"close":11.0}]
    assert close_at_or_after(candles,1500) == 11.0
    assert close_at_or_after(candles,3000) is None


def test_prediction_outcome_rejects_first_available_candle_when_too_late():
    candles=[{"ts":10_000,"close":12.0}]
    assert close_at_or_after(candles,1_000,max_lag_ms=2_000) is None


def test_prediction_outcome_accepts_first_candle_within_explicit_tolerance():
    candles=[{"ts":2_500,"close":11.5},{"ts":3_000,"close":12.0}]
    assert close_at_or_after(candles,1_000,max_lag_ms=2_000) == 11.5
