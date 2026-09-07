from evaluator import close_at_or_after


def test_prediction_outcome_never_uses_price_before_deadline():
    candles=[{"ts":1000,"close":10.0},{"ts":2000,"close":11.0}]
    assert close_at_or_after(candles,1500) == 11.0
    assert close_at_or_after(candles,3000) is None
