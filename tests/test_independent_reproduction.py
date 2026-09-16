import sys

from independent_reproduction import compare_reproduction_metrics, reproduce_vectorized


def test_absent_vectorbt_fails_closed(monkeypatch):
    monkeypatch.setitem(sys.modules, "vectorbt", None)
    result = reproduce_vectorized(
        {"canonical_metrics": {"net_expectancy_pct": 0.2, "profit_factor": 1.3}},
        [{"close": 100.0}, {"close": 101.0}],
    )
    assert result["status"] == "INDEPENDENT_REPRODUCTION_UNAVAILABLE"
    assert result["pass"] is False


def test_matching_independent_economics_pass():
    result = compare_reproduction_metrics(
        {"net_expectancy_pct": 0.20, "profit_factor": 1.30},
        {"net_expectancy_pct": 0.19, "profit_factor": 1.28},
        expectancy_tolerance_pct=0.05,
        profit_factor_tolerance=0.10,
    )
    assert result["status"] == "PASS"
    assert result["pass"] is True


def test_material_economic_disagreement_blocks_validation():
    result = compare_reproduction_metrics(
        {"net_expectancy_pct": 0.20, "profit_factor": 1.30},
        {"net_expectancy_pct": -0.10, "profit_factor": 0.80},
        expectancy_tolerance_pct=0.05,
        profit_factor_tolerance=0.10,
    )
    assert result["status"] == "DISAGREE"
    assert result["pass"] is False
