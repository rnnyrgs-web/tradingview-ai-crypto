from datetime import datetime, timedelta, timezone

from research_learning import learning_diagnostics
from research_quant_science_factory import build_quant_science_queue
from research_specialist_bridge import enrich_diagnostics_with_specialists


def _rows(count=16):
    start = datetime(2026, 7, 1, tzinfo=timezone.utc)
    rows = []
    for index in range(count):
        origin = start + timedelta(days=index * 2)
        due = origin + timedelta(hours=24)
        rows.append({
            "symbol": "BTC-USDT",
            "horizon": "24h",
            "direction": "BUY",
            "market_regime": "BULL",
            "score": 85,
            "strategy_identity": "fingerprint-a",
            "due_at": due.isoformat(),
            "resolved_at": (due + timedelta(minutes=1)).isoformat(),
            "correct": index % 4 == 0,
            "directional_return_pct": -1.0 if index % 4 else 1.0,
        })
    return rows


def test_specialists_feed_only_scope_safe_hypotheses_into_quant_factory():
    rows = _rows()
    diagnostics = learning_diagnostics(rows)
    enriched, audit = enrich_diagnostics_with_specialists(rows, diagnostics)

    assert audit["logical_specialists_seen"] >= 32
    assert audit["accepted_candidate_count"] > 0
    assert audit["deferred_candidate_count"] > 0
    assert audit["scope_loss_allowed"] is False
    assert any(
        row["specialist"] == "btc-diagnostics"
        and row["reason"] == "specialist_scope_requires_dedicated_evaluator"
        for row in audit["deferred_candidates"]
    )

    queue = build_quant_science_queue(enriched, {"lessons": []})
    assert queue["research_only"] is True
    assert queue["trade_authority"] is False
    assert queue["promotion_authority"] is False
    assert queue["experiment_count"] > 0
    assert all(item["science_design"]["parameter_mining_allowed"] is False for item in queue["experiments"])


def test_bridge_does_not_create_evidence_when_ledger_is_empty():
    diagnostics = learning_diagnostics([])
    enriched, audit = enrich_diagnostics_with_specialists([], diagnostics)

    assert enriched["research_priorities"] == []
    assert audit["accepted_candidate_count"] == 0
    assert audit["deferred_candidate_count"] == 0
    assert audit["trade_authority"] is False
