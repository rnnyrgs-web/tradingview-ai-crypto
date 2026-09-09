import selective_precision_observability as obs


def test_snapshot_uses_resolved_rows_and_remains_research_only(monkeypatch):
    rows = [
        {"horizon": "24h", "score": 95, "correct": True, "market_consensus_reliable": True},
        {"horizon": "24h", "score": 65, "correct": False, "market_consensus_reliable": True},
        {"horizon": "7d", "score": 85, "correct": True, "market_consensus_reliable": True},
    ]
    monkeypatch.setattr(obs, "fetch_resolved_predictions", lambda limit=5000: rows)

    result = obs.resolved_selective_precision_snapshot()

    assert result["ok"] is True
    assert result["resolved_rows_observed"] == 3
    assert result["source"] == "prediction_ledger_resolved_only"
    assert result["research_only"] is True
    assert result["trade_authority"] is False
    assert result["promotion_authority"] is False
    assert result["threshold_selection_authority"] is False
    assert {item["horizon"] for item in result["horizons"]} == {"24h", "7d"}


def test_snapshot_does_not_mutate_or_select_thresholds(monkeypatch):
    rows = [{"horizon": "24h", "score": 90, "correct": True}]
    original = [dict(row) for row in rows]
    monkeypatch.setattr(obs, "fetch_resolved_predictions", lambda limit=5000: rows)

    result = obs.resolved_selective_precision_snapshot(limit=100)

    assert rows == original
    assert result["threshold_selection_authority"] is False
    assert all(item["trade_authority"] is False for item in result["horizons"])
