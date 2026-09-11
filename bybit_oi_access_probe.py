"""Bounded research-only accessibility probe for Bybit historical open interest.

This module intentionally has no signal, paper, promotion, persistence, or broker
integration. It exists only to test whether the public Bybit V5 open-interest
endpoint is reachable and structurally usable from the deployed research network
before any separately fingerprinted V4 challenger is considered.
"""

from __future__ import annotations

import json

import httpx


SYSTEM_ID = "FFRIZZ_SECONDARY_V4_BYBIT_OI_ACCESS_PROBE"
SOURCE_ID = "bybit_open_interest_history"
ENDPOINT = "https://api.bybit.com/v5/market/open-interest"
ALLOWED_STATUSES = {
    "available",
    "valid_empty",
    "http_451",
    "http_429",
    "http_other_4xx",
    "http_5xx",
    "http_other",
    "timeout",
    "network_error",
    "invalid_payload",
    "source_error",
}


def _http_status_bucket(exc: BaseException) -> str:
    if not isinstance(exc, httpx.HTTPStatusError) or exc.response is None:
        return "http_other"
    status = int(exc.response.status_code)
    if status == 451:
        return "http_451"
    if status == 429:
        return "http_429"
    if 400 <= status < 500:
        return "http_other_4xx"
    if 500 <= status < 600:
        return "http_5xx"
    return "http_other"


def _base_result(status: str, *, points_observed: int = 0) -> dict:
    safe_status = status if status in ALLOWED_STATUSES else "source_error"
    return {
        "system": SYSTEM_ID,
        "diagnostic_only": True,
        "source": SOURCE_ID,
        "status": safe_status,
        "points_observed": max(0, min(int(points_observed), 5)),
        "requests_attempted": 1,
        "symbol_level_data_exposed": False,
        "raw_payload_exposed": False,
        "venue_substitution": False,
        "used_for_signal_scoring": False,
        "persistence_authority": False,
        "paper_trade_authority": False,
        "trade_authority": False,
        "promotion_authority": False,
        "broker_authority": False,
    }


def probe(*, client: httpx.Client | None = None) -> dict:
    """Make exactly one small public request and return bounded diagnostics only."""
    owns_client = client is None
    if client is None:
        client = httpx.Client(
            timeout=httpx.Timeout(connect=5.0, read=10.0, write=5.0, pool=5.0),
            follow_redirects=True,
        )
    try:
        response = client.get(
            ENDPOINT,
            params={
                "category": "linear",
                "symbol": "BTCUSDT",
                "intervalTime": "1h",
                "limit": "5",
            },
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict) or payload.get("retCode") != 0:
            return _base_result("invalid_payload")
        result = payload.get("result")
        if not isinstance(result, dict):
            return _base_result("invalid_payload")
        rows = result.get("list")
        if not isinstance(rows, list):
            return _base_result("invalid_payload")
        if not rows:
            return _base_result("valid_empty")

        valid = 0
        for row in rows[:5]:
            if not isinstance(row, dict):
                continue
            try:
                timestamp = int(row.get("timestamp"))
                open_interest = float(row.get("openInterest"))
            except (TypeError, ValueError):
                continue
            if timestamp > 0 and open_interest >= 0:
                valid += 1
        if valid <= 0:
            return _base_result("invalid_payload")
        return _base_result("available", points_observed=valid)
    except httpx.TimeoutException:
        return _base_result("timeout")
    except httpx.HTTPStatusError as exc:
        return _base_result(_http_status_bucket(exc))
    except httpx.NetworkError:
        return _base_result("network_error")
    except (ValueError, TypeError, json.JSONDecodeError):
        return _base_result("invalid_payload")
    except Exception:
        return _base_result("source_error")
    finally:
        if owns_client:
            client.close()


def main() -> None:
    print(json.dumps(probe(), sort_keys=True, separators=(",", ":")), flush=True)


if __name__ == "__main__":
    main()
