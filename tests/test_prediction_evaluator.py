from datetime import datetime, timedelta, timezone

import evaluator
from evaluator import close_at_or_after, nearest_close


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


def test_legacy_signal_resolution_rejects_stale_and_pre_deadline_fallback_prices():
    assert nearest_close([{"ts":10_000,"close":12.0}],1_000,max_lag_ms=2_000) is None
    assert nearest_close([{"ts":500,"close":9.0}],1_000,max_lag_ms=2_000) is None
    assert nearest_close([{"ts":2_500,"close":11.5}],1_000,max_lag_ms=2_000) == 11.5


def test_run_evaluation_does_not_persist_outcomes_across_a_market_data_gap(monkeypatch):
    now = datetime(2026, 9, 24, 12, 0, tzinfo=timezone.utc)
    created = now - timedelta(hours=2)
    signal = {
        "id": "legacy-gap",
        "symbol": "BTC-USDT",
        "created_at": created.isoformat(),
        "entry_price": 100.0,
        "direction": "LONG",
        "timeframe": "24h",
        "status": "PENDING",
    }
    stale_ts = int((created + timedelta(hours=1, minutes=30)).timestamp() * 1000)
    patches = []
    monkeypatch.setattr(evaluator, "now_utc", lambda: now)
    monkeypatch.setattr(evaluator, "fetch_recent", lambda **kwargs: [signal])
    monkeypatch.setattr(evaluator, "get_candles", lambda *args, **kwargs: [{"ts": stale_ts, "close": 125.0}])
    monkeypatch.setattr(evaluator, "patch_signal", lambda signal_id, fields: patches.append((signal_id, fields)))
    monkeypatch.setattr(
        evaluator,
        "run_prediction_drain",
        lambda: {"errors": [], "predictions_checked": 0, "predictions_updated": 0},
    )

    report = evaluator.run_evaluation()

    assert report["ok"] is True
    assert report["updated"] == 1
    assert "price_15m" not in patches[0][1]
    assert "return_15m" not in patches[0][1]
    assert "price_1h" not in patches[0][1]
    assert "return_1h" not in patches[0][1]
