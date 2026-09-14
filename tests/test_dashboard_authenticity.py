from datetime import datetime, timezone

import combined_dashboard as dashboard


def _trade(**overrides):
    row = {
        "opened_at": "2026-09-14T17:00:00Z",
        "execution_model_version": dashboard.V2_EXECUTION_MODEL,
        "pnl_usd": 10.0,
    }
    row.update(overrides)
    return row


def test_post_merge_trade_is_not_clean_without_verified_production_cutover(monkeypatch):
    monkeypatch.setattr(dashboard, "_VERIFIED_CUTOVER_DT", None)
    assert dashboard._measurement_cohort(_trade()) == "UNVERIFIED"


def test_verified_cutover_still_requires_execution_model_provenance(monkeypatch):
    monkeypatch.setattr(
        dashboard,
        "_VERIFIED_CUTOVER_DT",
        datetime(2026, 9, 14, 16, 45, tzinfo=timezone.utc),
    )
    assert dashboard._measurement_cohort(_trade(execution_model_version="legacy_v1")) == "UNVERIFIED"
    assert dashboard._measurement_cohort(_trade()) == "POST-FIX CLEAN"


def test_definitely_pre_merge_trade_remains_legacy(monkeypatch):
    monkeypatch.setattr(dashboard, "_VERIFIED_CUTOVER_DT", None)
    assert dashboard._measurement_cohort(_trade(opened_at="2026-09-14T16:00:00Z")) == "LEGACY"


def test_malformed_pnl_never_becomes_zero_return_sample():
    metrics = dashboard._closed_metrics([
        _trade(pnl_usd=25.0),
        _trade(pnl_usd=None),
        _trade(pnl_usd="not-a-number"),
    ])
    assert metrics["raw_count"] == 3
    assert metrics["count"] == 1
    assert metrics["invalid_count"] == 2
    assert metrics["complete"] is False
    assert metrics["realized_pnl"] == 25.0
    assert metrics["win_rate"] == 100.0


def test_duration_fallback_is_labeled_as_proxy_not_model_estimate():
    duration, source = dashboard._duration({"horizon": "24h"})
    assert duration == "~12–24 hours"
    assert source == "forecast-horizon proxy"


def test_paper_backend_failure_is_explicitly_degraded(monkeypatch):
    def fail():
        raise RuntimeError("db offline")

    monkeypatch.setattr(dashboard, "paper_status", fail)
    snapshot = dashboard._paper_snapshot()
    assert snapshot["data_ok"] is False
    assert snapshot["error"] == "RuntimeError"
    assert snapshot["forward_total_pnl"] is None


def test_stale_or_missing_timestamp_is_not_actionable_freshness():
    fresh, age, reason = dashboard._freshness({})
    assert fresh is False
    assert age is None
    assert reason == "timestamp unavailable"


def test_dashboard_source_cannot_self_declare_proven_positive():
    # Canonical profitability proof belongs to the stricter tournament/proof
    # pipeline, not to a few dashboard summary statistics.
    with open(dashboard.__file__, "r", encoding="utf-8") as handle:
        source = handle.read()
    assert "PROVEN POSITIVE" not in source
    assert "PRELIMINARY FORWARD POSITIVE — NOT PROVEN" in source
    assert "PAPER_GEOMETRY_FIX_CUTOVER_UTC" in source
