from datetime import datetime, timedelta, timezone

import pytest

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


@pytest.mark.parametrize("nonfinite", [float("nan"), float("inf"), float("-inf")])
def test_bridge_quarantines_nonfinite_imported_priority_with_audit(nonfinite):
    diagnostics = {
        "research_priorities": [
            {
                "dimension": "direction",
                "group": "INVALID",
                "target_horizon": "24h",
                "priority_score": nonfinite,
                "independent_samples": 100,
            },
            {
                "dimension": "direction",
                "group": "LONG",
                "target_horizon": "24h",
                "priority_score": 2.5,
                "independent_samples": 12,
            },
        ]
    }

    enriched, audit = enrich_diagnostics_with_specialists([], diagnostics)

    assert [row["group"] for row in enriched["research_priorities"]] == ["LONG"]
    assert audit["invalid_priority_candidate_count"] == 1
    assert audit["invalid_priority_candidates"] == [
        {
            "source": "diagnostics.research_priorities",
            "source_index": 0,
            "dimension": "direction",
            "group": "INVALID",
            "invalid_fields": ["priority_score"],
            "reason": "nonfinite_numeric_priority",
        }
    ]
