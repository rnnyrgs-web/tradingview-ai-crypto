import research_adaptive_accuracy_runner as runner


def _report(eligible):
    return {
        "system": "FFRIZZ_SECONDARY_V1",
        "generated_at": "2026-09-10T11:00:00+00:00",
        "forward_evidence": {
            "eligible_shadow_forecasts": eligible,
            "non_overlapping_full_horizon_buckets": True,
            "wait_rows_persisted": False,
            "historical_oi_backfill_used": False,
        },
    }


def test_eligible_ffrizz_collection_fails_closed_without_prediction_ledger(monkeypatch):
    monkeypatch.setattr(runner, "run_ffrizz_secondary", lambda persist=True: _report(3))
    monkeypatch.setattr(runner, "prediction_ledger_configured", lambda: False)

    result = runner._ffrizz_forward_collection()

    assert result["ok"] is False
    assert result["error_type"] == "PredictionLedgerNotConfigured"
    assert result["eligible_shadow_forecasts"] == 3
    assert result["trade_authority"] is False
    assert result["promotion_authority"] is False


def test_all_wait_ffrizz_cycle_does_not_require_ledger_write(monkeypatch):
    monkeypatch.setattr(runner, "run_ffrizz_secondary", lambda persist=True: _report(0))
    monkeypatch.setattr(runner, "prediction_ledger_configured", lambda: False)

    result = runner._ffrizz_forward_collection()

    assert result["ok"] is True
    assert result["eligible_shadow_forecasts"] == 0
