from datetime import datetime, timezone

from ffrizz_secondary_runner import UNCLASSIFIED_MARKET_REGIME, build_forward_ledger_rows


def test_ffrizz_forward_ledger_rows_use_truthful_non_null_unclassified_regime():
    report = {
        "horizon_results": [
            {
                "horizon": "24h",
                "current_shadow_signals": [
                    {
                        "action": "SHADOW_BUY",
                        "direction": "LONG",
                        "entry_price": 100.0,
                        "symbol": "BTC-USDC",
                        "score": 72.0,
                        "bar": "1H",
                        "independent_family_agreement": 3,
                        "available_family_count": 3,
                        "families": [],
                    }
                ],
            }
        ]
    }

    rows = build_forward_ledger_rows(
        report,
        generated_at=datetime(2026, 9, 12, 11, 0, tzinfo=timezone.utc),
    )

    assert len(rows) == 1
    row = rows[0]
    assert row["market_regime"] == UNCLASSIFIED_MARKET_REGIME == "UNCLASSIFIED"
    assert row["market_regime"] is not None
    assert row["action_at_forecast"] == "WAIT"
    assert row["calibration"]["market_regime_source"] == "unavailable_at_forecast"
    assert row["calibration"]["trade_authority"] is False
    assert row["calibration"]["promotion_authority"] is False
