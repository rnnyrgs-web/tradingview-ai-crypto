from datetime import datetime, timezone
import pytest
from safety import validate_candles, validate_risk, SafetyError

def test_long_risk_invariant():
    validate_risk("LONG",100,95,110,120)

def test_short_risk_invariant():
    validate_risk("SHORT",100,105,90,80)

def test_bad_long_rejected():
    with pytest.raises(SafetyError):
        validate_risk("LONG",100,105,110,120)

def test_nan_risk_rejected():
    with pytest.raises(SafetyError):
        validate_risk("LONG",float("nan"),95,110,120)

def _candles():
    base = int(datetime.now(timezone.utc).timestamp() * 1000) - 40 * 60_000
    return [
        {"ts":base+i*60_000,"open":100.0,"high":101.0,"low":99.0,"close":100.5,"volume":10.0}
        for i in range(40)
    ]

def test_duplicate_timestamp_rejected():
    c = _candles()
    c[20]["ts"] = c[19]["ts"]
    with pytest.raises(SafetyError):
        validate_candles(c,"TEST-USDT","1H")

def test_invalid_ohlc_rejected():
    c = _candles()
    c[10]["close"] = float("nan")
    with pytest.raises(SafetyError):
        validate_candles(c,"TEST-USDT","1H")

def test_future_candle_rejected():
    c = _candles()
    c[-1]["ts"] = int(datetime.now(timezone.utc).timestamp() * 1000) + 60_000
    with pytest.raises(SafetyError):
        validate_candles(c,"TEST-USDT","1H")
