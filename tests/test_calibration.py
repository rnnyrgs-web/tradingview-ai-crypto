from calibration import (
    calibration_assessment,
    calibration_summary,
    deterioration_assessment,
    score_bin,
    wilson_lower_bound,
)


def test_score_bins_are_bounded():
    assert score_bin(-1) == (0, 10)
    assert score_bin(56) == (50, 60)
    assert score_bin(100) == (90, 100)


def test_calibration_fails_closed_without_enough_samples():
    rows=[{"horizon":"24h","score":75,"market_regime":"BULL","correct":True} for _ in range(29)]
    result=calibration_assessment(75,"24h",rows,"BULL")
    assert result["ready"] is False
    assert result["empirical_precision"] is None
    assert result["allows_live_action"] is False


def test_calibration_uses_conservative_lower_bound():
    strong=[{"horizon":"24h","score":75,"market_regime":"BULL","correct":i<28} for i in range(30)]
    weak=[{"horizon":"7d","score":75,"market_regime":"BULL","correct":i<16} for i in range(30)]
    assert calibration_assessment(75,"24h",strong,"BULL")["allows_live_action"] is True
    assert calibration_assessment(75,"7d",weak,"BULL")["allows_live_action"] is False
    assert wilson_lower_bound(0,0) == 0.0


def _dated_rows(prior_correct, recent_correct):
    rows=[]
    for i in range(40):
        rows.append({
            "horizon":"24h","score":75,"market_regime":"BULL",
            "correct": i < prior_correct,
            "resolved_at":f"2026-01-{i+1:02d}T00:00:00Z",
        })
    for i in range(20):
        rows.append({
            "horizon":"24h","score":75,"market_regime":"BULL",
            "correct": i < recent_correct,
            "resolved_at":f"2026-03-{i+1:02d}T00:00:00Z",
        })
    return rows


def test_recent_deterioration_blocks_strong_long_run_calibration():
    rows=_dated_rows(38,7)
    result=calibration_assessment(75,"24h",rows,"BULL")
    assert result["ready"] is True
    assert result["precision_95pct_lower"] >= 0.50
    assert result["deterioration"]["ready"] is True
    assert result["deterioration"]["deteriorating"] is True
    assert result["restriction_reason"] == "RECENT_FORECAST_DETERIORATION"
    assert result["allows_live_action"] is False


def test_recent_performance_that_remains_healthy_does_not_trigger_demotion():
    rows=_dated_rows(34,17)
    result=deterioration_assessment(rows)
    assert result["ready"] is True
    assert result["deteriorating"] is False


def test_deterioration_needs_both_recent_and_prior_samples():
    rows=[{"correct":True,"resolved_at":f"2026-01-{i+1:02d}T00:00:00Z"} for i in range(25)]
    result=deterioration_assessment(rows)
    assert result["ready"] is False
    assert result["deteriorating"] is False


def test_summary_keeps_horizons_separate():
    rows=[{"horizon":"24h","correct":True},{"horizon":"24h","correct":False},{"horizon":"7d","correct":True}]
    summary=calibration_summary(rows)
    assert summary["horizons"][0]["precision"] == 0.5
    assert summary["horizons"][1]["precision"] == 1.0
    assert summary["horizons"][0]["deterioration"]["ready"] is False
