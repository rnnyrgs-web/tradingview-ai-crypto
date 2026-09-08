import json

import historical_cache
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
    snap = obs.snapshot(metrics_dir=tmp_path)
    assert snap["cache"]["reads_observed"] == 0
    assert snap["trade_authority"] is False
    assert snap["promotion_authority"] is False
