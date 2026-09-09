from datetime import datetime, timedelta, timezone

from research_meta_wait import build_meta_wait_diagnostics


def _rows(n=12, *, return_pct=-0.5, correct=False, overlap=False, horizon="24h"):
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    rows = []
    horizon_delta = timedelta(hours=24) if horizon == "24h" else timedelta(days=7)
    step = timedelta(days=1) if horizon == "24h" else timedelta(days=7)
    for i in range(n):
        if overlap:
            origin = start + timedelta(minutes=15 * i)
        else:
            origin = start + step * i
        due = origin + horizon_delta
        rows.append({
            "due_at": due.isoformat(),
            "resolved_at": (due + timedelta(minutes=1)).isoformat(),
            "correct": correct,
            "horizon": horizon,
            "market_regime": "TREND",
            "direction": "LONG",
            "score": 85,
            "strategy_identity": "s1",
            "directional_return_pct": return_pct,
        })
    return rows


def _find(report, dimension, group, horizon="24h"):
    return next(row for row in report["groups"] if row["horizon"] == horizon and row["dimension"] == dimension and row["group"] == group)


def test_meta_wait_uses_only_non_overlapping_full_horizon_rows():
    report = build_meta_wait_diagnostics(_rows(30, overlap=True), minimum_samples=12)
    group = _find(report, "direction", "LONG")
    assert report["independent_samples"] == 1
    assert report["independent_samples_by_horizon"]["24h"] == 1
    assert group["samples"] == 1
    assert group["ready_for_research"] is False
    assert report["research_priorities"] == []


def test_fixed_cost_can_turn_small_raw_gain_into_economic_loss():
    report = build_meta_wait_diagnostics(_rows(return_pct=0.05, correct=True), cost_pct=0.12)
    group = _find(report, "direction", "LONG")
    assert group["directional_precision"] == 1.0
    assert group["after_cost_expectancy_pct"] == -0.07
    assert group["cost_stress_expectancy_pct"]["3x"] == -0.31
    assert group["after_cost_win_rate"] == 0.0
    assert group["economic_harm_pct"] == 0.07
    assert group["ready_for_research"] is True


def test_meta_wait_never_pools_24h_and_7d_economics():
    rows = _rows(return_pct=-0.5, correct=False, horizon="24h") + _rows(return_pct=1.0, correct=True, horizon="7d")
    report = build_meta_wait_diagnostics(rows)
    h24 = _find(report, "direction", "LONG", horizon="24h")
    h7 = _find(report, "direction", "LONG", horizon="7d")
    assert h24["after_cost_expectancy_pct"] == -0.62
    assert h7["after_cost_expectancy_pct"] == 0.88
    assert h24["ready_for_research"] is True
    assert h7["ready_for_research"] is True
    assert report["sample_policy"] == "non_overlapping_full_horizon_resolved_rows_separate_by_horizon"


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
