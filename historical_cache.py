"""Cross-process immutable cache for normalized historical market data.

Cache objects are keyed by exact request identity plus a bounded time bucket.
Objects are immutable within a bucket and include provenance + SHA-256 integrity.
Any malformed, corrupt, stale, wrong-key, or future-dated object is ignored so
callers can safely fall back to the authoritative public exchange endpoint.

Exact-key single-flight claims prevent multiple worker processes from launching
the same expensive deep-history request at the same time. The first requester
claims the immutable request key and fetches normally; concurrent requesters wait
briefly for that exact validated cache object, then fall back normally if the
claim fails or expires. No request identity, TTL, chronology, or source rule is
weakened by this coordination.
"""

from __future__ import annotations

import hashlib
import json
import math
import os
import tempfile
import time
from pathlib import Path

from research_observability import record_cache_read


CACHE_VERSION = 1
DEFAULT_TTL_SECONDS = max(60, min(int(os.getenv("HISTORY_SHARED_CACHE_TTL_SECONDS", "900")), 3600))
DEFAULT_CACHE_DIR = Path(os.getenv("HISTORY_SHARED_CACHE_DIR", str(Path(tempfile.gettempdir()) / "tradingview-ai-history-cache")))
DEFAULT_SINGLEFLIGHT_WAIT_SECONDS = max(1, min(int(os.getenv("HISTORY_SHARED_CACHE_SINGLEFLIGHT_WAIT_SECONDS", "20")), 60))
SINGLEFLIGHT_POLL_SECONDS = 0.10
MAX_FUTURE_SKEW_MS = 5000
SOURCE = "okx"
ENDPOINT = "/api/v5/market/history-candles"


def _canonical_json(value) -> str:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _rows_digest(rows) -> str:
    return hashlib.sha256(_canonical_json(rows).encode("utf-8")).hexdigest()


def _request_descriptor(symbol, bar, wanted, max_bars, bucket):
    return {
        "version": CACHE_VERSION,
        "source": SOURCE,
        "endpoint": ENDPOINT,
        "symbol": str(symbol),
        "bar": str(bar),
        "wanted": int(wanted),
        "max_bars": int(max_bars),
        "bucket": int(bucket),
    }


def _cache_key(descriptor) -> str:
    return hashlib.sha256(_canonical_json(descriptor).encode("utf-8")).hexdigest()


def _bucket(now_ms, ttl_seconds):
    return int(now_ms // (int(ttl_seconds) * 1000))


def _cache_path(cache_dir, key):
    return Path(cache_dir) / f"{key}.json"


def _claim_path(cache_dir, key):
    return Path(cache_dir) / f".{key}.fetching"


def _valid_rows(rows, now_ms, wanted):
    if not isinstance(rows, list) or not rows or len(rows) > int(wanted):
        return False
    last_ts = -1
    required = ("ts", "open", "high", "low", "close", "volume", "quote_volume")
    for row in rows:
        if not isinstance(row, dict) or any(k not in row for k in required):
            return False
        try:
            ts = int(row["ts"])
            open_px = float(row["open"])
            high_px = float(row["high"])
            low_px = float(row["low"])
            close_px = float(row["close"])
            volume = float(row["volume"])
            quote_volume = float(row["quote_volume"])
        except (TypeError, ValueError):
            return False
        values = (open_px, high_px, low_px, close_px, volume, quote_volume)
        if ts <= last_ts or ts <= 0 or ts > now_ms + MAX_FUTURE_SKEW_MS:
            return False
        if not all(math.isfinite(v) for v in values):
            return False
        if high_px < low_px or min(open_px, high_px, low_px, close_px) <= 0:
            return False
        if volume < 0 or quote_volume < 0:
            return False
        last_ts = ts
    return True


def _read_bucket(symbol, bar, wanted, max_bars, bucket, now_ms, ttl_seconds, cache_dir):
    descriptor = _request_descriptor(symbol, bar, wanted, max_bars, bucket)
    key = _cache_key(descriptor)
    path = _cache_path(cache_dir, key)
    if not path.exists():
        return "miss", None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return "rejection", None
    if not isinstance(payload, dict) or payload.get("descriptor") != descriptor or payload.get("cache_key") != key:
        return "rejection", None
    try:
        fetched_at_ms = int(payload.get("fetched_at_ms"))
    except (TypeError, ValueError):
        return "rejection", None
    if fetched_at_ms <= 0 or fetched_at_ms > now_ms + MAX_FUTURE_SKEW_MS:
        return "rejection", None
    if now_ms - fetched_at_ms >= int(ttl_seconds) * 1000:
        return "miss", None
    rows = payload.get("rows")
    if not _valid_rows(rows, now_ms, wanted):
        return "rejection", None
    if payload.get("rows_sha256") != _rows_digest(rows):
        return "rejection", None
    return "hit", rows


def _claim_is_stale(path: Path, wait_seconds: int) -> bool:
    try:
        age = time.time() - path.stat().st_mtime
    except OSError:
        return False
    return age > max(2, int(wait_seconds) * 2)


def _try_claim(cache_dir: Path, key: str, wait_seconds: int) -> bool:
    cache_dir.mkdir(parents=True, exist_ok=True)
    claim = _claim_path(cache_dir, key)
    if claim.exists() and _claim_is_stale(claim, wait_seconds):
        try:
            claim.unlink()
        except OSError:
            pass
    try:
        fd = os.open(str(claim), os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        return False
    except OSError:
        # Coordination is an optimization only. If the claim cannot be created,
        # preserve the old fail-safe behavior and let the caller fetch normally.
        return True
    try:
        os.write(fd, str(int(time.time() * 1000)).encode("ascii"))
    finally:
        os.close(fd)
    return True


def _release_claim(cache_dir: Path, key: str) -> None:
    try:
        _claim_path(cache_dir, key).unlink()
    except FileNotFoundError:
        pass
    except OSError:
        pass


def read_history(
    symbol,
    bar,
    wanted,
    max_bars,
    *,
    now_ms=None,
    ttl_seconds=None,
    cache_dir=None,
    observe=True,
    singleflight=True,
    singleflight_wait_seconds=None,
):
    started = time.perf_counter()
    use_live_clock = now_ms is None
    now_ms = int(now_ms if now_ms is not None else time.time() * 1000)
    ttl_seconds = int(ttl_seconds or DEFAULT_TTL_SECONDS)
    cache_dir = Path(cache_dir or DEFAULT_CACHE_DIR)
    current_bucket = _bucket(now_ms, ttl_seconds)

    def finish(result, value):
        # One caller request produces exactly one observability outcome even
        # though the implementation may safely inspect one fallback bucket or
        # wait for an exact-key concurrent writer.
        if observe:
            record_cache_read(result, (time.perf_counter() - started) * 1000.0)
        return value

    status, rows = _read_bucket(symbol, bar, wanted, max_bars, current_bucket, now_ms, ttl_seconds, cache_dir)
    if status == "hit":
        return finish("hit", rows)
    if status == "rejection":
        # Never hide a corrupt/current cache object behind an older snapshot.
        return finish("rejection", None)

    # A fetch near the end of a bucket used to become an immediate cache miss at
    # the boundary, causing another full ~30-page history download seconds later.
    # The previous immutable bucket may be reused only when its exact request
    # identity and digest validate and its real fetched age is still < TTL.
    status, rows = _read_bucket(symbol, bar, wanted, max_bars, current_bucket - 1, now_ms, ttl_seconds, cache_dir)
    if status == "hit":
        return finish("hit", rows)
    if status == "rejection":
        return finish("rejection", None)

    if not singleflight:
        return finish("miss", None)

    descriptor = _request_descriptor(symbol, bar, wanted, max_bars, current_bucket)
    key = _cache_key(descriptor)
    wait_seconds = int(singleflight_wait_seconds or DEFAULT_SINGLEFLIGHT_WAIT_SECONDS)
    if _try_claim(cache_dir, key, wait_seconds):
        return finish("miss", None)

    # Another process is fetching this exact immutable request. Wait only for
    # that exact object; never accept a different wanted/max_bars/bar identity.
    deadline = time.monotonic() + max(1, wait_seconds)
    while time.monotonic() < deadline:
        time.sleep(SINGLEFLIGHT_POLL_SECONDS)
        check_now_ms = int(time.time() * 1000) if use_live_clock else now_ms
        status, rows = _read_bucket(symbol, bar, wanted, max_bars, current_bucket, check_now_ms, ttl_seconds, cache_dir)
        if status == "hit":
            return finish("hit", rows)
        if status == "rejection":
            return finish("rejection", None)
        claim = _claim_path(cache_dir, key)
        if not claim.exists() or _claim_is_stale(claim, wait_seconds):
            if _try_claim(cache_dir, key, wait_seconds):
                return finish("miss", None)

    # Coordination must never turn a cache optimization into an availability
    # dependency. After the bounded wait, fall back to authoritative network data.
    return finish("miss", None)


def write_history(symbol, bar, wanted, max_bars, rows, *, now_ms=None, ttl_seconds=None, cache_dir=None):
    now_ms = int(now_ms if now_ms is not None else time.time() * 1000)
    ttl_seconds = int(ttl_seconds or DEFAULT_TTL_SECONDS)
    cache_dir = Path(cache_dir or DEFAULT_CACHE_DIR)
    descriptor = _request_descriptor(symbol, bar, wanted, max_bars, _bucket(now_ms, ttl_seconds))
    key = _cache_key(descriptor)
    if not _valid_rows(rows, now_ms, wanted):
        _release_claim(cache_dir, key)
        return False
    path = _cache_path(cache_dir, key)
    payload = {
        "cache_key": key,
        "descriptor": descriptor,
        "fetched_at_ms": now_ms,
        "rows_sha256": _rows_digest(rows),
        "rows": rows,
    }
    try:
        cache_dir.mkdir(parents=True, exist_ok=True)
        if path.exists():
            existing = read_history(
                symbol, bar, wanted, max_bars,
                now_ms=now_ms, ttl_seconds=ttl_seconds, cache_dir=cache_dir, observe=False, singleflight=False,
            )
            return existing is not None
        with tempfile.NamedTemporaryFile("w", encoding="utf-8", dir=cache_dir, prefix=f".{key}.", suffix=".tmp", delete=False) as handle:
            temp_path = Path(handle.name)
            json.dump(payload, handle, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.link(temp_path, path)
        except FileExistsError:
            pass
        finally:
            try:
                temp_path.unlink()
            except FileNotFoundError:
                pass
        return read_history(
            symbol, bar, wanted, max_bars,
            now_ms=now_ms, ttl_seconds=ttl_seconds, cache_dir=cache_dir, observe=False, singleflight=False,
        ) is not None
    except OSError:
        return False
    finally:
        _release_claim(cache_dir, key)


def prune_cache(*, ttl_seconds=None, cache_dir=None, keep_buckets=2):
    ttl_seconds = int(ttl_seconds or DEFAULT_TTL_SECONDS)
    cache_dir = Path(cache_dir or DEFAULT_CACHE_DIR)
    if not cache_dir.exists():
        return 0
    max_age_seconds = ttl_seconds * max(2, int(keep_buckets) + 1)
    removed = 0
    for path in cache_dir.glob("*.json"):
        try:
            age = time.time() - path.stat().st_mtime
            if age > max_age_seconds:
                path.unlink()
                removed += 1
        except OSError:
            continue
    for path in cache_dir.glob(".*.fetching"):
        try:
            age = time.time() - path.stat().st_mtime
            if age > max_age_seconds:
                path.unlink()
                removed += 1
        except OSError:
            continue
    return removed