from datetime import datetime, timedelta, timezone

from selective_precision import PREDECLARED_THRESHOLDS, selective_precision_assessment


def _rows(n=40, spacing=timedelta(hours=24)):
    rows = []
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    for i in range(n):
        score = 95 if i < 10 else 85 if i < 20 else 75 if i < 30 else 65
        origin = start + spacing * i
        due = origin + timedelta(hours=24)
        rows.append({
            "horizon": "24h",
            "score": score,
            "correct": i < 30,
            "market_consensus_reliable": True,
            "due_at": due.isoformat(),
            "resolved_at": (due + timedelta(minutes=5)).isoformat(),
            "strategy_identity": {"fingerprint": "fp-1"},
        })
    return rows


def test_thresholds_are_fixed_and_research_only():
    result = selective_precision_assessment(_rows(), "24h", minimum_samples=5)
    assert tuple(item["minimum_score"] for item in result["subsets"]) == PREDECLARED_THRESHOLDS
    assert result["thresholds_predeclared"] is True
    assert result["non_overlapping_full_horizon_samples_only"] is True
    assert result["research_only"] is True
    assert result["trade_authority"] is False
    assert result["promotion_authority"] is False
    assert result["probability_claim"] is False


def test_higher_selectivity_can_measure_precision_lift_without_authorizing_trade():
    result = selective_precision_assessment(_rows(), "24h", minimum_samples=5)
    baseline = result["baseline"]
    high = next(item for item in result["subsets"] if item["minimum_score"] == 90.0)
    assert baseline["precision"] == 0.75
    assert high["precision"] == 1.0
    assert high["precision_lift_vs_all_resolved"] == 0.25
    assert high["ready"] is True


def test_insufficient_samples_never_claim_precision_lift():
    result = selective_precision_assessment(_rows(8), "24h", minimum_samples=30)
    for subset in result["subsets"]:
        assert subset["ready"] is False
        assert subset["precision_lift_vs_all_resolved"] is None


def test_unreliable_recorded_consensus_is_excluded_from_selective_subset():
    rows = _rows(10)
    rows[0]["market_consensus_reliable"] = False
    result = selective_precision_assessment(rows, "24h", minimum_samples=1)
    high = next(item for item in result["subsets"] if item["minimum_score"] == 90.0)
    assert high["samples"] == 9


def test_dense_overlapping_scan_stream_cannot_manufacture_independent_sample_readiness():
    rows = _rows(96, spacing=timedelta(minutes=15))
    result = selective_precision_assessment(rows, "24h", minimum_samples=30)

    assert result["baseline"]["raw_resolved_rows"] == 96
    assert result["baseline"]["samples"] == 1
    for subset in result["subsets"]:
        assert subset["samples"] <= 1
        assert subset["ready"] is False
        assert subset["precision_lift_vs_all_resolved"] is None


def test_rows_resolved_before_due_are_rejected_as_not_full_horizon_evidence():
    rows = _rows(2)
    rows[0]["resolved_at"] = (datetime.fromisoformat(rows[0]["due_at"]) - timedelta(minutes=1)).isoformat()
    result = selective_precision_assessment(rows, "24h", minimum_samples=1)
    assert result["baseline"]["raw_resolved_rows"] == 2
    assert result["baseline"]["samples"] == 1


def test_missing_due_at_fails_closed_from_independent_confidence_count():
    rows = _rows(2)
    rows[0].pop("due_at")
    result = selective_precision_assessment(rows, "24h", minimum_samples=1)
    assert result["baseline"]["raw_resolved_rows"] == 2
    assert result["baseline"]["samples"] == 1
