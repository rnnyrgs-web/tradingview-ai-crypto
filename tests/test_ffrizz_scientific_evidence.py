from datetime import datetime, timezone

import ffrizz_secondary_runner as runner


def test_pooled_backtest_is_explicitly_descriptive_not_independent_evidence():
    aggregate = runner._aggregate_backtests([
        {"signals": 10, "accuracy": 0.7, "mean_net_pct": 0.4},
        {"signals": 10, "accuracy": 0.6, "mean_net_pct": 0.2},
    ])
    assert aggregate["signals"] == 20
    assert aggregate["accuracy"] == 0.65
    assert aggregate["descriptive_only"] is True
    assert aggregate["cross_symbol_independence_proven"] is False
    assert aggregate["independent_sample_count"] is None
    assert aggregate["eligible_for_validation_evidence"] is False
    assert aggregate["historical_oi_included"] is False
    assert aggregate["strategy_fingerprint_matches_forward"] is False


def test_forward_ledger_does_not_claim_feature_family_independence():
    report = {
        "horizon_results": [{
            "horizon": "24h",
            "current_shadow_signals": [{
                "action": "SHADOW_BUY",
                "direction": "LONG",
                "entry_price": 100.0,
                "symbol": "BTC-USDT",
                "bar": "1H",
                "score": 3.5,
                "independent_family_agreement": 3,
                "available_family_count": 4,
                "families": [],
            }],
        }],
    }
    rows = runner.build_forward_ledger_rows(
        report,
        generated_at=datetime(2026, 9, 10, 4, 0, tzinfo=timezone.utc),
    )
    assert len(rows) == 1
    calibration = rows[0]["calibration"]
    assert calibration["family_agreement_count"] == 3
    assert calibration["family_agreement_independence_proven"] is False
    assert "independent_family_agreement" not in calibration
    assert calibration["historical_diagnostic_matches_forward_fingerprint"] is False


def test_empty_aggregate_still_fails_closed_as_validation_evidence():
    aggregate = runner._aggregate_backtests([])
    assert aggregate["signals"] == 0
    assert aggregate["accuracy"] is None
    assert aggregate["eligible_for_validation_evidence"] is False
    assert aggregate["cross_symbol_independence_proven"] is False
