from datetime import datetime, timezone

import combined_dashboard as dashboard


def _v2_trade(**overrides):
    row = {
        "opened_at": "2026-09-14T17:00:00Z",
        "execution_model_version": dashboard.V2_EXECUTION_MODEL,
    }
    row.update(overrides)
    return row


def test_post_fix_trade_cutover_requires_verified_production_activation(monkeypatch):
    monkeypatch.setattr(dashboard, "_VERIFIED_CUTOVER_DT", None)
    assert dashboard._measurement_cohort(_v2_trade()) == "UNVERIFIED"

    monkeypatch.setattr(
        dashboard,
        "_VERIFIED_CUTOVER_DT",
        datetime(2026, 9, 14, 16, 45, tzinfo=timezone.utc),
    )
    assert dashboard._measurement_cohort(_v2_trade(opened_at="2026-09-14T16:44:59Z")) == "UNVERIFIED"
    assert dashboard._measurement_cohort(_v2_trade(opened_at="2026-09-14T16:45:00Z")) == "POST-FIX CLEAN"
    assert dashboard._measurement_cohort(_v2_trade(execution_model_version="legacy_v1")) == "UNVERIFIED"
    assert dashboard._measurement_cohort({}) == "UNVERIFIED"
    assert dashboard._measurement_cohort({"opened_at": "not-a-date"}) == "UNVERIFIED"


def test_closed_metrics_compute_forward_economics_without_hiding_invalid_rows():
    trades = [
        {"closed_at": "2026-09-14T17:00:00Z", "pnl_usd": 100},
        {"closed_at": "2026-09-14T18:00:00Z", "pnl_usd": -50},
    ]
    metrics = dashboard._closed_metrics(trades)
    assert metrics["raw_count"] == 2
    assert metrics["count"] == 2
    assert metrics["invalid_count"] == 0
    assert metrics["complete"] is True
    assert metrics["wins"] == 1
    assert metrics["losses"] == 1
    assert metrics["realized_pnl"] == 50
    assert metrics["win_rate"] == 50
    assert metrics["profit_factor"] == 2
    assert metrics["expectancy"] == 25
    assert metrics["realized_sequence_drawdown_usd"] == 50


def test_legacy_and_unverified_rows_cannot_contaminate_clean_forward_metrics(monkeypatch):
    monkeypatch.setattr(
        dashboard,
        "_VERIFIED_CUTOVER_DT",
        datetime(2026, 9, 14, 16, 45, tzinfo=timezone.utc),
    )
    trades = [
        _v2_trade(
            opened_at="2026-09-14T16:00:00Z",
            closed_at="2026-09-14T17:00:00Z",
            pnl_usd=-900,
        ),
        _v2_trade(
            opened_at="2026-09-14T16:40:00Z",
            closed_at="2026-09-14T17:30:00Z",
            pnl_usd=-400,
        ),
        _v2_trade(
            opened_at="2026-09-14T16:46:00Z",
            closed_at="2026-09-14T18:00:00Z",
            pnl_usd=100,
        ),
    ]
    clean = [trade for trade in trades if dashboard._measurement_cohort(trade) == "POST-FIX CLEAN"]
    metrics = dashboard._closed_metrics(clean)
    assert metrics["count"] == 1
    assert metrics["realized_pnl"] == 100
    assert metrics["win_rate"] == 100


def test_forward_summary_sample_floor_remains_30():
    assert dashboard.MIN_FORWARD_CLOSED_TRADES == 30
