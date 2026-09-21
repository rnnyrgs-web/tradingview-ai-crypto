"""Trusted contemporaneous reference-price capture for 90-day 2x research.

The public entry point accepts market identifiers only; it never accepts a caller
supplied price, timestamp, raw provider payload, or evidence digest.  The trusted
server fetches Binance and OKX itself, retains the exact UTF-8 response bodies,
parses their provider timestamps deterministically, requires freshness and
cross-venue agreement, and derives the frozen reference price from those responses.

This module is research-only and grants no prediction, promotion, broker, or trade
authority.  A capture still does not count as a prospective forecast until its
immutable database observation receipt and forecast-formation receipt both exist.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
from typing import Any, Callable

import httpx

from config import BINANCE_SPOT_BASE, OKX_BASE


SOURCE_ID = "TRUSTED_CROSS_VENUE_SPOT_REFERENCE_V1"
EVIDENCE_SCHEMA = "trusted_cross_venue_reference_evidence.v1"
MAX_PROVIDER_AGE = timedelta(seconds=120)
MAX_PROVIDER_FUTURE_SKEW = timedelta(seconds=5)
MAX_CAPTURE_TO_STORE_AGE = timedelta(minutes=5)
MAX_CROSS_VENUE_DEVIATION_BPS = Decimal("75")


def _utc(value: datetime, *, field: str) -> datetime:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(timezone.utc)


def _iso(value: datetime, *, field: str) -> str:
    return _utc(value, field=field).isoformat().replace("+00:00", "Z")


def _parse_ms(value: Any, *, field: str) -> datetime:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be epoch milliseconds")
    try:
        milliseconds = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{field} must be epoch milliseconds") from exc
    if milliseconds <= 0:
        raise ValueError(f"{field} must be positive")
    return datetime.fromtimestamp(milliseconds / 1000, tz=timezone.utc)


def _price(value: Any, *, field: str) -> Decimal:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a finite positive number")
    try:
        price = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be a finite positive number") from exc
    if not price.is_finite() or price <= 0:
        raise ValueError(f"{field} must be a finite positive number")
    return price


def _decimal_text(value: Decimal) -> str:
    normalized = value.normalize()
    text = format(normalized, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _provider_age_check(observed_at: datetime, captured_at: datetime, *, provider: str) -> None:
    if observed_at > captured_at + MAX_PROVIDER_FUTURE_SKEW:
        raise ValueError(f"{provider} observation timestamp is implausibly in the future")
    if captured_at - observed_at > MAX_PROVIDER_AGE:
        raise ValueError(f"{provider} observation is stale")


def _parse_binance(raw: bytes, symbol: str, captured_at: datetime) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("Binance response is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict) or payload.get("symbol") != symbol:
        raise ValueError("Binance response symbol mismatch")
    price = _price(payload.get("lastPrice"), field="binance.lastPrice")
    observed_at = _parse_ms(payload.get("closeTime"), field="binance.closeTime")
    _provider_age_check(observed_at, captured_at, provider="Binance")
    return {
        "venue": "BINANCE_SPOT",
        "symbol": symbol,
        "price": _decimal_text(price),
        "observed_at": _iso(observed_at, field="binance.observed_at"),
        "raw_response_sha256": _sha(raw),
        "raw_response_utf8": raw.decode("utf-8"),
    }


def _parse_okx(raw: bytes, inst_id: str, captured_at: datetime) -> dict[str, Any]:
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("OKX response is not valid UTF-8 JSON") from exc
    if not isinstance(payload, dict) or str(payload.get("code", "")) != "0":
        raise ValueError("OKX response code is not success")
    rows = payload.get("data")
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise ValueError("OKX response must contain exactly one ticker")
    row = rows[0]
    if row.get("instId") != inst_id:
        raise ValueError("OKX response instrument mismatch")
    price = _price(row.get("last"), field="okx.last")
    observed_at = _parse_ms(row.get("ts"), field="okx.ts")
    _provider_age_check(observed_at, captured_at, provider="OKX")
    return {
        "venue": "OKX_SPOT",
        "symbol": inst_id,
        "price": _decimal_text(price),
        "observed_at": _iso(observed_at, field="okx.observed_at"),
        "raw_response_sha256": _sha(raw),
        "raw_response_utf8": raw.decode("utf-8"),
    }


def _derive_reference(binance: dict[str, Any], okx: dict[str, Any]) -> tuple[str, str]:
    first = _price(binance["price"], field="binance.price")
    second = _price(okx["price"], field="okx.price")
    midpoint = (first + second) / Decimal("2")
    deviation_bps = abs(first - second) / midpoint * Decimal("10000")
    if deviation_bps > MAX_CROSS_VENUE_DEVIATION_BPS:
        raise ValueError("cross-venue reference prices disagree beyond frozen tolerance")
    return _decimal_text(midpoint), _decimal_text(deviation_bps)


@dataclass(frozen=True)
class TrustedReferenceCapture:
    asset_id: str
    captured_at: datetime
    reference_price: str
    observed_at: datetime
    evidence: dict[str, Any]
    evidence_sha256: str

    @property
    def source_id(self) -> str:
        return SOURCE_ID

    @property
    def observation_id(self) -> str:
        return f"capture:{self.evidence_sha256}"

    def to_store_payload(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "captured_at": _iso(self.captured_at, field="captured_at"),
            "evidence": self.evidence,
            "evidence_sha256": self.evidence_sha256,
            "observed_at": _iso(self.observed_at, field="observed_at"),
            "reference_price": self.reference_price,
            "source_id": SOURCE_ID,
        }


def capture_trusted_reference_price(
    *,
    asset_id: str,
    binance_symbol: str,
    okx_inst_id: str,
    client: httpx.Client | None = None,
    now_fn: Callable[[], datetime] | None = None,
) -> TrustedReferenceCapture:
    """Fetch and derive a reference price without accepting caller market values."""

    asset = str(asset_id).strip()
    binance_symbol = str(binance_symbol).strip().upper()
    okx_inst_id = str(okx_inst_id).strip().upper()
    if not asset or not binance_symbol or not okx_inst_id:
        raise ValueError("asset and venue identifiers must be non-empty")

    captured_at = _utc(
        (now_fn or (lambda: datetime.now(timezone.utc)))(), field="captured_at"
    )
    own_client = client is None
    http = client or httpx.Client(
        timeout=httpx.Timeout(connect=10, read=20, write=10, pool=10),
        follow_redirects=False,
    )
    try:
        binance_response = http.get(
            f"{BINANCE_SPOT_BASE}/api/v3/ticker/24hr",
            params={"symbol": binance_symbol},
        )
        binance_response.raise_for_status()
        okx_response = http.get(
            f"{OKX_BASE}/api/v5/market/ticker",
            params={"instId": okx_inst_id},
        )
        okx_response.raise_for_status()
    finally:
        if own_client:
            http.close()

    # Use exact response bytes.  Do not reserialize provider JSON before hashing.
    binance = _parse_binance(binance_response.content, binance_symbol, captured_at)
    okx = _parse_okx(okx_response.content, okx_inst_id, captured_at)
    reference_price, deviation_bps = _derive_reference(binance, okx)
    observed_at = max(
        datetime.fromisoformat(binance["observed_at"].replace("Z", "+00:00")),
        datetime.fromisoformat(okx["observed_at"].replace("Z", "+00:00")),
    )
    evidence = {
        "asset_id": asset,
        "captured_at": _iso(captured_at, field="captured_at"),
        "cross_venue_deviation_bps": deviation_bps,
        "derivation": {
            "method": "ARITHMETIC_MIDPOINT_OF_TWO_TRUSTED_SPOT_LAST_PRICES",
            "max_cross_venue_deviation_bps": _decimal_text(
                MAX_CROSS_VENUE_DEVIATION_BPS
            ),
            "max_provider_age_seconds": int(MAX_PROVIDER_AGE.total_seconds()),
            "version": "1",
        },
        "providers": [binance, okx],
        "reference_price": reference_price,
        "schema": EVIDENCE_SCHEMA,
        "source_id": SOURCE_ID,
    }
    evidence_sha256 = _sha(_canonical(evidence))
    return TrustedReferenceCapture(
        asset_id=asset,
        captured_at=captured_at,
        reference_price=reference_price,
        observed_at=observed_at,
        evidence=evidence,
        evidence_sha256=evidence_sha256,
    )


def verify_capture_evidence(capture: TrustedReferenceCapture) -> None:
    """Re-parse retained provider bytes and reproduce every derived field."""

    if capture.source_id != SOURCE_ID:
        raise ValueError("unexpected trusted reference source")
    expected_sha = _sha(_canonical(capture.evidence))
    if capture.evidence_sha256 != expected_sha:
        raise ValueError("trusted reference evidence SHA-256 mismatch")
    if capture.evidence.get("schema") != EVIDENCE_SCHEMA:
        raise ValueError("trusted reference evidence schema mismatch")
    providers = capture.evidence.get("providers")
    if not isinstance(providers, list) or len(providers) != 2:
        raise ValueError("trusted reference evidence requires two providers")
    by_venue = {
        row.get("venue"): row for row in providers if isinstance(row, dict)
    }
    binance_stored = by_venue.get("BINANCE_SPOT")
    okx_stored = by_venue.get("OKX_SPOT")
    if not isinstance(binance_stored, dict) or not isinstance(okx_stored, dict):
        raise ValueError("trusted reference provider evidence missing")

    captured_at = _utc(capture.captured_at, field="captured_at")
    binance_raw = str(binance_stored.get("raw_response_utf8", "")).encode("utf-8")
    okx_raw = str(okx_stored.get("raw_response_utf8", "")).encode("utf-8")
    if _sha(binance_raw) != binance_stored.get("raw_response_sha256"):
        raise ValueError("retained Binance bytes SHA-256 mismatch")
    if _sha(okx_raw) != okx_stored.get("raw_response_sha256"):
        raise ValueError("retained OKX bytes SHA-256 mismatch")

    binance = _parse_binance(
        binance_raw, str(binance_stored.get("symbol", "")), captured_at
    )
    okx = _parse_okx(okx_raw, str(okx_stored.get("symbol", "")), captured_at)
    reference_price, deviation_bps = _derive_reference(binance, okx)
    if reference_price != capture.reference_price:
        raise ValueError("trusted reference price does not reproduce from retained bytes")
    if reference_price != capture.evidence.get("reference_price"):
        raise ValueError("trusted reference evidence price mismatch")
    if deviation_bps != capture.evidence.get("cross_venue_deviation_bps"):
        raise ValueError("trusted reference deviation does not reproduce")
