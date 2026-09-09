from research_experiment_factory_runner import build_factory_report


def test_factory_runner_builds_research_only_queue(monkeypatch, tmp_path):
    monkeypatch.setenv("RESEARCH_LEARNING_STATE_PATH", str(tmp_path / "learning.json"))
    rows = []
    for i in range(30):
        rows.append(
            {
                "resolved_at": "2026-09-09T00:00:00+00:00",
                "correct": i < 18,
                "horizon": "24h",
                "market_regime": "TREND",
                "direction": "LONG",
                "score": 85,
                "strategy_identity": "s1",
                "directional_return_pct": 1.0 if i < 18 else -1.0,
            }
        )
    report = build_factory_report(rows)
    assert report["research_only"] is True
    assert report["trade_authority"] is False
    assert report["promotion_authority"] is False
    assert report["strategy_mutation_authority"] is False
    assert report["automatic_execution_authority"] is False
    assert report["resolved_samples"] == 30
    assert report["experiment_queue"]["experiment_count"] >= 1
