import continuous_worker_army as army


def test_worker_army_is_bounded_and_research_only():
    assert len(army.WORKERS) == 17
    assert 1 <= army.MAX_CONCURRENT <= 4
    snap = army.snapshot()
    assert snap["trade_authority"] is False
    assert snap["write_authority"] is False
    assert snap["promotion_authority"] is False
    assert snap["broker_connected"] is False
    assert snap["research_only"] is True


def test_worker_mix_has_major_pons_universe_swing_and_cross_asset():
    names = {worker.name for worker in army.WORKERS}
    assert {"major-btc", "major-eth", "major-sol", "major-xrp", "major-link"} <= names
    assert "pons" in names
    assert "swing-majors" in names
    assert {"cross-asset-rank-24h", "cross-asset-rank-7d"} <= names
    assert {f"universe-{idx}" for idx in range(8)} <= names
    cross_24h = next(worker for worker in army.WORKERS if worker.name == "cross-asset-rank-24h")
    cross_7d = next(worker for worker in army.WORKERS if worker.name == "cross-asset-rank-7d")
    assert cross_24h.script == cross_7d.script == "cross_asset_runner.py"
    assert army._is_accuracy_worker(cross_24h)
    assert army._is_accuracy_worker(cross_7d)
    assert not army._is_accuracy_worker(next(worker for worker in army.WORKERS if worker.name == "major-btc"))
    assert cross_24h.env["CROSS_ASSET_HORIZON"] == "24h"
    assert cross_7d.env["CROSS_ASSET_HORIZON"] == "7d"


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
