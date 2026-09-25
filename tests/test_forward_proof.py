from datetime import datetime, timedelta, timezone

import pytest

import forward_proof
from forward_proof import assess_forward_proof


FP = "a" * 64
OTHER = "b" * 64


def _rows(count, horizon="24h", return_pct=2.0, spacing_hours=24, fingerprint=FP):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    span = timedelta(hours=24) if horizon == "24h" else timedelta(days=7)
    rows = []
    for i in range(count):
        origin = start + timedelta(hours=spacing_hours * i)
        due = origin + span
        rows.append({
            "due_at": due.isoformat(),
            "resolved_at": (due + timedelta(minutes=1)).isoformat(),
            "horizon": horizon,
            "directional_return_pct": return_pct,
            "correct": return_pct > 0,
            "strategy_identity": {"fingerprint": fingerprint},
        })
    return rows


def test_forward_proof_preserves_production_ledger_diagnostics_without_cost_authority():
    rows = _rows(20)
    assert all("created_at" not in row for row in rows)
    result = assess_forward_proof({"fingerprint": FP}, "24h", rows)
    assert result["passed"] is False
    assert result["reason"] == "insufficient_authenticated_execution_cost_evidence"
    assert result["independent_samples"] == 20
    assert result["raw_matching_rows"] == 20
    assert result["policy"]["chronology_source"] == "due_at_minus_horizon"
    assert result["after_cost_expectancy_pct"] > 0
    assert result["after_cost_precision_95pct_lower"] >= 0.50


def test_overlapping_forecasts_do_not_fake_sample_size():
    result = assess_forward_proof({"fingerprint": FP}, "24h", _rows(96, spacing_hours=1))
    assert result["passed"] is False
    assert result["raw_matching_rows"] == 96
    assert result["independent_samples"] < 20
    assert result["reason"] == "insufficient_independent_forward_samples"


def test_missing_due_at_fails_closed_even_if_created_at_is_present():
    rows = _rows(20)
    for i, row in enumerate(rows):
        row.pop("due_at")
        row["created_at"] = (datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=i)).isoformat()
    result = assess_forward_proof({"fingerprint": FP}, "24h", rows)
    assert result["passed"] is False
    assert result["independent_samples"] == 0
    assert result["reason"] == "insufficient_independent_forward_samples"


def test_forward_proof_requires_exact_strategy_fingerprint():
    rows = _rows(20, fingerprint=OTHER)
    result = assess_forward_proof({"fingerprint": FP}, "24h", rows)
    assert result["passed"] is False
    assert result["independent_samples"] == 0


def test_conservative_costs_can_turn_apparent_edge_into_rejection():
    result = assess_forward_proof({"fingerprint": FP}, "24h", _rows(20, return_pct=0.20))
    assert result["passed"] is False
    assert result["reason"] == "non_positive_after_cost_forward_expectancy"


def test_seven_day_gate_uses_nonoverlapping_weekly_samples():
    result = assess_forward_proof({"fingerprint": FP}, "7d", _rows(12, horizon="7d", spacing_hours=24 * 7))
    assert result["passed"] is False
    assert result["reason"] == "insufficient_authenticated_execution_cost_evidence"
    assert result["minimum_independent_samples"] == 12


@pytest.mark.parametrize("execution_claim", [
    {},
    {"venue": "generic", "product": "spot", "verified": True},
    {
        "venue": "Kraken", "product": "spot", "notional_usd": 10000,
        "round_trip_cost_bps": 160, "execution_cost_verified": True,
        "execution_cost_evidence": {"verified": True, "status": "AUTHENTICATED"},
    },
])
def test_proxy_cost_false_proof_stays_blocked_despite_execution_labels(monkeypatch, execution_claim):
    # Frozen Work-audit witness: twenty daily +0.50% gross forecasts.
    monkeypatch.setattr(forward_proof, "BACKTEST_COST_BPS", 12.0)
    rows = _rows(20, return_pct=0.50)
    for row in rows:
        row.update(execution_claim)
        row["strategy_identity"].update(execution_claim)
    result = assess_forward_proof({"fingerprint": FP, **execution_claim}, "24h", rows)
    assert result["independent_samples"] == 20
    assert result["modeled_round_trip_cost_bps"] == 36.0
    assert result["after_cost_expectancy_pct"] == pytest.approx(0.14)
    assert result["after_cost_successes"] == 20
    assert result["after_cost_precision_95pct_lower"] >= 0.50
    assert result["max_forward_drawdown_pct"] == 0.0
    assert result["deterioration"]["deteriorating"] is False
    assert result["passed"] is False
    assert result["status"] == "FORWARD_PROOF_BLOCKED"
    assert result["reason"] == "insufficient_authenticated_execution_cost_evidence"
    assert result["execution_cost_evidence"] == "PROXY_ONLY"
    assert result["proxy_diagnostics_passed"] is True
