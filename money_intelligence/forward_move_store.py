"""Durable formation path that binds a forecast to a stored reference receipt.

This module is intentionally narrower than reference-price acquisition. It proves that
formation persistence consumes the exact append-only reference-observation receipt and
that the database returns the same receipt back with the formation. It does NOT make a
caller-constructible market capture provider-authentic; that independent service-boundary
problem remains fail-closed until separately repaired and reviewed.

Research only. No prediction, promotion, broker or trading authority is granted.
"""

from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from typing import Any

from money_intelligence.forward_move_ledger import (
    ForwardMoveForecast,
    TrustedFormationReceipt,
    receipt_from_store_row,
    verify_formation_receipt,
)
from money_intelligence.trusted_reference_store import (
    TrustedReferenceReceipt,
    reference_receipt_from_store_row,
)


def _parse_time(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field} must be RFC3339 UTC ending in Z")
    try:
        return datetime.fromisoformat(value[:-1] + "+00:00").astimezone(timezone.utc)
    except ValueError as exc:
        raise ValueError(f"{field} must be valid RFC3339 UTC") from exc


def verify_forecast_reference_receipt(
    forecast: ForwardMoveForecast,
    reference_receipt: TrustedReferenceReceipt,
) -> None:
    """Require every frozen reference field to equal the durable receipt."""

    if not isinstance(forecast, ForwardMoveForecast):
        raise TypeError("forecast must be a ForwardMoveForecast")
    if not isinstance(reference_receipt, TrustedReferenceReceipt):
        raise TypeError("reference_receipt must be a TrustedReferenceReceipt")
    if forecast.asset_id != reference_receipt.asset_id:
        raise ValueError("forecast asset does not match durable reference receipt")
    if forecast.reference_price_source_id != reference_receipt.source_id:
        raise ValueError("forecast reference source does not match durable reference receipt")
    if forecast.reference_price_observation_id != reference_receipt.observation_id:
        raise ValueError("forecast reference observation id does not match durable receipt")
    if forecast.reference_price_observation_sha256 != reference_receipt.evidence_sha256:
        raise ValueError("forecast reference evidence SHA does not match durable receipt")
    if Decimal(str(forecast.reference_price)) != Decimal(str(reference_receipt.reference_price)):
        raise ValueError("forecast reference price does not match durable receipt")
    if forecast.reference_price_observed_at.astimezone(timezone.utc) != reference_receipt.observed_at:
        raise ValueError("forecast reference observation time does not match durable receipt")
    if reference_receipt.server_created_at > forecast.formed_at.astimezone(timezone.utc):
        raise ValueError("forecast cannot declare formation before durable reference receipt")


def _verify_returned_reference(
    row: dict[str, Any],
    expected: TrustedReferenceReceipt,
) -> None:
    if row.get("reference_observation_sequence") != expected.sequence:
        raise ValueError("formation receipt references unexpected reference observation")
    created_at = _parse_time(
        row.get("reference_observation_created_at"),
        field="reference_observation_created_at",
    )
    if created_at != expected.server_created_at:
        raise ValueError("formation returned reference receipt time mismatch")
    stored = row.get("reference_observation")
    if not isinstance(stored, dict):
        raise ValueError("formation did not return the bound reference observation")
    # The formation RPC returns the reference row payload plus its authoritative
    # created_at separately. Reattach it before using the same strict parser used for
    # the direct reference-observation RPC response.
    stored_with_created_at = dict(stored)
    stored_with_created_at["created_at"] = row.get("reference_observation_created_at")
    parsed = reference_receipt_from_store_row(stored_with_created_at)
    if parsed != expected:
        raise ValueError("formation returned a different durable reference observation")


def formation_receipt_from_bound_store_row(
    forecast: ForwardMoveForecast,
    reference_receipt: TrustedReferenceReceipt,
    row: dict[str, Any],
) -> TrustedFormationReceipt:
    """Parse and independently verify the joined DB formation/reference receipt."""

    if not isinstance(row, dict):
        raise ValueError("formation persistence row must be an object")
    verify_forecast_reference_receipt(forecast, reference_receipt)
    _verify_returned_reference(row, reference_receipt)
    receipt = receipt_from_store_row(row)
    verify_formation_receipt(forecast, receipt)
    return receipt


def persist_forward_move_forecast(
    forecast: ForwardMoveForecast,
    reference_receipt: TrustedReferenceReceipt,
) -> TrustedFormationReceipt:
    """Append a formation only through the DB RPC that consumes the reference receipt."""

    verify_forecast_reference_receipt(forecast, reference_receipt)

    from config import SUPABASE_URL
    from db import configured, headers, http

    if not configured():
        raise RuntimeError("Supabase is not configured for forward formation persistence")
    response = http.post(
        f"{SUPABASE_URL}/rest/v1/rpc/append_big_move_forward_formation_v1",
        headers=headers(),
        json={
            "p_forecast_fingerprint": forecast.fingerprint,
            "p_reference_observation_sequence": reference_receipt.sequence,
            "p_formation_payload": forecast.to_record(),
        },
    )
    if response.status_code >= 300:
        raise RuntimeError(
            f"forward formation persistence failed: {response.status_code} {response.text}"
        )
    rows = response.json()
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise RuntimeError("forward formation persistence returned an invalid receipt")
    return formation_receipt_from_bound_store_row(
        forecast,
        reference_receipt,
        rows[0],
    )
