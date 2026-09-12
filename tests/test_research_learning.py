from datetime import datetime, timedelta, timezone

from research_learning import learning_diagnostics


def _row(**overrides):
    due_at = overrides.pop("due_at", "2026-09-10T00:00:00+00:00")
    row = {
        "due_at": due_at,
        "resolved_at": "2026-09-10T00:01:00+00:00",
        "correct": False,
        "horizon": "24h",
        "market_regime": "TREND",
        "direction": "LONG",
        "score": 85,
        "strategy_identity": "s1",
        "directional_return_pct": -1.0,
    }
    row.update(overrides)
    return row


def _independent_rows(n):
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    rows = []
    for i in range(n):
        due_at = start + timedelta(days=i + 1)
        rows.append(_row(due_at=due_at.isoformat(), resolved_at=(due_at + timedelta(minutes=1)).isoformat()))
    return rows


def test_unresolved_rows_are_excluded():
    rows = [_row(), _row(resolved_at=None, correct=True)]
    result = learning_diagnostics(rows, minimum_samples=1)
    assert result["resolved_samples"] == 1
    assert result["baseline_precision"] == 0.0


def test_production_due_at_reconstructs_independent_origin_without_forecast_at():
    rows = _independent_rows(12)
    assert all("forecast_at" not in row for row in rows)
    result = learning_diagnostics(rows)
    direction = result["diagnostics"]["direction"][0]
    assert direction["independent_samples"] == 12
    assert direction["ready_for_diagnostic"] is True
    assert result["sample_sufficiency_basis"] == "non_overlapping_full_horizon_windows_reconstructed_from_due_at"


def test_overlapping_rows_do_not_create_false_sample_sufficiency():
    rows = []
    origin = datetime(2026, 9, 9, tzinfo=timezone.utc)
    for i in range(30):
        due_at = origin + timedelta(minutes=15 * i) + timedelta(hours=24)
        rows.append(_row(due_at=due_at.isoformat(), resolved_at=(due_at + timedelta(minutes=1)).isoformat()))
    result = learning_diagnostics(rows, minimum_samples=12)
    direction = result["diagnostics"]["direction"][0]
    assert direction["samples"] == 30
    assert direction["independent_samples"] == 1
    assert direction["ready_for_diagnostic"] is False
    assert result["research_priorities"] == []


def test_priorities_require_independent_windows_and_new_validation():
    result = learning_diagnostics(_independent_rows(12))
    assert result["research_only"] is True
    assert result["trade_authority"] is False
    assert result["promotion_authority"] is False
    assert result["automatic_strategy_mutation"] is False
    assert result["research_priorities"]
    top = result["research_priorities"][0]
    assert top["independent_samples"] == 12
    assert top["requires_new_validation"] is True
    assert top["trade_authority"] is False
    assert top["promotion_authority"] is False


def test_profitability_harm_ranks_before_wrong_signal_rate():
    start = datetime(2026, 8, 1, tzinfo=timezone.utc)
    rows = []
    for i in range(12):
        due_at = start + timedelta(days=i + 1)
        common = {"due_at": due_at.isoformat(), "resolved_at": (due_at + timedelta(minutes=1)).isoformat()}
        rows.append(_row(
            **common,
            strategy_identity="profitable_low_accuracy",
            correct=i < 3,
            after_cost_return_pct=1.0,
        ))
        rows.append(_row(
            **common,
            strategy_identity="losing_high_accuracy",
            correct=i < 10,
            after_cost_return_pct=-0.2,
        ))
    result = learning_diagnostics(rows, minimum_samples=12)
    top = result["research_priorities"][0]
    assert top["dimension"] == "strategy_identity"
    assert top["group"] == "losing_high_accuracy"
    assert top["average_after_cost_return_pct"] == -0.2
    assert top["economic_harm_score_pct"] > 0


def test_small_independent_groups_do_not_become_priorities():
    result = learning_diagnostics(_independent_rows(5), minimum_samples=12)
    assert result["research_priorities"] == []


def test_missing_bad_or_premature_chronology_fails_closed_for_independence():
    rows = [
        _row(due_at=None),
        _row(due_at="bad-time"),
        _row(due_at="2026-09-10T00:00:00+00:00", resolved_at="2026-09-09T23:59:00+00:00"),
        _row(horizon="unknown"),
    ]
    result = learning_diagnostics(rows, minimum_samples=1)
    direction = result["diagnostics"]["direction"][0]
    assert direction["samples"] == 4
    assert direction["independent_samples"] == 0
    assert direction["ready_for_diagnostic"] is False
    assert result["research_priorities"] == []


def test_nonfinite_scores_are_bucketed_unknown():
    rows = _independent_rows(12)
    for row in rows:
        row["score"] = float("nan")
    result = learning_diagnostics(rows)
    groups = result["diagnostics"]["score_band"]
    assert groups[0]["group"] == "unknown"
