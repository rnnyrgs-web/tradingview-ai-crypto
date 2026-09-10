from datetime import datetime, timezone

import ffrizz_secondary_runner as runner


def _report(action="SHADOW_BUY", direction="LONG", score=3.5):
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
                        "score": score,
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
    assert row["score"] == 3.5
    assert row["calibration"]["raw_score"] == 3.5
    assert row["calibration"]["shadow_action"] == "SHADOW_BUY"
    assert row["calibration"]["production_action_semantics"] == "WAIT"
    assert row["calibration"]["trade_authority"] is False
    assert row["calibration"]["promotion_authority"] is False


def test_shadow_sell_uses_nonnegative_ledger_strength_and_preserves_signed_raw_score():
    rows = runner.build_forward_ledger_rows(
        _report(action="SHADOW_SELL", direction="SHORT", score=-3.5),
        generated_at=datetime(2026, 9, 10, 7, 0, tzinfo=timezone.utc),
    )
    assert len(rows) == 1
    row = rows[0]
    assert row["direction"] == "SHORT"
    assert row["action_at_forecast"] == "WAIT"
    assert row["score"] == 3.5
    assert 0.0 <= row["score"] <= 100.0
    assert row["calibration"]["raw_score"] == -3.5
    assert row["calibration"]["ledger_score_semantics"] == "absolute_shadow_strength"
    assert row["calibration"]["shadow_action"] == "SHADOW_SELL"


def test_source_wait_still_creates_no_forward_evidence():
    rows = runner.build_forward_ledger_rows(
        _report(action="WAIT"), generated_at=datetime(2026, 9, 10, 7, 0, tzinfo=timezone.utc)
    )
    assert rows == []
