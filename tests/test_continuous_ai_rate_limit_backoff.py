import continuous_ai_agent as agent


def test_rate_limit_backoff_grows_and_is_bounded():
    first = agent.retry_delay_seconds("RateLimitError", 1)
    second = agent.retry_delay_seconds("RateLimitError", 2)
    later = agent.retry_delay_seconds("RateLimitError", 20)

    assert first >= max(agent.CONTINUOUS_AI_INTERVAL_SECONDS * 2, 600)
    assert second >= first
    assert later == agent.MAX_RATE_LIMIT_BACKOFF_SECONDS
    assert later <= 7200


def test_non_rate_limit_failure_keeps_normal_cadence():
    assert agent.retry_delay_seconds("HTTPStatusError", 9) == agent.CONTINUOUS_AI_INTERVAL_SECONDS
    assert agent.retry_delay_seconds("ValueError", 3) == agent.CONTINUOUS_AI_INTERVAL_SECONDS


def test_success_resets_failure_backoff_state():
    agent._status["failure_streak"] = 4
    agent._status["next_retry_seconds"] = agent.MAX_RATE_LIMIT_BACKOFF_SECONDS
    agent._status["last_error_type"] = "RateLimitError"

    agent.apply_result({
        "configured": True,
        "assessment": {
            "status": "HEALTHY",
            "priority": "LOW",
            "summary": "ok",
            "next_action": "continue",
        },
    })

    snapshot = agent.status_snapshot()
    assert snapshot["failure_streak"] == 0
    assert snapshot["next_retry_seconds"] == agent.CONTINUOUS_AI_INTERVAL_SECONDS
    assert snapshot["last_error_type"] is None
    assert snapshot["trade_authority"] is False
    assert snapshot["write_authority"] is False
    assert snapshot["promotion_authority"] is False
