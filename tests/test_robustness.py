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
