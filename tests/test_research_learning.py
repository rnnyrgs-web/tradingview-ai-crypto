from research_learning import learning_diagnostics


def _rows():
    rows = []
    for i in range(24):
        rows.append({
            "horizon": "24h",
            "market_regime": "TREND" if i < 12 else "CHOP",
            "direction": "LONG" if i % 2 == 0 else "SHORT",
            "score": 85 if i < 12 else 65,
            "strategy_identity": "champion-a" if i < 12 else "challenger-b",
            "directional_return_pct": 1.0 if i < 12 else -0.5,
            "correct": True if i < 12 else False,
        })
    return rows


def test_learning_diagnostics_is_research_only():
    result = learning_diagnostics(_rows(), minimum_samples=6)
    assert result["research_only"] is True
    assert result["trade_authority"] is False
    assert result["promotion_authority"] is False
    assert result["automatic_strategy_mutation"] is False


def test_wrong_groups_become_research_priorities():
    result = learning_diagnostics(_rows(), minimum_samples=6)
    priorities = result["research_priorities"]
    assert priorities
    assert any(p["dimension"] == "market_regime" and p["group"] == "CHOP" for p in priorities)
    for item in priorities:
        assert item["requires_new_validation"] is True
        assert item["trade_authority"] is False


def test_small_groups_do_not_create_priority():
    result = learning_diagnostics(_rows()[:4], minimum_samples=6)
    assert result["research_priorities"] == []


def test_unresolved_rows_are_excluded():
    rows = _rows()
    rows.append({"horizon": "24h", "correct": None, "score": 99})
    result = learning_diagnostics(rows, minimum_samples=6)
    assert result["resolved_samples"] == 24
