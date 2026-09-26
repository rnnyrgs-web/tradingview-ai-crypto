import asyncio

import pytest

import continuous_worker_army as army


def test_worker_army_is_bounded_and_research_only():
    assert len(army.WORKERS) == 20
    assert 1 <= army.MAX_CONCURRENT <= 4
    assert 1 <= army.LIGHTWEIGHT_MAX_CONCURRENT <= 4
    snap = army.snapshot()
    assert snap["heavy_worker_count"] == 18
    assert snap["lightweight_worker_count"] == 2
    assert snap["trade_authority"] is False
    assert snap["write_authority"] is False
    assert snap["promotion_authority"] is False
    assert snap["broker_connected"] is False
    assert snap["research_only"] is True


def test_worker_mix_excludes_retired_rejected_profitability_candidate():
    names = {worker.name for worker in army.WORKERS}
    assert {"major-btc", "major-eth", "major-sol", "major-xrp", "major-link"} <= names
    assert "pons" in names
    assert "swing-majors" in names
    assert {"cross-asset-rank-24h", "cross-asset-rank-7d"} <= names
    assert {"learning-diagnostics", "experiment-factory", "adaptive-accuracy"} <= names
    assert "basis-falsification-btc" not in names
    assert all(worker.script != "basis_falsification_runner.py" for worker in army.WORKERS)
    assert {f"universe-{idx}" for idx in range(8)} <= names
    cross_24h = next(worker for worker in army.WORKERS if worker.name == "cross-asset-rank-24h")
    cross_7d = next(worker for worker in army.WORKERS if worker.name == "cross-asset-rank-7d")
    adaptive = next(worker for worker in army.WORKERS if worker.name == "adaptive-accuracy")
    learning = next(worker for worker in army.WORKERS if worker.name == "learning-diagnostics")
    factory = next(worker for worker in army.WORKERS if worker.name == "experiment-factory")
    assert cross_24h.script == cross_7d.script == "cross_asset_runner.py"
    assert adaptive.script == "research_adaptive_accuracy_runner.py"
    assert army._is_accuracy_worker(cross_24h)
    assert army._is_accuracy_worker(cross_7d)
    assert army._is_accuracy_worker(adaptive)
    assert army._is_lightweight_worker(learning)
    assert army._is_lightweight_worker(factory)
    assert not army._is_lightweight_worker(adaptive)
    assert cross_24h.env["CROSS_ASSET_HORIZON"] == "24h"
    assert cross_7d.env["CROSS_ASSET_HORIZON"] == "7d"


def test_no_candidate_safe_idles_all_candidate_specific_heavy_workers():
    objective = army.load_objective()
    discovery_queue = army.load_strategy_discovery_queue()
    assert objective["single_strategy_focus"]["active_candidate"] is None
    assert discovery_queue["active_deep_candidate"] is None
    selected = army.focused_worker_specs(army.WORKERS, objective, discovery_queue)
    assert {spec.name for spec in selected} == {"learning-diagnostics", "experiment-factory"}
    assert all(spec.compute_class == "lightweight" for spec in selected)
    assert "cross-asset-rank-24h" not in {spec.name for spec in selected}


def test_stale_selection_screener_cannot_reauthorize_acc002_when_queue_is_empty():
    objective = {
        "single_strategy_focus": {
            "enabled": True,
            "max_active_deep_candidates": 1,
            "active_candidate": None,
            "selection_screen_workers": ["cross-asset-rank-24h"],
        }
    }
    discovery_queue = {"max_active_deep_candidates": 1, "active_deep_candidate": None}
    selected = army.focused_worker_specs(army.WORKERS, objective, discovery_queue)
    assert {spec.name for spec in selected} == {"learning-diagnostics", "experiment-factory"}


def test_objective_and_discovery_queue_candidate_disagreement_fails_closed():
    objective = {
        "single_strategy_focus": {
            "enabled": True,
            "max_active_deep_candidates": 1,
            "active_candidate": None,
        }
    }
    discovery_queue = {
        "max_active_deep_candidates": 1,
        "active_deep_candidate": {"fingerprint_id": "DISC-OTHER-001-v1"},
    }
    with pytest.raises(RuntimeError, match="disagree on active candidate"):
        army.focused_worker_specs(army.WORKERS, objective, discovery_queue)


def test_mismatched_active_candidate_identities_fail_closed():
    objective = {
        "single_strategy_focus": {
            "enabled": True,
            "max_active_deep_candidates": 1,
            "active_candidate": {
                "fingerprint_id": "DISC-A-001-v1",
                "deep_worker_contracts": {
                    "cross-asset-rank-24h": {"strategy_family": "residual_momentum"}
                },
            },
        }
    }
    discovery_queue = {
        "max_active_deep_candidates": 1,
        "active_deep_candidate": {"fingerprint_id": "DISC-B-001-v1"},
    }
    with pytest.raises(RuntimeError, match="identities disagree"):
        army.focused_worker_specs(army.WORKERS, objective, discovery_queue)


def test_matching_active_candidate_preserves_deep_worker_contract_gate():
    objective = {
        "single_strategy_focus": {
            "enabled": True,
            "max_active_deep_candidates": 1,
            "active_candidate": {
                "fingerprint_id": "DISC-A-001-v1",
                "deep_worker_contracts": {
                    "cross-asset-rank-24h": {"strategy_family": "residual_momentum"}
                },
            },
        }
    }
    discovery_queue = {"max_active_deep_candidates": 1, "active_deep_candidate": "DISC-A-001-v1"}
    selected = army.focused_worker_specs(army.WORKERS, objective, discovery_queue)
    names = {spec.name for spec in selected}
    assert names == {"learning-diagnostics", "experiment-factory", "cross-asset-rank-24h"}
    deep = next(spec for spec in selected if spec.name == "cross-asset-rank-24h")
    assert deep.env["SINGLE_STRATEGY_DEEP_MODE"] == "1"
    assert deep.env["ACTIVE_STRATEGY_FINGERPRINT"] == "DISC-A-001-v1"
    assert deep.env["ACTIVE_STRATEGY_FAMILY"] == "residual_momentum"


def test_invalid_active_deep_worker_still_fails_closed():
    objective = {
        "single_strategy_focus": {
            "enabled": True,
            "max_active_deep_candidates": 1,
            "active_candidate": {
                "fingerprint_id": "DISC-A-001-v1",
                "deep_worker_contracts": {"unknown-worker": {"strategy_family": "residual_momentum"}},
            },
        }
    }
    discovery_queue = {"max_active_deep_candidates": 1, "active_deep_candidate": "DISC-A-001-v1"}
    with pytest.raises(RuntimeError, match="unknown deep workers"):
        army.focused_worker_specs(army.WORKERS, objective, discovery_queue)


def test_summary_paths_are_routed_per_active_worker_script():
    path = "/tmp/summary.json"
    learning = next(worker for worker in army.WORKERS if worker.name == "learning-diagnostics")
    factory = next(worker for worker in army.WORKERS if worker.name == "experiment-factory")
    cross = next(worker for worker in army.WORKERS if worker.name == "cross-asset-rank-24h")
    adaptive = next(worker for worker in army.WORKERS if worker.name == "adaptive-accuracy")
    assert army._worker_env(learning, path)["RESEARCH_LEARNING_SUMMARY_PATH"] == path
    assert army._worker_env(factory, path)["RESEARCH_EXPERIMENT_SUMMARY_PATH"] == path
    assert army._worker_env(cross, path)["CROSS_ASSET_SUMMARY_PATH"] == path
    assert army._worker_env(adaptive, path)["RESEARCH_ADAPTIVE_ACCURACY_SUMMARY_PATH"] == path


def test_lightweight_workers_do_not_consume_heavy_semaphore_lane():
    lanes = army._build_lanes()
    learning = next(worker for worker in army.WORKERS if worker.name == "learning-diagnostics")
    factory = next(worker for worker in army.WORKERS if worker.name == "experiment-factory")
    btc = next(worker for worker in army.WORKERS if worker.name == "major-btc")
    adaptive = next(worker for worker in army.WORKERS if worker.name == "adaptive-accuracy")
    cross = next(worker for worker in army.WORKERS if worker.name == "cross-asset-rank-24h")
    assert lanes[learning.name] is lanes[factory.name]
    assert lanes[learning.name] is not lanes[btc.name]
    assert lanes[adaptive.name] is lanes[cross.name]
    assert lanes[adaptive.name] is not lanes[btc.name]
    assert isinstance(lanes[learning.name], asyncio.Semaphore)


def test_pure_acc002_insufficient_history_gets_long_recheck_without_masking_other_failures():
    cross = next(worker for worker in army.WORKERS if worker.name == "cross-asset-rank-24h")
    pure_history = {
        "research_blocked": True,
        "research_blocked_reason": "insufficient_supported_liquidity_subsets",
        "failed_symbol_count": 4,
        "failure_type_counts": {"InsufficientHistory": 4},
    }
    mixed = {**pure_history, "failure_type_counts": {"InsufficientHistory": 3, "RequestError": 1}}
    assert army._success_recheck_delay_seconds(cross, pure_history) == army.NATURAL_HISTORY_RECHECK_SECONDS
    assert army._success_recheck_delay_seconds(cross, mixed) == army.REST_SECONDS


def test_adaptive_accuracy_uses_slow_success_recheck_to_bound_supabase_egress():
    adaptive = next(worker for worker in army.WORKERS if worker.name == "adaptive-accuracy")
    assert army.ADAPTIVE_ACCURACY_MIN_RECHECK_SECONDS >= 300
    assert (
        army._success_recheck_delay_seconds(adaptive, {"evidence_conclusion": "validation_failed"})
        == army.ADAPTIVE_ACCURACY_MIN_RECHECK_SECONDS
    )
    evidence = {"evidence_conclusion": "deferred_repeat_no_material_new_evidence"}
    assert army._success_recheck_delay_seconds(adaptive, evidence) == max(
        army.ADAPTIVE_ACCURACY_MIN_RECHECK_SECONDS,
        army.ADAPTIVE_IDLE_RECHECK_SECONDS,
    )


def test_explicit_symbol_workers_disable_forced_symbol_duplication(monkeypatch):
    monkeypatch.setenv("RESEARCH_FORCE_SYMBOLS", "SHOULD-NOT-SURVIVE")
    spec = next(worker for worker in army.WORKERS if worker.name == "major-btc")
    env = army._worker_env(spec)
    assert env["RESEARCH_SYMBOLS"] == "BTC-USDT"
    assert env["RESEARCH_SHARD_COUNT"] == "1"
    assert env["RESEARCH_SHARD_INDEX"] == "0"
    assert env["RESEARCH_FORCE_SYMBOLS"] == ""


def test_status_snapshot_is_copy():
    original = army.snapshot()
    original["worker_count"] = -1
    assert army.snapshot()["worker_count"] == len(army.WORKERS)


def test_retry_delay_grows_on_failures_and_is_bounded():
    assert army._retry_delay_seconds(0) == army.REST_SECONDS
    first = army._retry_delay_seconds(1)
    second = army._retry_delay_seconds(2)
    later = army._retry_delay_seconds(20)
    assert first >= army.REST_SECONDS
    assert second >= first
    assert later <= army.MAX_ERROR_BACKOFF_SECONDS


def test_success_resets_retry_delay_to_fast_cycle():
    assert army._retry_delay_seconds(0) < army._retry_delay_seconds(4)


def test_reentry_waiting_for_heavy_lane_is_explicitly_queued_and_healthy():
    spec = next(worker for worker in army.WORKERS if worker.name == "major-eth")
    previous_workers = army._status["workers"]
    previous_active = army._status["active_jobs"]
    army._status["workers"] = {spec.name: army._initial_worker_state(spec)}
    army._status["workers"][spec.name]["state"] = "resting"
    semaphore = asyncio.Semaphore(0)

    async def scenario():
        task = asyncio.create_task(army._run_once(spec, semaphore))
        await asyncio.sleep(0)
        snap = army.snapshot()
        assert snap["workers"][spec.name]["state"] == "queued"
        assert snap["workers"][spec.name]["health"]["healthy"] is True
        assert snap["active_jobs"] == previous_active
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)

    try:
        asyncio.run(scenario())
    finally:
        army._status["workers"] = previous_workers
        army._status["active_jobs"] = previous_active


def test_learning_diagnostics_uses_slow_success_recheck_to_bound_supabase_egress():
    learning = next(worker for worker in army.WORKERS if worker.name == "learning-diagnostics")
    assert army.LEARNING_DIAGNOSTICS_RECHECK_SECONDS >= 300
    assert army._success_recheck_delay_seconds(learning, {"ok": True}) == army.LEARNING_DIAGNOSTICS_RECHECK_SECONDS
    assert army._success_recheck_delay_seconds(learning, None) == army.LEARNING_DIAGNOSTICS_RECHECK_SECONDS


def test_experiment_factory_uses_slow_success_recheck_to_bound_supabase_egress():
    factory = next(worker for worker in army.WORKERS if worker.name == "experiment-factory")
    assert army.EXPERIMENT_FACTORY_RECHECK_SECONDS >= 300
    assert army._success_recheck_delay_seconds(factory, {"ok": True}) == army.EXPERIMENT_FACTORY_RECHECK_SECONDS
    assert army._success_recheck_delay_seconds(factory, None) == army.EXPERIMENT_FACTORY_RECHECK_SECONDS
