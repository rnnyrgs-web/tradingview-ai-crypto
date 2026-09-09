import research_learning_state
from research_learning_runner import build_learning_report


def test_runner_report_combines_learning_and_selective_precision(tmp_path, monkeypatch):
    monkeypatch.setattr(research_learning_state, "DEFAULT_PATH", tmp_path / "learning.json")
    rows = []
    for i in range(30):
        rows.append({
            "resolved_at": "2026-09-09T00:00:00+00:00",
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
    assert report["selective_precision"]["ok"] is True
    assert report["research_memory"]["lesson_count"] == 1
