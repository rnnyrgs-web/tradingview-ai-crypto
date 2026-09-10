from datetime import datetime, timedelta, timezone

from production_risk_gate import assess_portfolio_risk


def _account():
    return {
        "initial_cash": 100000.0,
        "equity": 100000.0,
        "peak_equity": 100000.0,
        "max_drawdown_pct": 0.0,
    }


def test_recent_four_loss_streak_remains_blocked():
    stats = {
        "consecutive_losses": 4,
        "last_closed_at": (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat(),
    }
    decision = assess_portfolio_risk(_account(), [], stats)
    assert decision.blocked
    assert "repeated_loss_streak" in decision.reasons
    assert decision.metrics["loss_streak_cooldown_remaining_seconds"] > 0


def test_four_loss_streak_recovers_after_24h_cooldown():
    stats = {
        "consecutive_losses": 4,
        "last_closed_at": (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat(),
    }
    decision = assess_portfolio_risk(_account(), [], stats)
    assert "repeated_loss_streak" not in decision.reasons
    assert decision.metrics["loss_streak_cooldown_complete"] is True


def test_missing_loss_chronology_fails_closed():
    decision = assess_portfolio_risk(_account(), [], {"consecutive_losses": 4})
    assert decision.blocked
    assert "repeated_loss_streak" in decision.reasons
    assert decision.metrics["loss_streak_timestamp_valid"] is False
