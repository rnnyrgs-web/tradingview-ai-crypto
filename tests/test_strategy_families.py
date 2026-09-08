import strategy_families as sf
from strategy_families import STRATEGY_FAMILIES, _quality_gate, _skipped_robustness


def metrics(trades, avg, pf, dd=5.0):
    return {
        "trades": trades,
        "win_rate_pct": 50.0,
        "avg_trade_pct": avg,
        "sum_net_returns_pct": avg * trades,
        "profit_factor": pf,
        "max_drawdown_pct": dd,
    }


def test_expected_strategy_families_present():
    assert set(STRATEGY_FAMILIES) == {
        "trend",
        "breakout",
        "momentum",
        "mean_reversion",
        "volatility_expansion",
        "relative_strength",
    }


def test_quality_gate_passes_robust_oos_candidate():
    gate = _quality_gate(
        metrics(30, 0.10, 1.30),
        metrics(12, 0.08, 1.20),
        metrics(12, 0.09, 1.25),
    )
    assert gate["passed"] is True
    assert gate["eligible_for_live_ensemble"] is True
    assert gate["reasons"] == []


def test_quality_gate_rejects_negative_holdout():
    gate = _quality_gate(
        metrics(30, 0.10, 1.30),
        metrics(12, 0.08, 1.20),
        metrics(12, -0.03, 0.90),
    )
    assert gate["passed"] is False
    assert gate["eligible_for_live_ensemble"] is False
    assert "holdout_expectancy<=0" in gate["reasons"]
    assert "holdout_pf<1.10" in gate["reasons"]


def test_skipped_robustness_is_explicitly_failed():
    gate = {"passed": False, "reasons": ["holdout_expectancy<=0"]}
    result = _skipped_robustness(gate)
    assert result["passed"] is False
    assert result["status"] == "SKIPPED_QUALITY_GATE_FAILED"
    assert result["bootstrap_runs"] == 0
    assert result["gate_reasons"] == ["holdout_expectancy<=0"]


def test_registry_does_not_run_expensive_robustness_after_quality_failure(monkeypatch):
    history = [{"ts": i, "close": 100.0} for i in range(1000)]
    monkeypatch.setattr(sf, "STRATEGY_FAMILIES", ("trend",))
    monkeypatch.setattr(sf, "get_history", lambda *args, **kwargs: history)
    monkeypatch.setattr(sf, "_simulate", lambda *args, **kwargs: [])

    def should_not_run(*args, **kwargs):
        raise AssertionError("expensive robustness should be skipped for failed quality gate")

    monkeypatch.setattr(sf, "evaluate_robustness", should_not_run)
    result = sf.evaluate_strategy_registry("BTC-USDT", bar="15m", bars=1000)
    item = result["registry"][0]
    assert item["status"] == "RESEARCH_ONLY"
    assert item["eligible_for_promotion_review"] is False
    assert item["robustness"]["status"] == "SKIPPED_QUALITY_GATE_FAILED"
