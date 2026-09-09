from datetime import datetime, timedelta, timezone

from shadow_competition import compare_challenger


def _identity(ch, cost=10.0):
    return {"fingerprint": ch * 64, "backtest_cost_bps": cost}


def _rows(identity, horizon, returns, start=None):
    start = start or datetime(2026, 1, 1, tzinfo=timezone.utc)
    step = timedelta(days=7) if horizon == "7d" else timedelta(days=1)
    out = []
    for i, ret in enumerate(returns):
        due = start + i * step
        out.append({
            "scan_id": f"scan-{i}",
            "horizon": horizon,
            "strategy_identity": identity,
            "correct": ret > 0,
            "directional_return_pct": ret,
            "due_at": due.isoformat(),
            "resolved_at": due.isoformat(),
        })
    return out


def test_strong_challenger_can_earn_review_recommendation():
    champion = _identity("a")
    challenger = _identity("b")
    predictions = _rows(champion, "24h", [1.0] * 24) + _rows(challenger, "24h", [2.0] * 24)
    result = compare_challenger(predictions, champion, challenger, "24h")
    assert result["passed"]
    assert result["eligible_for_strategy_registry_review"]
    assert not result["trade_authority"]
    assert not result["promotion_authority"]


def test_insufficient_matched_periods_fail_closed():
    champion = _identity("a")
    challenger = _identity("b")
    predictions = _rows(champion, "24h", [1.0] * 10) + _rows(challenger, "24h", [2.0] * 10)
    result = compare_challenger(predictions, champion, challenger, "24h")
    assert not result["passed"]
    assert "matched_independent_periods<20" in result["reasons"]


def test_challenger_must_win_after_its_own_costs():
    champion = _identity("a", cost=5.0)
    challenger = _identity("b", cost=50.0)
    predictions = _rows(champion, "24h", [1.0] * 24) + _rows(challenger, "24h", [1.2] * 24)
    result = compare_challenger(predictions, champion, challenger, "24h")
    assert not result["passed"]
    assert "challenger_after_cost_expectancy<=0" in result["reasons"] or "challenger_mean_advantage<=0" in result["reasons"]


def test_unmatched_future_periods_do_not_count():
    champion = _identity("a")
    challenger = _identity("b")
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    predictions = _rows(champion, "24h", [1.0] * 25, start) + _rows(challenger, "24h", [2.0] * 10, start)
    result = compare_challenger(predictions, champion, challenger, "24h")
    assert result["matched_independent_periods"] == 10
    assert not result["passed"]


def test_overlapping_intraday_rows_cannot_inflate_24h_sample_count():
    champion = _identity("a")
    challenger = _identity("b")
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    predictions = []
    for identity, ret in ((champion, 1.0), (challenger, 2.0)):
        for i in range(96):
            due = start + timedelta(minutes=15 * i)
            predictions.append({
                "scan_id": f"{identity['fingerprint'][0]}-{i}",
                "horizon": "24h",
                "strategy_identity": identity,
                "correct": True,
                "directional_return_pct": ret,
                "due_at": due.isoformat(),
                "resolved_at": due.isoformat(),
            })
    result = compare_challenger(predictions, champion, challenger, "24h")
    assert result["matched_independent_periods"] <= 1
    assert not result["passed"]


def test_midnight_boundary_cannot_create_fake_matched_independent_periods():
    champion = _identity("a")
    challenger = _identity("b")
    due_times = [
        datetime(2026, 1, 2, 23, 59, tzinfo=timezone.utc),
        datetime(2026, 1, 3, 0, 1, tzinfo=timezone.utc),
    ]
    predictions = []
    for identity, ret in ((champion, 1.0), (challenger, 2.0)):
        for i, due in enumerate(due_times):
            predictions.append({
                "scan_id": f"{identity['fingerprint'][0]}-{i}",
                "horizon": "24h",
                "strategy_identity": identity,
                "correct": True,
                "directional_return_pct": ret,
                "due_at": due.isoformat(),
                "resolved_at": due.isoformat(),
            })
    result = compare_challenger(predictions, champion, challenger, "24h")
    assert result["matched_independent_periods"] == 1
    assert result["independence_policy"] == "matched_exact_due_at_full_horizon_non_overlapping_windows_only"
    assert not result["passed"]


def test_different_due_endpoints_do_not_count_as_matched_periods():
    champion = _identity("a")
    challenger = _identity("b")
    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    champion_rows = _rows(champion, "24h", [1.0] * 20, start)
    challenger_rows = _rows(challenger, "24h", [2.0] * 20, start + timedelta(minutes=5))
    result = compare_challenger(champion_rows + challenger_rows, champion, challenger, "24h")
    assert result["matched_independent_periods"] == 0
    assert not result["passed"]


def test_same_or_invalid_fingerprint_fails_closed():
    identity = _identity("a")
    assert not compare_challenger([], identity, identity, "24h")["passed"]
    assert not compare_challenger([], {"fingerprint":"bad"}, _identity("b"), "24h")["passed"]


def test_weekly_horizon_requires_twelve_matched_periods():
    champion = _identity("a")
    challenger = _identity("b")
    predictions = _rows(champion, "7d", [1.0] * 12) + _rows(challenger, "7d", [2.0] * 12)
    result = compare_challenger(predictions, champion, challenger, "7d")
    assert result["matched_independent_periods"] == 12
    assert result["passed"]
