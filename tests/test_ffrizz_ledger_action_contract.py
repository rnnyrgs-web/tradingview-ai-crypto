from datetime import datetime, timezone

import ffrizz_secondary_runner as runner


def _report(action="SHADOW_BUY", direction="LONG"):
    return {
        "horizon_results": [
            {
                "horizon": "6h",
                "current_shadow_signals": [
                    {
                        "symbol": "BTC-USDT",
                        "action": action,
                        "direction": direction,
                        "entry_price": 100.0,
                        "score": 3.5,
                        "bar": "1H",
                        "independent_family_agreement": 3,
                        "available_family_count": 4,
                        "families": [],
                    }
                ],
            }
        ]
    }


def test_shadow_buy_persists_with_canonical_wait_action():
    rows = runner.build_forward_ledger_rows(
        _report(), generated_at=datetime(2026, 9, 10, 7, 0, tzinfo=timezone.utc)
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["direction"] == "LONG"
    assert row["action_at_forecast"] == "WAIT"
    assert row["calibration"]["shadow_action"] == "SHADOW_BUY"
    assert row["calibration"]["production_action_semantics"] == "WAIT"
    assert row["calibration"]["trade_authority"] is False
    assert row["calibration"]["promotion_authority"] is False


def test_shadow_sell_persists_direction_but_never_trade_action():
    rows = runner.build_forward_ledger_rows(
        _report(action="SHADOW_SELL", direction="SHORT"),
        generated_at=datetime(2026, 9, 10, 7, 0, tzinfo=timezone.utc),
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["direction"] == "SHORT"
    assert row["action_at_forecast"] == "WAIT"
    assert row["calibration"]["shadow_action"] == "SHADOW_SELL"


def test_source_wait_still_creates_no_forward_evidence():
    rows = runner.build_forward_ledger_rows(
        _report(action="WAIT"), generated_at=datetime(2026, 9, 10, 7, 0, tzinfo=timezone.utc)
    )
    assert rows == []
