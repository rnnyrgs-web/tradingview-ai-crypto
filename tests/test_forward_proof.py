from datetime import datetime, timedelta, timezone

from forward_proof import assess_forward_proof


FP = "a" * 64
OTHER = "b" * 64


def _rows(count, horizon="24h", return_pct=2.0, spacing_hours=24, fingerprint=FP):
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    span = timedelta(hours=24) if horizon == "24h" else timedelta(days=7)
    rows = []
    for i in range(count):
        created = start + timedelta(hours=spacing_hours * i)
        rows.append({
            "created_at": created.isoformat(),
            "due_at": (created + span).isoformat(),
            "resolved_at": (created + span + timedelta(minutes=1)).isoformat(),
            "horizon": horizon,
            "directional_return_pct": return_pct,
            "correct": return_pct > 0,
            "strategy_identity": {"fingerprint": fingerprint},
        })
    return rows


def test_forward_proof_passes_only_with_enough_independent_after_cost_evidence():
    result = assess_forward_proof({"fingerprint": FP}, "24h", _rows(20))
    assert result["passed"] is True
    assert result["independent_samples"] == 20
    assert result["after_cost_expectancy_pct"] > 0
    assert result["after_cost_precision_95pct_lower"] >= 0.50


def test_overlapping_forecasts_do_not_fake_sample_size():
    result = assess_forward_proof({"fingerprint": FP}, "24h", _rows(96, spacing_hours=1))
    assert result["passed"] is False
    assert result["independent_samples"] < 20
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
    assert result["passed"] is True
    assert result["minimum_independent_samples"] == 12
