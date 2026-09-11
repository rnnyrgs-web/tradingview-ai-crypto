import asyncio

import continuous_worker_army as army


def test_worker_army_is_bounded_and_research_only():
    assert len(army.WORKERS) == 21
    assert 1 <= army.MAX_CONCURRENT <= 4
    assert 1 <= army.LIGHTWEIGHT_MAX_CONCURRENT <= 4
    snap = army.snapshot()
    assert snap["heavy_worker_count"] == 19
    assert snap["lightweight_worker_count"] == 2
    assert snap["trade_authority"] is False
    assert snap["write_authority"] is False
    assert snap["promotion_authority"] is False
    assert snap["broker_connected"] is False
    assert snap["research_only"] is True


def test_worker_mix_has_major_pons_universe_swing_cross_asset_learning_adaptive_and_basis_roles():
    names = {worker.name for worker in army.WORKERS}
    assert {"major-btc", "major-eth", "major-sol", "major-xrp", "major-link"} <= names
    assert "pons" in names
    assert "swing-majors" in names
    assert {"cross-asset-rank-24h", "cross-asset-rank-7d"} <= names
    assert {"learning-diagnostics", "experiment-factory", "adaptive-accuracy"} <= names
    assert "basis-falsification-btc" in names
    assert {f"universe-{idx}" for idx in range(8)} <= names
    cross_24h = next(worker for worker in army.WORKERS if worker.name == "cross-asset-rank-24h")
    cross_7d = next(worker for worker in army.WORKERS if worker.name == "cross-asset-rank-7d")
    adaptive = next(worker for worker in army.WORKERS if worker.name == "adaptive-accuracy")
    basis = next(worker for worker in army.WORKERS if worker.name == "basis-falsification-btc")
    learning = next(worker for worker in army.WORKERS if worker.name == "learning-diagnostics")
    factory = next(worker for worker in army.WORKERS if worker.name == "experiment-factory")
    assert cross_24h.script == cross_7d.script == "cross_asset_runner.py"
    assert adaptive.script == "research_adaptive_accuracy_runner.py"
    assert basis.script == "basis_falsification_runner.py"
    assert army._is_accuracy_worker(cross_24h)
    assert army._is_accuracy_worker(cross_7d)
    assert army._is_accuracy_worker(adaptive)
    assert army._is_accuracy_worker(basis)
    assert army._is_lightweight_worker(learning)
    assert army._is_lightweight_worker(factory)
    assert not army._is_lightweight_worker(adaptive)
    assert not army._is_lightweight_worker(basis)
    assert cross_24h.env["CROSS_ASSET_HORIZON"] == "24h"
    assert cross_7d.env["CROSS_ASSET_HORIZON"] == "7d"


def test_summary_paths_are_routed_per_worker_script():
    path = "/tmp/summary.json"
    learning = next(worker for worker in army.WORKERS if worker.name == "learning-diagnostics")
    factory = next(worker for worker in army.WORKERS if worker.name == "experiment-factory")
    cross = next(worker for worker in army.WORKERS if worker.name == "cross-asset-rank-24h")
    adaptive = next(worker for worker in army.WORKERS if worker.name == "adaptive-accuracy")
    basis = next(worker for worker in army.WORKERS if worker.name == "basis-falsification-btc")
    assert army._worker_env(learning, path)["RESEARCH_LEARNING_SUMMARY_PATH"] == path
    assert army._worker_env(factory, path)["RESEARCH_EXPERIMENT_SUMMARY_PATH"] == path
    assert army._worker_env(cross, path)["CROSS_ASSET_SUMMARY_PATH"] == path
    assert army._worker_env(adaptive, path)["RESEARCH_ADAPTIVE_ACCURACY_SUMMARY_PATH"] == path
    assert army._worker_env(basis, path)["BASIS_FALSIFICATION_SUMMARY_PATH"] == path


def test_lightweight_workers_do_not_consume_heavy_semaphore_lane():
    lanes = army._build_lanes()
    learning = next(worker for worker in army.WORKERS if worker.name == "learning-diagnostics")
    factory = next(worker for worker in army.WORKERS if worker.name == "experiment-factory")
    btc = next(worker for worker in army.WORKERS if worker.name == "major-btc")
    basis = next(worker for worker in army.WORKERS if worker.name == "basis-falsification-btc")
    adaptive = next(worker for worker in army.WORKERS if worker.name == "adaptive-accuracy")
    cross = next(worker for worker in army.WORKERS if worker.name == "cross-asset-rank-24h")
    assert lanes[learning.name] is lanes[factory.name]
    assert lanes[learning.name] is not lanes[btc.name]
    assert lanes[adaptive.name] is lanes[cross.name]
    assert lanes[adaptive.name] is not lanes[btc.name]
    assert lanes[basis.name] is lanes[adaptive.name]
    assert lanes[basis.name] is not lanes[btc.name]
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


def test_adaptive_idle_state_uses_bounded_recheck_delay():
    adaptive = next(worker for worker in army.WORKERS if worker.name == "adaptive-accuracy")
    evidence = {"evidence_conclusion": "deferred_repeat_no_material_new_evidence"}
    assert army._success_recheck_delay_seconds(adaptive, evidence) == army.ADAPTIVE_IDLE_RECHECK_SECONDS


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
