from deployment_canary import CANARY_GRACE_SECONDS, evaluate_canary


def _healthy_inputs():
    coordinator = {
        "production_ok": True,
        "state_ok": True,
        "consecutive_failures": 0,
    }
    army = {
        "supervisor": {
            "healthy": True,
            "stale_workers": [],
            "crashed_workers": [],
            "task_restarts": 0,
        },
        "observability": {
            "workers": {
                "completed": 10,
                "failed": 0,
                "timeouts": 0,
                "failure_rate": 0.0,
            }
        },
    }
    return coordinator, army


def test_canary_warms_without_recommending_rollback():
    coordinator, army = _healthy_inputs()
    result = evaluate_canary(coordinator, army, uptime_seconds=CANARY_GRACE_SECONDS - 1)
    assert result["status"] == "warming"
    assert result["rollback_recommended"] is False


def test_canary_becomes_healthy_after_grace():
    coordinator, army = _healthy_inputs()
    result = evaluate_canary(coordinator, army, uptime_seconds=CANARY_GRACE_SECONDS + 1)
    assert result["status"] == "healthy"
    assert result["rollback_recommended"] is False
    assert result["reasons"] == []


def test_supervisor_failure_recommends_rollback_after_grace():
    coordinator, army = _healthy_inputs()
    army["supervisor"]["healthy"] = False
    army["supervisor"]["stale_workers"] = ["pons"]
    result = evaluate_canary(coordinator, army, uptime_seconds=CANARY_GRACE_SECONDS + 1)
    assert result["status"] == "rollback_recommended"
    assert result["rollback_recommended"] is True
    assert "worker_supervisor_unhealthy" in result["reasons"]
    assert "stale_workers_detected" in result["reasons"]


def test_repeated_dependency_failures_recommend_rollback():
    coordinator, army = _healthy_inputs()
    coordinator["production_ok"] = False
    coordinator["consecutive_failures"] = 3
    result = evaluate_canary(coordinator, army, uptime_seconds=CANARY_GRACE_SECONDS + 1)
    assert result["rollback_recommended"] is True
    assert "production_health_check_failed" in result["reasons"]
    assert "coordinator_repeated_failures" in result["reasons"]


def test_worker_failure_rate_requires_minimum_sample_depth():
    coordinator, army = _healthy_inputs()
    army["observability"]["workers"] = {
        "completed": 1,
        "failed": 1,
        "timeouts": 0,
        "failure_rate": 0.5,
    }
    result = evaluate_canary(coordinator, army, uptime_seconds=CANARY_GRACE_SECONDS + 1)
    assert "worker_failure_rate_exceeded" not in result["reasons"]


def test_canary_has_no_action_or_trading_authority():
    coordinator, army = _healthy_inputs()
    result = evaluate_canary(coordinator, army, uptime_seconds=CANARY_GRACE_SECONDS + 1)
    assert result["automatic_rollback_authority"] is False
    assert result["deployment_authority"] is False
    assert result["repository_write_authority"] is False
    assert result["trade_authority"] is False
    assert result["promotion_authority"] is False
    assert result["broker_connected"] is False
