import db
from opportunity_engine import _preforecast_market_context


def test_preforecast_context_preserves_independent_quote_timestamps():
    candidate = {
        "market_consensus": {
            "reliable": True,
            "reason": "ok",
            "source_count": 2,
            "required_source_count": 2,
            "price_range_bps": 4.5,
            "max_quote_age_seconds": 1.5,
            "confidence_multiplier": 1.0,
            "quotes": [
                {"exchange": "okx", "observed_ms": 1_700_000_000_000, "price": 100.0},
                {"exchange": "binance", "observed_ms": 1_700_000_000_500, "price": 100.02},
            ],
            "provenance": {"accepted_exchange_names": ["okx", "binance"]},
        }
    }
    context = _preforecast_market_context(candidate, "2023-11-14T22:13:21+00:00")
    market = context["market_consensus"]
    assert market["recorded"] is True
    assert market["reliable_at_forecast"] is True
    assert market["independent_source_count"] == 2
    assert market["accepted_exchange_names"] == ["binance", "okx"]
    assert market["accepted_observations"] == [
        {"exchange": "binance", "observed_ms": 1_700_000_000_500},
        {"exchange": "okx", "observed_ms": 1_700_000_000_000},
    ]


def test_resolved_research_exposes_only_timestamp_safe_consensus():
    safe = {
        "calibration": {
            "preforecast_market_context": {
                "captured_at": "2023-11-14T22:13:21+00:00",
                "market_consensus": {
                    "recorded": True,
                    "reliable_at_forecast": True,
                    "independent_source_count": 2,
                    "required_source_count": 2,
                    "accepted_exchange_names": ["okx", "binance"],
                    "accepted_observations": [
                        {"exchange": "okx", "observed_ms": 1_700_000_000_000},
                        {"exchange": "binance", "observed_ms": 1_700_000_000_500},
                    ],
                },
            }
        }
    }
    out = db._expose_preforecast_market_fields(safe)
    assert out["market_consensus_reliable"] is True
    assert out["market_consensus_timestamp_safe"] is True
    assert out["market_consensus_source_count"] == 2

    future_quote = {
        "calibration": {
            "preforecast_market_context": {
                "captured_at": "2023-11-14T22:13:20+00:00",
                "market_consensus": {
                    "recorded": True,
                    "reliable_at_forecast": True,
                    "independent_source_count": 2,
                    "required_source_count": 2,
                    "accepted_observations": [
                        {"exchange": "okx", "observed_ms": 1_700_000_001_000},
                    ],
                },
            }
        }
    }
    out = db._expose_preforecast_market_fields(future_quote)
    assert out["market_consensus_reliable"] is False
    assert out["market_consensus_timestamp_safe"] is False


def test_historical_rows_are_not_backfilled_with_missing_consensus():
    historical = {"horizon": "24h", "score": 80.0, "calibration": {"status": "CALIBRATING"}}
    out = db._expose_preforecast_market_fields(historical)
    assert "market_consensus_reliable" not in out
    assert "market_consensus_timestamp_safe" not in out


def test_shadow_learning_read_includes_calibration_and_exposes_safe_consensus(monkeypatch):
    row = {
        "horizon": "24h",
        "resolved_at": "2023-11-15T22:13:21+00:00",
        "correct": True,
        "calibration": {
            "preforecast_market_context": {
                "captured_at": "2023-11-14T22:13:21+00:00",
                "market_consensus": {
                    "recorded": True,
                    "reliable_at_forecast": True,
                    "independent_source_count": 2,
                    "required_source_count": 2,
                    "accepted_observations": [
                        {"exchange": "okx", "observed_ms": 1_700_000_000_000},
                        {"exchange": "binance", "observed_ms": 1_700_000_000_500},
                    ],
                },
            }
        },
    }

    class Response:
        status_code = 200
        text = ""

        def json(self):
            return [row]

    captured = {}

    class HTTP:
        def get(self, url, headers=None, params=None):
            captured["params"] = params
            return Response()

    monkeypatch.setattr(db, "configured", lambda: True)
    monkeypatch.setattr(db, "http", HTTP())
    out = db.fetch_shadow_predictions(limit=10)
    assert "calibration" in captured["params"]["select"].split(",")
    assert out[0]["market_consensus_reliable"] is True
    assert out[0]["market_consensus_timestamp_safe"] is True
