from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

from shadow_readiness import assess_shadow_readiness, canary_review_decision


def row(day, ret, correct=None, symbol="BTC-USDT", horizon="24h", family="trend"):
    due = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(days=day)
    return {
        "symbol": symbol,
        "horizon": horizon,
        "due_at": due.isoformat(),
        "resolved_at": (due + timedelta(hours=1)).isoformat(),
        "directional_return_pct": ret,
        "correct": (ret > 0) if correct is None else correct,
        "strategy_identity": {
            "symbol": symbol,
            "horizon": horizon,
            "strategy_family": family,
            "strategy_version": "v-test",
            "implementation_sha256": "abc",
        },
    }


def identity():
    return {
        "symbol": "BTC-USDT",
        "horizon": "24h",
        "strategy_family": "trend",
        "strategy_version": "v-test",
        "implementation_sha256": "abc",
    }


def test_overlapping_forecasts_do_not_inflate_independent_evidence():
    rows = [row(0, 1.0), row(0, 2.0), row(1, 1.0)]
    result = assess_shadow_readiness(rows, target_identity=identity(), horizon="24h")
    assert result["raw_resolved_forecasts"] == 3
    assert result["independent_periods"] == 2
    assert result["eligible_for_tiny_canary_review"] is False


def test_positive_forward_evidence_can_reach_tiny_canary_review_only():
    returns = [1.0, 0.8, -0.2, 1.2, 0.5, 0.7, -0.1, 0.9, 0.6, 0.4]
    rows = [row(i, ret) for i, ret in enumerate(returns)]
    result = assess_shadow_readiness(rows, target_identity=identity(), horizon="24h")
    assert result["independent_periods"] == 10
    assert result["eligible_for_tiny_canary_review"] is True
    assert result["eligible_for_scale_review"] is False
    assert result["trade_authority"] is False


def test_negative_recent_expectancy_blocks_canary_review():
    returns = [1.0, 1.0, 1.0, 1.0, 1.0, -0.2, -0.2, -0.2, -0.2, -0.2]
    rows = [row(i, ret) for i, ret in enumerate(returns)]
    result = assess_shadow_readiness(rows, target_identity=identity(), horizon="24h")
    assert result["eligible_for_tiny_canary_review"] is False
    assert "recent_shadow_expectancy<=0" in result["tiny_canary_reasons"]


def test_canary_decision_never_grants_trade_authority():
    shadow = {
        "eligible_for_tiny_canary_review": True,
        "tiny_canary_reasons": [],
    }
    validation = SimpleNamespace(approved=True)
    result = canary_review_decision(validation, shadow)
    assert result["eligible_for_production_risk_canary_review"] is True
    assert result["trade_authority"] is False
    assert result["canary_execution_enabled"] is False


def test_unpromoted_strategy_is_blocked_even_with_good_shadow_evidence():
    shadow = {
        "eligible_for_tiny_canary_review": True,
        "tiny_canary_reasons": [],
    }
    validation = SimpleNamespace(approved=False)
    result = canary_review_decision(validation, shadow)
    assert result["eligible_for_production_risk_canary_review"] is False
    assert "live_strategy_not_promoted_and_verified" in result["reasons"]
