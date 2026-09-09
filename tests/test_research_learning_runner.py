from datetime import datetime, timedelta, timezone

import research_learning_state
from research_learning_runner import build_learning_report


def test_runner_report_combines_learning_selective_precision_meta_wait_and_router(tmp_path, monkeypatch):
    monkeypatch.setattr(research_learning_state, "DEFAULT_PATH", tmp_path / "learning.json")
    rows = []
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    for i in range(30):
        forecast_at = start + timedelta(days=i)
        due_at = forecast_at + timedelta(hours=24)
        rows.append({
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
            "market_consensus_reliable": True,
        })
    report = build_learning_report(rows)
    assert report["research_only"] is True
    assert report["trade_authority"] is False
    assert report["promotion_authority"] is False
    assert report["automatic_strategy_mutation"] is False
    assert report["diagnostics"]["resolved_samples"] == 30
    assert report["diagnostics"]["diagnostics"]["direction"][0]["independent_samples"] == 30
    assert report["selective_precision"]["ok"] is True
    assert report["meta_wait_economic_diagnostics"]["ok"] is True
    assert report["meta_wait_economic_diagnostics"]["trade_authority"] is False
    assert report["meta_wait_economic_diagnostics"]["independent_samples"] == 30
    assert report["regime_strategy_router"]["ok"] is True
    assert report["regime_strategy_router"]["untouched_oos_outcomes_scored"] is False
    assert report["regime_strategy_router"]["trade_authority"] is False
    assert report["research_memory"]["lesson_count"] == 1
