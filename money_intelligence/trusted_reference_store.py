"""Durable receipt boundary for trusted 2x reference-price captures.

Only a `TrustedReferenceCapture` produced by the server-side cross-venue capture
module is accepted by the public persistence helper.  The database independently
timestamps the append.  The returned receipt is revalidated against the retained
provider response bytes before it may be used by a forecast formation.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from typing import Any

from money_intelligence.trusted_reference_price import (
    MAX_CAPTURE_TO_STORE_AGE,
    SOURCE_ID,
    TrustedReferenceCapture,
    verify_capture_evidence,
)


def _parse_time(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field} must be RFC3339 UTC ending in Z")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(timezone.utc)
    except ValueError as exc:
        raise ValueError(f"{field} must be valid RFC3339 UTC") from exc


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


def reference_receipt_from_store_row(row: dict[str, Any]) -> TrustedReferenceReceipt:
    if not isinstance(row, dict):
        raise ValueError("trusted reference receipt row must be an object")
    sequence = row.get("sequence")
    if not isinstance(sequence, int) or isinstance(sequence, bool) or sequence <= 0:
        raise ValueError("trusted reference receipt sequence must be positive")
    source_id = str(row.get("source_id") or "")
    if source_id != SOURCE_ID:
        raise ValueError("trusted reference receipt source mismatch")
    evidence = row.get("evidence")
    if not isinstance(evidence, dict):
        raise ValueError("trusted reference receipt evidence missing")
    captured_at = _parse_time(row.get("captured_at"), field="captured_at")
    observed_at = _parse_time(row.get("observed_at"), field="observed_at")
    created_at = _parse_time(row.get("created_at"), field="created_at")
    reference_price = _positive_price(row.get("reference_price"))
    evidence_sha256 = str(row.get("evidence_sha256") or "").lower()

    capture = TrustedReferenceCapture(
        asset_id=str(row.get("asset_id") or ""),
        captured_at=captured_at,
        reference_price=reference_price,
        observed_at=observed_at,
        evidence=evidence,
        evidence_sha256=evidence_sha256,
    )
    verify_capture_evidence(capture)
    if not capture.asset_id:
        raise ValueError("trusted reference receipt asset_id missing")
    if observed_at > captured_at:
        raise ValueError("provider observation cannot follow trusted capture time")
    if created_at < captured_at:
        raise ValueError("database receipt cannot predate trusted capture")
    if created_at - captured_at > MAX_CAPTURE_TO_STORE_AGE:
        raise ValueError("trusted capture became stale before database persistence")
    if evidence.get("asset_id") != capture.asset_id:
        raise ValueError("trusted evidence asset does not match receipt")
    if evidence.get("reference_price") != reference_price:
        raise ValueError("trusted evidence price does not match receipt")

    return TrustedReferenceReceipt(
        sequence=sequence,
        asset_id=capture.asset_id,
        reference_price=reference_price,
        observed_at=observed_at,
        captured_at=captured_at,
        server_created_at=created_at,
        source_id=source_id,
        evidence_sha256=evidence_sha256,
        evidence=evidence,
    )


def persist_trusted_reference_capture(
    capture: TrustedReferenceCapture,
) -> TrustedReferenceReceipt:
    """Persist a server-fetched capture; this API has no caller price argument."""

    if not isinstance(capture, TrustedReferenceCapture):
        raise TypeError("capture must be a TrustedReferenceCapture")
    verify_capture_evidence(capture)

    from config import SUPABASE_URL
    from db import configured, headers, http

    if not configured():
        raise RuntimeError("Supabase is not configured for trusted reference persistence")
    response = http.post(
        f"{SUPABASE_URL}/rest/v1/rpc/append_big_move_reference_observation_v1",
        headers=headers(),
        json={"p_capture": capture.to_store_payload()},
    )
    if response.status_code >= 300:
        raise RuntimeError(
            f"trusted reference persistence failed: {response.status_code} {response.text}"
        )
    rows = response.json()
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise RuntimeError("trusted reference persistence returned an invalid receipt")
    return reference_receipt_from_store_row(rows[0])
