from selective_precision import PREDECLARED_THRESHOLDS, selective_precision_assessment


def _rows(n=40):
    rows = []
    for i in range(n):
        score = 95 if i < 10 else 85 if i < 20 else 75 if i < 30 else 65
        rows.append({"horizon": "24h", "score": score, "correct": i < 30, "market_consensus_reliable": True})
    return rows


def test_thresholds_are_fixed_and_research_only():
    result = selective_precision_assessment(_rows(), "24h", minimum_samples=5)
    assert tuple(item["minimum_score"] for item in result["subsets"]) == PREDECLARED_THRESHOLDS
    assert result["thresholds_predeclared"] is True
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
