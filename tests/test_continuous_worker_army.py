import asyncio

import continuous_worker_army as army


def test_worker_army_is_bounded_and_research_only():
    assert len(army.WORKERS) == 15
    assert 1 <= army.MAX_CONCURRENT <= 4
    snap = army.snapshot()
    assert snap["trade_authority"] is False
    assert snap["write_authority"] is False
    assert snap["promotion_authority"] is False
    assert snap["broker_connected"] is False
    assert snap["research_only"] is True


def test_worker_mix_has_major_pons_universe_and_swing():
    names = {worker.name for worker in army.WORKERS}
    assert {"major-btc", "major-eth", "major-sol", "major-xrp", "major-link"} <= names
    assert "pons" in names
    assert "swing-majors" in names
    assert {f"universe-{idx}" for idx in range(8)} <= names


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
