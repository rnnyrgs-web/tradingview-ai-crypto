from research_learning import learning_diagnostics


def _row(**overrides):
    row = {
        "resolved_at": "2026-09-09T00:00:00+00:00",
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


def test_unresolved_rows_are_excluded():
    rows = [_row(), _row(resolved_at=None, correct=True)]
    result = learning_diagnostics(rows, minimum_samples=1)
    assert result["resolved_samples"] == 1
    assert result["baseline_precision"] == 0.0


def test_priorities_are_research_only_and_require_new_validation():
    rows = [_row() for _ in range(12)]
    result = learning_diagnostics(rows)
    assert result["research_only"] is True
    assert result["trade_authority"] is False
    assert result["promotion_authority"] is False
    assert result["automatic_strategy_mutation"] is False
    assert result["research_priorities"]
    top = result["research_priorities"][0]
    assert top["requires_new_validation"] is True
    assert top["trade_authority"] is False
    assert top["promotion_authority"] is False


def test_small_groups_do_not_become_priorities():
    result = learning_diagnostics([_row() for _ in range(5)], minimum_samples=12)
    assert result["research_priorities"] == []


def test_nonfinite_scores_are_bucketed_unknown():
    rows = [_row(score=float("nan")) for _ in range(12)]
    result = learning_diagnostics(rows)
    groups = result["diagnostics"]["score_band"]
    assert groups[0]["group"] == "unknown"
