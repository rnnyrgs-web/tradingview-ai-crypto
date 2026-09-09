from datetime import datetime, timedelta, timezone

from research_experiment_factory_runner import build_factory_report


def test_factory_runner_builds_research_only_queue(monkeypatch, tmp_path):
    monkeypatch.setenv("RESEARCH_LEARNING_STATE_PATH", str(tmp_path / "learning.json"))
    rows = []
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    for i in range(30):
        forecast_at = start + timedelta(days=i)
        due_at = forecast_at + timedelta(hours=24)
        rows.append(
            {
                "forecast_at": forecast_at.isoformat(),
                "due_at": due_at.isoformat(),
                "resolved_at": (due_at + timedelta(minutes=1)).isoformat(),
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
