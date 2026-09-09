from datetime import datetime, timedelta, timezone

from research_meta_wait import build_meta_wait_diagnostics


def _rows(n=12, *, return_pct=-0.5, correct=False, overlap=False):
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    rows = []
    for i in range(n):
        if overlap:
            origin = start + timedelta(minutes=15 * i)
        else:
            origin = start + timedelta(days=i)
        due = origin + timedelta(hours=24)
        rows.append({
            "due_at": due.isoformat(),
            "resolved_at": (due + timedelta(minutes=1)).isoformat(),
            "correct": correct,
            "horizon": "24h",
            "market_regime": "TREND",
            "direction": "LONG",
            "score": 85,
            "strategy_identity": "s1",
            "directional_return_pct": return_pct,
        })
    return rows


def _find(report, dimension, group):
    return next(row for row in report["groups"] if row["dimension"] == dimension and row["group"] == group)


def test_meta_wait_uses_only_non_overlapping_full_horizon_rows():
    report = build_meta_wait_diagnostics(_rows(30, overlap=True), minimum_samples=12)
    group = _find(report, "direction", "LONG")
    assert report["independent_samples"] == 1
    assert group["samples"] == 1
    assert group["ready_for_research"] is False
    assert report["research_priorities"] == []


def test_fixed_cost_can_turn_small_raw_gain_into_economic_loss():
    report = build_meta_wait_diagnostics(_rows(return_pct=0.05, correct=True), cost_pct=0.12)
    group = _find(report, "direction", "LONG")
    assert group["directional_precision"] == 1.0
    assert group["after_cost_expectancy_pct"] == -0.07
    assert group["after_cost_win_rate"] == 0.0
    assert group["economic_harm_pct"] == 0.07
    assert group["ready_for_research"] is True


def test_missing_return_data_fails_closed_for_economic_research():
    rows = _rows()
    rows[0]["directional_return_pct"] = None
    report = build_meta_wait_diagnostics(rows)
    group = _find(report, "direction", "LONG")
    assert group["economic_evidence_complete"] is False
    assert group["ready_for_research"] is False


def test_meta_wait_has_no_production_authority():
    report = build_meta_wait_diagnostics(_rows())
    assert report["research_only"] is True
    assert report["trade_authority"] is False
    assert report["promotion_authority"] is False
    assert report["strategy_mutation_authority"] is False
    assert report["automatic_execution_authority"] is False
