"""Durable provider-origin boundary for <=90-day 2x reference prices.

Authoritative reference observations are fetched *inside Postgres* from two fixed
public spot endpoints.  A caller may provide only the Binance/OKX instrument IDs; it
cannot provide price, timestamp, raw provider bytes, evidence hash, or receipt time.
The database appends the observation with its own clock and returns retained provider
bytes, which this module independently re-parses before a formation may consume them.

The older Python `TrustedReferenceCapture` object remains useful for non-authoritative
unit/research plumbing, but it can never be persisted as a trusted prospective receipt.
Research only; no prediction, promotion, broker, or trading authority is granted.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import re
from typing import Any

from money_intelligence.trusted_reference_price import (
    MAX_CAPTURE_TO_STORE_AGE,
    MAX_CROSS_VENUE_DEVIATION_BPS,
    TrustedReferenceCapture,
    _derive_reference,
    _parse_binance,
    _parse_okx,
)


DB_SOURCE_ID = "TRUSTED_DB_CROSS_VENUE_SPOT_REFERENCE_V2"
DB_EVIDENCE_SCHEMA = "trusted_db_cross_venue_reference_evidence.v2"
DB_FINGERPRINT_DOMAIN = "trusted_db_cross_venue_reference.v2"
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _parse_time(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} must be an RFC3339 UTC timestamp")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise ValueError(f"{field} must be valid RFC3339 UTC") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timedelta(0):
        raise ValueError(f"{field} must be UTC")
    return parsed.astimezone(timezone.utc)


def _positive_price(value: Any) -> str:
    if isinstance(value, bool):
        raise ValueError("reference_price must be positive")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError("reference_price must be positive") from exc
    if not number.is_finite() or number <= 0:
        raise ValueError("reference_price must be positive")
    normalized = number.normalize()
    text = format(normalized, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _db_capture_iso(value: datetime) -> str:
    """Match SQL `YYYY-MM-DDTHH24:MI:SS.USZ` exactly."""
    utc = value.astimezone(timezone.utc)
    return utc.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _evidence_preimage(
    *,
    asset_id: str,
    binance_symbol: str,
    binance_raw_sha256: str,
    okx_inst_id: str,
    okx_raw_sha256: str,
    captured_at: datetime,
    reference_price: str,
) -> bytes:
    return (
        f"{DB_FINGERPRINT_DOMAIN}\n"
        f"{asset_id}\n"
        f"{binance_symbol}\n"
        f"{binance_raw_sha256}\n"
        f"{okx_inst_id}\n"
        f"{okx_raw_sha256}\n"
        f"{_db_capture_iso(captured_at)}\n"
        f"{reference_price}"
    ).encode("utf-8")


@dataclass(frozen=True)
class TrustedReferenceReceipt:
    sequence: int
    asset_id: str
    reference_price: str
    observed_at: datetime
    captured_at: datetime
    server_created_at: datetime
    source_id: str
    evidence_sha256: str
    evidence: dict[str, Any]

    @property
    def observation_id(self) -> str:
        return f"big_move_reference:{self.sequence}"


def _validate_db_evidence(
    *,
    asset_id: str,
    reference_price: str,
    captured_at: datetime,
    observed_at: datetime,
    source_id: str,
    evidence_sha256: str,
    evidence: dict[str, Any],
) -> None:
    if source_id != DB_SOURCE_ID:
        raise ValueError("trusted reference receipt source mismatch")
    if evidence.get("schema") != DB_EVIDENCE_SCHEMA:
        raise ValueError("trusted reference evidence schema mismatch")
    if evidence.get("source_id") != DB_SOURCE_ID:
        raise ValueError("trusted reference evidence source mismatch")
    if evidence.get("asset_id") != asset_id:
        raise ValueError("trusted evidence asset does not match receipt")
    if _positive_price(evidence.get("reference_price")) != reference_price:
        raise ValueError("trusted evidence price does not match receipt")
    if _parse_time(evidence.get("captured_at"), field="evidence.captured_at") != captured_at:
        raise ValueError("trusted evidence capture time does not match receipt")

    derivation = evidence.get("derivation")
    if not isinstance(derivation, dict):
        raise ValueError("trusted reference derivation missing")
    if derivation.get("method") != "ARITHMETIC_MIDPOINT_OF_DB_FETCHED_SPOT_LAST_PRICES":
        raise ValueError("trusted reference derivation method mismatch")
    if derivation.get("version") != "2":
        raise ValueError("trusted reference derivation version mismatch")
    if derivation.get("provider_fetch_authority") != "POSTGRES_HTTP_EXTENSION_FIXED_ENDPOINTS":
        raise ValueError("trusted reference provider authority mismatch")
    if int(derivation.get("max_provider_age_seconds", -1)) != 120:
        raise ValueError("trusted reference provider age policy mismatch")
    if Decimal(str(derivation.get("max_cross_venue_deviation_bps"))) != MAX_CROSS_VENUE_DEVIATION_BPS:
        raise ValueError("trusted reference cross-venue policy mismatch")

    providers = evidence.get("providers")
    if not isinstance(providers, list) or len(providers) != 2:
        raise ValueError("trusted reference evidence requires exactly two providers")
    by_venue = {row.get("venue"): row for row in providers if isinstance(row, dict)}
    binance_stored = by_venue.get("BINANCE_SPOT")
    okx_stored = by_venue.get("OKX_SPOT")
    if not isinstance(binance_stored, dict) or not isinstance(okx_stored, dict):
        raise ValueError("trusted reference provider evidence missing")

    binance_symbol = str(binance_stored.get("symbol") or "")
    okx_inst_id = str(okx_stored.get("symbol") or "")
    expected_okx = f"{asset_id[:-4]}-USDT" if asset_id.endswith("USDT") else ""
    if binance_symbol != asset_id or okx_inst_id != expected_okx:
        raise ValueError("trusted reference cross-venue identity mismatch")

    binance_raw_text = binance_stored.get("raw_response_utf8")
    okx_raw_text = okx_stored.get("raw_response_utf8")
    if not isinstance(binance_raw_text, str) or not isinstance(okx_raw_text, str):
        raise ValueError("trusted reference retained provider bytes missing")
    binance_raw = binance_raw_text.encode("utf-8")
    okx_raw = okx_raw_text.encode("utf-8")
    binance_sha = _sha256(binance_raw)
    okx_sha = _sha256(okx_raw)
    if binance_sha != binance_stored.get("raw_response_sha256"):
        raise ValueError("retained Binance bytes SHA-256 mismatch")
    if okx_sha != okx_stored.get("raw_response_sha256"):
        raise ValueError("retained OKX bytes SHA-256 mismatch")

    binance = _parse_binance(binance_raw, binance_symbol, captured_at)
    okx = _parse_okx(okx_raw, okx_inst_id, captured_at)
    reproduced_price, reproduced_deviation = _derive_reference(binance, okx)
    if reproduced_price != reference_price:
        raise ValueError("trusted reference price does not reproduce from retained bytes")
    if _positive_price(binance_stored.get("price")) != _positive_price(binance["price"]):
        raise ValueError("trusted Binance price does not reproduce")
    if _positive_price(okx_stored.get("price")) != _positive_price(okx["price"]):
        raise ValueError("trusted OKX price does not reproduce")
    if Decimal(str(evidence.get("cross_venue_deviation_bps"))) != Decimal(reproduced_deviation):
        raise ValueError("trusted reference deviation does not reproduce")

    reproduced_observed = max(
        _parse_time(binance["observed_at"], field="binance.observed_at"),
        _parse_time(okx["observed_at"], field="okx.observed_at"),
    )
    if reproduced_observed != observed_at:
        raise ValueError("trusted reference observed_at does not reproduce")

    if not SHA256_RE.fullmatch(evidence_sha256):
        raise ValueError("trusted reference evidence SHA-256 invalid")
    expected_evidence_sha = _sha256(
        _evidence_preimage(
            asset_id=asset_id,
            binance_symbol=binance_symbol,
            binance_raw_sha256=binance_sha,
            okx_inst_id=okx_inst_id,
            okx_raw_sha256=okx_sha,
            captured_at=captured_at,
            reference_price=reference_price,
        )
    )
    if evidence_sha256 != expected_evidence_sha:
        raise ValueError("trusted reference evidence SHA-256 does not reproduce")


def reference_receipt_from_store_row(row: dict[str, Any]) -> TrustedReferenceReceipt:
    if not isinstance(row, dict):
        raise ValueError("trusted reference receipt row must be an object")
    sequence = row.get("sequence")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence <= 0:
        raise ValueError("trusted reference receipt sequence must be positive")
    asset_id = str(row.get("asset_id") or "")
    if not asset_id:
        raise ValueError("trusted reference receipt asset_id missing")
    source_id = str(row.get("source_id") or "")
    evidence = row.get("evidence")
    if not isinstance(evidence, dict):
        raise ValueError("trusted reference receipt evidence missing")
    captured_at = _parse_time(row.get("captured_at"), field="captured_at")
    observed_at = _parse_time(row.get("observed_at"), field="observed_at")
    created_at = _parse_time(row.get("created_at"), field="created_at")
    reference_price = _positive_price(row.get("reference_price"))
    evidence_sha256 = str(row.get("evidence_sha256") or "").lower()

    if observed_at > captured_at:
        raise ValueError("provider observation cannot follow trusted capture time")
    if created_at < captured_at:
        raise ValueError("database receipt cannot predate trusted capture")
    if created_at - captured_at > MAX_CAPTURE_TO_STORE_AGE:
        raise ValueError("trusted capture became stale before database persistence")

    _validate_db_evidence(
        asset_id=asset_id,
        reference_price=reference_price,
        captured_at=captured_at,
        observed_at=observed_at,
        source_id=source_id,
        evidence_sha256=evidence_sha256,
        evidence=evidence,
    )
    return TrustedReferenceReceipt(
        sequence=sequence,
        asset_id=asset_id,
        reference_price=reference_price,
        observed_at=observed_at,
        captured_at=captured_at,
        server_created_at=created_at,
        source_id=source_id,
        evidence_sha256=evidence_sha256,
        evidence=evidence,
    )


def capture_and_persist_trusted_reference(
    *, binance_symbol: str, okx_inst_id: str
) -> TrustedReferenceReceipt:
    """Ask the trusted DB boundary to fetch, parse, hash, and append both providers."""

    binance = str(binance_symbol).strip().upper()
    okx = str(okx_inst_id).strip().upper()
    if not binance or not okx:
        raise ValueError("venue identifiers must be non-empty")

    from config import SUPABASE_URL
    from db import configured, headers, http

    if not configured():
        raise RuntimeError("Supabase is not configured for trusted reference persistence")
    response = http.post(
        f"{SUPABASE_URL}/rest/v1/rpc/append_big_move_reference_observation_v1",
        headers=headers(),
        json={"p_binance_symbol": binance, "p_okx_inst_id": okx},
    )
    if response.status_code >= 300:
        raise RuntimeError(
            f"trusted reference persistence failed: {response.status_code} {response.text}"
        )
    rows = response.json()
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise RuntimeError("trusted reference persistence returned an invalid receipt")
    return reference_receipt_from_store_row(rows[0])


def persist_trusted_reference_capture(
    capture: TrustedReferenceCapture,
) -> TrustedReferenceReceipt:
    """Fail closed: caller-constructible V1 captures are never authoritative."""

    raise RuntimeError(
        "caller-constructible TrustedReferenceCapture cannot receive a trusted receipt; "
        "use capture_and_persist_trusted_reference() so Postgres fetches provider data"
    )
