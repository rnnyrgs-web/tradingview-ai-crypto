from math import inf, nan

from robustness import evaluate_robustness, monte_carlo_bootstrap


def test_monte_carlo_is_deterministic():
    returns = [0.4, 0.2, -0.1, 0.3] * 5
    assert monte_carlo_bootstrap(returns, "same") == monte_carlo_bootstrap(returns, "same")


def test_robustness_fails_with_insufficient_evidence():
    result = evaluate_robustness([0.2] * 8, {"low": [0.2] * 8}, {"TREND": [0.2] * 8}, "x")
    assert result["passed"] is False
    assert result["monte_carlo"]["reason"] == "oos_trades<12"


def test_robustness_requires_parameter_and_multiple_regime_stability():
    base = [0.3] * 20
    stable = evaluate_robustness(
        base,
        {"threshold_90pct": [0.2] * 8, "threshold_110pct": [0.1] * 8},
        {"TREND": [0.2] * 6, "RANGE": [0.1] * 6},
        "stable",
    )
    assert stable["passed"] is True
    unstable = evaluate_robustness(
        base,
        {"threshold_90pct": [-0.2] * 8, "threshold_110pct": [0.1] * 8},
        {"TREND": [0.2] * 6, "RANGE": [-0.1] * 6},
        "unstable",
    )
    assert unstable["passed"] is False


def test_nonfinite_base_returns_fail_closed_before_bootstrap():
    for bad in (nan, inf, -inf):
        result = monte_carlo_bootstrap([0.2] * 12 + [bad], "bad")
        assert result["passed"] is False
        assert result["reason"] == "invalid_nonfinite_oos_returns"
        assert result["simulations"] == 0


def test_nonfinite_parameter_variant_cannot_pass_by_numeric_accident():
    result = evaluate_robustness(
        [0.3] * 20,
        {"threshold_90pct": [0.2] * 8, "threshold_110pct": [inf] * 8},
        {"TREND": [0.2] * 6, "RANGE": [0.1] * 6},
        "nonfinite-parameter",
    )
    assert result["passed"] is False
    assert result["reason"] == "malformed_or_nonfinite_robustness_input"
    assert "parameter:threshold_110pct" in result["invalid_inputs"]


def test_nonfinite_regime_data_cannot_be_ignored():
    result = evaluate_robustness(
        [0.3] * 20,
        {"threshold_90pct": [0.2] * 8, "threshold_110pct": [0.1] * 8},
        {"TREND": [0.2] * 6, "RANGE": [0.1] * 5 + [nan]},
        "nonfinite-regime",
    )
    assert result["passed"] is False
    assert "regime:RANGE" in result["invalid_inputs"]


def test_missing_parameter_or_regime_evidence_fails_closed():
    assert evaluate_robustness([0.3] * 20, {}, {"TREND": [0.2] * 6}, "missing-param")["passed"] is False
    assert evaluate_robustness([0.3] * 20, {"p": [0.2] * 8}, {}, "missing-regime")["passed"] is False


def test_catastrophic_tail_risk_fails_monte_carlo_even_with_many_small_wins():
    returns = [1.0] * 19 + [-35.0]
    result = monte_carlo_bootstrap(returns, "tail-risk")
    assert result["passed"] is False
    assert (
        result["p05_sum_returns_pct"] <= 0
        or result["p95_max_drawdown_pct"] > 25
        or result["probability_positive"] < 0.80
    )


def test_parameter_collapse_blocks_strategy_despite_strong_base_oos():
    result = evaluate_robustness(
        [0.5] * 30,
        {"threshold_90pct": [0.25] * 8, "threshold_110pct": [-0.01] * 8},
        {"TREND_UP": [0.2] * 6, "RANGE": [0.1] * 6},
        "fragile-parameter",
    )
    assert result["passed"] is False
    assert result["parameter_stability"]["passed"] is False


def test_single_regime_success_cannot_substitute_for_multi_regime_robustness():
    result = evaluate_robustness(
        [0.5] * 30,
        {"threshold_90pct": [0.25] * 8, "threshold_110pct": [0.2] * 8},
        {"TREND_UP": [0.3] * 10, "RANGE": [0.1] * 2, "HIGH_VOL": [0.1] * 2},
        "single-regime",
    )
    assert result["passed"] is False
    assert result["regime_stability"]["passed"] is False
