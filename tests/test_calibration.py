from datetime import datetime, timedelta, timezone

from calibration import (
    calibration_assessment,
    calibration_summary,
    deterioration_assessment,
    score_bin,
    wilson_lower_bound,
)


def _resolved_row(index, *, horizon="24h", score=75, regime="BULL", correct=True, spacing=None):
    span = timedelta(hours=24) if horizon == "24h" else timedelta(days=7)
    step = spacing or span
    origin = datetime(2026, 1, 1, tzinfo=timezone.utc) + step * index
    due = origin + span
    return {
        "scan_id": f"scan-{index}",
        "symbol": "BTC-USDT",
        "horizon": horizon,
        "score": score,
        "market_regime": regime,
        "correct": bool(correct),
        "due_at": due.isoformat(),
        "resolved_at": due.isoformat(),
    }


def test_score_bins_are_bounded():
    assert score_bin(-1) == (0, 10)
    assert score_bin(56) == (50, 60)
    assert score_bin(100) == (90, 100)


def test_calibration_fails_closed_without_enough_independent_samples():
    rows = [_resolved_row(i, correct=True) for i in range(29)]
    result = calibration_assessment(75, "24h", rows, "BULL")
    assert result["ready"] is False
    assert result["independent_samples"] == 29
    assert result["empirical_precision"] is None
    assert result["allows_live_action"] is False


def test_many_overlapping_rows_do_not_fake_calibration_readiness():
    rows = [_resolved_row(i, correct=True, spacing=timedelta(minutes=15)) for i in range(120)]
    result = calibration_assessment(75, "24h", rows, "BULL")
    assert result["raw_matching_rows"] == 120
    assert result["independent_samples"] < 30
    assert result["ready"] is False
    assert result["allows_live_action"] is False


def test_missing_chronology_cannot_count_toward_live_calibration():
    rows = [{"horizon": "24h", "score": 75, "market_regime": "BULL", "correct": True} for _ in range(100)]
    result = calibration_assessment(75, "24h", rows, "BULL")
    assert result["raw_matching_rows"] == 100
    assert result["independent_samples"] == 0
    assert result["ready"] is False
    assert result["allows_live_action"] is False


def test_calibration_uses_conservative_lower_bound_on_independent_rows():
    strong = [_resolved_row(i, correct=i < 28) for i in range(30)]
    weak = [_resolved_row(i, horizon="7d", correct=i < 16) for i in range(30)]
    assert calibration_assessment(75, "24h", strong, "BULL")["allows_live_action"] is True
    assert calibration_assessment(75, "7d", weak, "BULL")["allows_live_action"] is False
    assert wilson_lower_bound(0, 0) == 0.0


def _dated_rows(prior_correct, recent_correct):
    rows = []
    for i in range(60):
        correct = i < prior_correct if i < 40 else (i - 40) < recent_correct
        rows.append(_resolved_row(i, correct=correct))
    return rows


def test_recent_deterioration_blocks_strong_long_run_calibration():
    rows = _dated_rows(38, 7)
    result = calibration_assessment(75, "24h", rows, "BULL")
    assert result["ready"] is True
    assert result["precision_95pct_lower"] >= 0.50
    assert result["deterioration"]["ready"] is True
    assert result["deterioration"]["deteriorating"] is True
    assert result["restriction_reason"] == "RECENT_FORECAST_DETERIORATION"
    assert result["allows_live_action"] is False


def test_recent_performance_that_remains_healthy_does_not_trigger_demotion():
    rows = _dated_rows(34, 17)
    result = deterioration_assessment(rows)
    assert result["ready"] is True
    assert result["deteriorating"] is False


def test_deterioration_needs_both_recent_and_prior_samples():
    rows = [_resolved_row(i, correct=True) for i in range(25)]
    result = deterioration_assessment(rows)
    assert result["ready"] is False
    assert result["deteriorating"] is False


def test_summary_reports_raw_and_independent_counts_separately():
    rows = [
        _resolved_row(0, correct=True),
        _resolved_row(1, correct=False),
        _resolved_row(0, horizon="7d", correct=True),
    ]
    summary = calibration_summary(rows)
    by_horizon = {item["horizon"]: item for item in summary["horizons"]}
    assert by_horizon["24h"]["precision"] == 0.5
    assert by_horizon["24h"]["raw_resolved_rows"] == 2
    assert by_horizon["24h"]["independent_samples"] == 2
    assert by_horizon["7d"]["precision"] == 1.0
    assert by_horizon["7d"]["independent_samples"] == 1
    assert by_horizon["24h"]["deterioration"]["ready"] is False
