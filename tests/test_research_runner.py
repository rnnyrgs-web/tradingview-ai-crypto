import os

import research_runner


def test_stable_shard_is_deterministic_and_bounded():
    first = research_runner.stable_shard("BTC-USDT", 16)
    second = research_runner.stable_shard("BTC-USDT", 16)
    assert first == second
    assert 0 <= first < 16


def test_resolve_research_symbols_explicit(monkeypatch):
    monkeypatch.setenv("RESEARCH_SYMBOLS", "BTC-USDT,ETH-USDT")
    symbols, meta = research_runner.resolve_research_symbols()
    assert symbols == ["BTC-USDT", "ETH-USDT"]
    assert meta["mode"] == "explicit"


def test_dynamic_universe_forces_pons_and_shards(monkeypatch):
    monkeypatch.delenv("RESEARCH_SYMBOLS", raising=False)
    monkeypatch.setenv("RESEARCH_UNIVERSE_SIZE", "3")
    monkeypatch.setenv("RESEARCH_FORCE_SYMBOLS", "PONS-USDT-SWAP")
    monkeypatch.setenv("RESEARCH_SHARD_INDEX", "0")
    monkeypatch.setenv("RESEARCH_SHARD_COUNT", "1")
    monkeypatch.setattr(
        research_runner,
        "build_universe",
        lambda: [
            {"symbol": "BTC-USDT"},
            {"symbol": "ETH-USDT"},
            {"symbol": "SOL-USDT"},
            {"symbol": "XRP-USDT"},
        ],
    )

    symbols, meta = research_runner.resolve_research_symbols()
    assert symbols == ["BTC-USDT", "ETH-USDT", "SOL-USDT", "PONS-USDT-SWAP"]
    assert meta["mode"] == "dynamic_liquid_universe"
    assert meta["universe_size_target"] == 3
    assert "PONS-USDT-SWAP" in meta["forced_symbols"]
