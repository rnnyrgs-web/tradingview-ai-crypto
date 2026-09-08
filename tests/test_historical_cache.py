import json
from pathlib import Path

import historical_cache as cache


def _rows(now_ms):
    base = now_ms - 300_000
    return [
        {
            "ts": base,
            "open": 100.0,
            "high": 102.0,
            "low": 99.0,
            "close": 101.0,
            "volume": 10.0,
            "quote_volume": 1000.0,
        },
        {
            "ts": base + 60_000,
            "open": 101.0,
            "high": 103.0,
            "low": 100.0,
            "close": 102.0,
            "volume": 11.0,
            "quote_volume": 1100.0,
        },
    ]


def test_shared_cache_round_trip_is_bucket_keyed_and_integrity_checked(tmp_path):
    now_ms = 2_000_000_000_000
    rows = _rows(now_ms)
    assert cache.write_history("BTC-USDT", "1H", 100, 50000, rows, now_ms=now_ms, ttl_seconds=900, cache_dir=tmp_path)
    assert cache.read_history("BTC-USDT", "1H", 100, 50000, now_ms=now_ms + 1_000, ttl_seconds=900, cache_dir=tmp_path) == rows
    assert cache.read_history("ETH-USDT", "1H", 100, 50000, now_ms=now_ms + 1_000, ttl_seconds=900, cache_dir=tmp_path) is None


def test_next_ttl_bucket_does_not_reuse_previous_snapshot(tmp_path):
    ttl = 60
    now_ms = 2_000_000_040_000
    rows = _rows(now_ms)
    assert cache.write_history("BTC-USDT", "1H", 100, 50000, rows, now_ms=now_ms, ttl_seconds=ttl, cache_dir=tmp_path)
    next_bucket_ms = ((now_ms // (ttl * 1000)) + 1) * ttl * 1000 + 1
    assert cache.read_history("BTC-USDT", "1H", 100, 50000, now_ms=next_bucket_ms, ttl_seconds=ttl, cache_dir=tmp_path) is None


def test_tampered_cache_is_rejected(tmp_path):
    now_ms = 2_000_000_000_000
    rows = _rows(now_ms)
    assert cache.write_history("BTC-USDT", "1H", 100, 50000, rows, now_ms=now_ms, cache_dir=tmp_path)
    path = next(Path(tmp_path).glob("*.json"))
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["rows"][0]["close"] = 999999.0
    path.write_text(json.dumps(payload), encoding="utf-8")
    assert cache.read_history("BTC-USDT", "1H", 100, 50000, now_ms=now_ms, cache_dir=tmp_path) is None


def test_future_or_nonchronological_rows_are_rejected(tmp_path):
    now_ms = 2_000_000_000_000
    rows = _rows(now_ms)
    future = [dict(rows[0], ts=now_ms + cache.MAX_FUTURE_SKEW_MS + 1)]
    assert not cache.write_history("BTC-USDT", "1H", 100, 50000, future, now_ms=now_ms, cache_dir=tmp_path)
    reversed_rows = list(reversed(rows))
    assert not cache.write_history("BTC-USDT", "1H", 100, 50000, reversed_rows, now_ms=now_ms, cache_dir=tmp_path)


def test_existing_valid_object_is_not_overwritten_in_same_bucket(tmp_path):
    now_ms = 2_000_000_000_000
    rows = _rows(now_ms)
    assert cache.write_history("BTC-USDT", "1H", 100, 50000, rows, now_ms=now_ms, cache_dir=tmp_path)
    path = next(Path(tmp_path).glob("*.json"))
    before = path.read_bytes()
    changed = [dict(row) for row in rows]
    changed[-1]["close"] = 102.5
    assert cache.write_history("BTC-USDT", "1H", 100, 50000, changed, now_ms=now_ms + 1_000, cache_dir=tmp_path)
    assert path.read_bytes() == before
