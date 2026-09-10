from datetime import datetime, timezone

import paper_trading as p


def _trade(direction="LONG", horizon="7d", symbol="MINA-USDT"):
    return {"id": 1, "symbol": symbol, "horizon": horizon, "direction": direction}


def _signal(direction="SHORT", evidence=85.0, rank=2, generated_at="2026-09-10T01:30:00Z", symbol="MINA-USDT"):
    return {
        "symbol": symbol,
        "horizon": "7d",
        "direction": direction,
        "evidence_score": evidence,
        "rank": rank,
        "generated_at": generated_at,
    }


def test_strong_fresh_bearish_7d_signal_triggers_long_exit_eligibility():
    now = datetime(2026, 9, 10, 1, 40, tzinfo=timezone.utc)
    row = p._strong_opposite_7d_signal(_trade(), [_signal()], now=now)
    assert row is not None
    assert row["direction"] == "SHORT"


def test_same_direction_does_not_trigger_reversal_sell():
    now = datetime(2026, 9, 10, 1, 40, tzinfo=timezone.utc)
    assert p._strong_opposite_7d_signal(_trade(), [_signal(direction="LONG")], now=now) is None


def test_weak_or_low_rank_bearish_signal_does_not_trigger_sell():
    now = datetime(2026, 9, 10, 1, 40, tzinfo=timezone.utc)
    assert p._strong_opposite_7d_signal(_trade(), [_signal(evidence=79.99)], now=now) is None
    assert p._strong_opposite_7d_signal(_trade(), [_signal(rank=6)], now=now) is None


def test_stale_signal_does_not_trigger_sell():
    now = datetime(2026, 9, 10, 2, 5, tzinfo=timezone.utc)
    assert p._strong_opposite_7d_signal(_trade(), [_signal()], now=now) is None


def test_reversal_policy_does_not_close_short_or_24h_trade():
    now = datetime(2026, 9, 10, 1, 40, tzinfo=timezone.utc)
    assert p._strong_opposite_7d_signal(_trade(direction="SHORT"), [_signal()], now=now) is None
    assert p._strong_opposite_7d_signal(_trade(horizon="24h"), [_signal()], now=now) is None
