import json

import historical_cache
import market_data
import research_observability as obs


def _rows(now_ms):
    return [
        {"ts": now_ms - 120_000, "open": 100.0, "high": 101.0, "low": 99.0, "close": 100.5, "volume": 10.0, "quote_volume": 1000.0},
        {"ts": now_ms - 60_000, "open": 100.5, "high": 102.0, "low": 100.0, "close": 101.0, "volume": 11.0, "quote_volume": 1100.0},
    ]


def test_cache_metrics_count_miss_hit_and_rejection(tmp_path, monkeypatch):
    metrics_dir = tmp_path / "metrics"
    cache_dir = tmp_path / "cache"
    monkeypatch.setattr(obs, "DEFAULT_METRICS_DIR", metrics_dir)
    now_ms = 2_000_000_000_000

    assert historical_cache.read_history("BTC-USDT", "1H", 100, 5000, now_ms=now_ms, cache_dir=cache_dir) is None
    assert historical_cache.write_history("BTC-USDT", "1H", 100, 5000, _rows(now_ms), now_ms=now_ms, cache_dir=cache_dir)
    assert historical_cache.read_history("BTC-USDT", "1H", 100, 5000, now_ms=now_ms, cache_dir=cache_dir) == _rows(now_ms)

    files = list(cache_dir.glob("*.json"))
    assert len(files) == 1
    payload = json.loads(files[0].read_text(encoding="utf-8"))
    payload["rows_sha256"] = "0" * 64
    files[0].write_text(json.dumps(payload), encoding="utf-8")
    assert historical_cache.read_history("BTC-USDT", "1H", 100, 5000, now_ms=now_ms, cache_dir=cache_dir) is None

    snap = obs.snapshot(metrics_dir=metrics_dir)
    assert snap["cache"]["misses"] == 1
    assert snap["cache"]["hits"] == 1
    assert snap["cache"]["rejections"] == 1
    assert snap["cache"]["reads_observed"] == 3
    assert snap["cache"]["read_latency_ms"]["samples"] == 3
    assert snap["trade_authority"] is False
    assert snap["promotion_authority"] is False
    assert snap["signal_authority"] is False
    assert snap["research_only"] is True


def test_history_network_metrics_record_success_and_failure(tmp_path):
    obs.record_history_network_fetch(
        "BTC-USDT", "1H", request_count=3, rows_received=250,
        network_latency_ms=120.0, success=True, metrics_dir=tmp_path,
    )
    obs.record_history_network_fetch(
        "ETH-USDT", "1H", request_count=2, rows_received=100,
        network_latency_ms=80.0, success=False, error_type="TimeoutError", metrics_dir=tmp_path,
    )
    snap = obs.snapshot(metrics_dir=tmp_path)
    network = snap["history_network"]
    assert network["fetches"] == 2
    assert network["failures"] == 1
    assert network["failure_rate"] == 0.5
    assert network["request_count"] == 5
    assert network["rows_received"] == 350
    assert network["network_latency_ms"]["mean"] == 100.0
    assert network["avg_requests_per_fetch"] == 2.5
    assert network["last_fetch"]["error_type"] == "TimeoutError"
    assert snap["trade_authority"] is False


def test_get_history_records_only_network_duration(tmp_path, monkeypatch):
    metrics_dir = tmp_path / "metrics"
    monkeypatch.setattr(obs, "DEFAULT_METRICS_DIR", metrics_dir)
    monkeypatch.setattr(market_data, "read_shared_history", lambda *args, **kwargs: None)
    monkeypatch.setattr(market_data, "write_shared_history", lambda *args, **kwargs: True)
    monkeypatch.setattr(market_data, "prune_shared_history_cache", lambda: 0)
    market_data.clear_history_cache()

    now = 2_000_000_000_000
    raw = [
        [str(now - 60_000), "100", "101", "99", "100.5", "10", "0", "1000", "1"],
        [str(now - 120_000), "99", "100", "98", "99.5", "11", "0", "1100", "1"],
    ]
    calls = {"count": 0}

    def fake_okx(path, params=None):
        assert path == "/api/v5/market/history-candles"
        calls["count"] += 1
        return raw

    ticks = iter([10.0, 10.025])
    monkeypatch.setattr(market_data, "okx_get", fake_okx)
    monkeypatch.setattr(market_data.time, "monotonic", lambda: next(ticks))
    monkeypatch.setattr(market_data.time, "sleep", lambda _: None)

    rows = market_data.get_history("BTC-USDT", bar="1H", bars=100, max_bars=100)
    assert len(rows) == 2
    assert calls["count"] == 1
    snap = obs.snapshot(metrics_dir=metrics_dir)
    network = snap["history_network"]
    assert network["fetches"] == 1
    assert network["request_count"] == 1
    assert network["rows_received"] == 2
    assert network["network_latency_ms"]["mean"] == 25.0
    assert "excludes cache" in network["scope"]


def test_worker_metrics_surface_acc002_evidence_and_failure_rates(tmp_path):
    evidence_24h = {"horizon": "24h", "selected_evaluation": {"acc002_research_pass": False}, "samples": 20}
    evidence_7d = {"horizon": "7d", "selected_evaluation": None, "samples": 12}

    obs.record_worker_result("cross-asset-rank-24h", 0, 12.5, evidence_24h, metrics_dir=tmp_path)
    obs.record_worker_result("cross-asset-rank-7d", -9, 30.0, evidence_7d, metrics_dir=tmp_path)
    obs.record_worker_result("major-btc", 1, 4.0, None, metrics_dir=tmp_path)

    snap = obs.snapshot(metrics_dir=tmp_path)
    assert snap["workers"]["completed"] == 3
    assert snap["workers"]["failed"] == 2
    assert snap["workers"]["timeouts"] == 1
    assert snap["workers"]["failure_rate"] == 0.6667
    assert snap["acc002"]["cross-asset-rank-24h"]["latest_evidence"] == evidence_24h
    assert snap["acc002"]["cross-asset-rank-7d"]["last_exit_code"] == -9


def test_invalid_metric_event_cannot_create_authority(tmp_path):
    obs.record_cache_read("not-a-real-result", 1.0, metrics_dir=tmp_path)
    obs.record_history_network_fetch(
        "BTC-USDT", "1H", request_count="bad", rows_received=1,
        network_latency_ms=1.0, success=True, metrics_dir=tmp_path,
    )
    snap = obs.snapshot(metrics_dir=tmp_path)
    assert snap["cache"]["reads_observed"] == 0
    assert snap["history_network"]["fetches"] == 0
    assert snap["trade_authority"] is False
    assert snap["promotion_authority"] is False
