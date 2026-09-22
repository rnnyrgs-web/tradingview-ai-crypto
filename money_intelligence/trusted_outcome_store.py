"""Trusted post-formation price-path evidence for <=90-day 2x research.

A prospective forecast is not enough: its outcome must also be derived from evidence
that a caller cannot backfill.  The authoritative append path in this module calls a
Postgres RPC that derives the market instruments from the already-persisted formation,
fetches both fixed spot providers inside Postgres, and binds the resulting provider
receipt to that exact formation.

This first slice intentionally grants only trusted *HIT evidence*.  It does not create
an authoritative final HIT/EXPIRED/INVALIDATED resolution and must not be used as a
factory performance record until a final append-only resolution receipt is added.
Legacy ``resolve_forecast`` values remain UNTRUSTED_RESOLUTION.

Research only.  No ranking, candidate, promotion, broker, or trading authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import re
from typing import Any, Iterable

from money_intelligence.forward_move_ledger import (
    ForwardMoveForecast,
    TrustedFormationReceipt,
    trusted_expires_at,
    verify_formation_receipt,
)
from money_intelligence.trusted_reference_store import (
    TrustedReferenceReceipt,
    reference_receipt_from_store_row,
)


OUTCOME_BINDING_DOMAIN = "trusted_forward_outcome_observation.v1"
HIT_EVIDENCE_DOMAIN = "trusted_forward_hit_evidence_set.v1"
OUTCOME_TRUST_STATUS = "TRUSTED_PROVIDER_EVIDENCE_NOT_FINAL_RESOLUTION"
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


def _db_iso(value: datetime) -> str:
    utc = value.astimezone(timezone.utc)
    return utc.strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _positive_price(value: Any, *, field: str) -> str:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a finite positive number")
    try:
        number = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be a finite positive number") from exc
    if not number.is_finite() or number <= 0:
        raise ValueError(f"{field} must be a finite positive number")
    normalized = number.normalize()
    text = format(normalized, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _positive_int(value: Any, *, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{field} must be a positive integer")
    return value


def _sha256_text(value: Any, *, field: str) -> str:
    text = str(value or "").strip().lower()
    if not SHA256_RE.fullmatch(text):
        raise ValueError(f"{field} must be lowercase SHA-256")
    return text


def _sha256(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _binding_preimage(
    *,
    formation_sequence: int,
    formation_fingerprint: str,
    source_reference_sequence: int,
    asset_id: str,
    source_evidence_sha256: str,
    observed_price: str,
    observed_at: datetime,
    captured_at: datetime,
) -> bytes:
    return (
        f"{OUTCOME_BINDING_DOMAIN}\n"
        f"{formation_sequence}\n"
        f"{formation_fingerprint}\n"
        f"{source_reference_sequence}\n"
        f"{asset_id}\n"
        f"{source_evidence_sha256}\n"
        f"{observed_price}\n"
        f"{_db_iso(observed_at)}\n"
        f"{_db_iso(captured_at)}"
    ).encode("utf-8")


@dataclass(frozen=True)
class TrustedOutcomeObservationReceipt:
    """DB-owned binding of a trusted two-venue spot observation to one formation."""

    sequence: int
    formation_sequence: int
    formation_fingerprint: str
    source_reference_observation_sequence: int
    asset_id: str
    observed_price: str
    observed_at: datetime
    captured_at: datetime
    source_evidence_sha256: str
    binding_sha256: str
    server_created_at: datetime
    source_reference_observation: dict[str, Any]

    @property
    def source_reference_receipt(self) -> TrustedReferenceReceipt:
        """Re-parse retained provider bytes whenever the receipt is consumed."""
        return reference_receipt_from_store_row(dict(self.source_reference_observation))


@dataclass(frozen=True)
class TrustedHitEvidence:
    """Provider-authenticated evidence that a target was observed after formation.

    This is deliberately not a final resolution receipt.  It proves that an ordered
    prefix of trusted outcome observations contains a target breach; a later DB-owned
    final-resolution boundary must bind the complete stored prefix before metrics use.
    """

    formation_sequence: int
    formation_fingerprint: str
    target_price: str
    observed_max_price: str
    first_trusted_hit_observed_at: datetime
    observation_sequences: tuple[int, ...]
    observation_binding_sha256s: tuple[str, ...]
    evidence_set_sha256: str
    trust_status: str = OUTCOME_TRUST_STATUS


def outcome_observation_receipt_from_store_row(
    row: dict[str, Any],
) -> TrustedOutcomeObservationReceipt:
    """Parse and independently reproduce a DB outcome-observation binding."""

    if not isinstance(row, dict):
        raise ValueError("trusted outcome observation row must be an object")
    sequence = _positive_int(row.get("sequence"), field="sequence")
    formation_sequence = _positive_int(
        row.get("formation_sequence"), field="formation_sequence"
    )
    formation_fingerprint = _sha256_text(
        row.get("formation_fingerprint"), field="formation_fingerprint"
    )
    source_sequence = _positive_int(
        row.get("source_reference_observation_sequence"),
        field="source_reference_observation_sequence",
    )
    asset_id = str(row.get("asset_id") or "").strip().upper()
    if not asset_id:
        raise ValueError("trusted outcome observation asset_id missing")
    observed_price = _positive_price(row.get("observed_price"), field="observed_price")
    observed_at = _parse_time(row.get("observed_at"), field="observed_at")
    captured_at = _parse_time(row.get("captured_at"), field="captured_at")
    server_created_at = _parse_time(row.get("created_at"), field="created_at")
    source_evidence_sha256 = _sha256_text(
        row.get("source_evidence_sha256"), field="source_evidence_sha256"
    )
    binding_sha256 = _sha256_text(row.get("binding_sha256"), field="binding_sha256")
    source_row = row.get("source_reference_observation")
    if not isinstance(source_row, dict):
        raise ValueError("trusted outcome source reference observation missing")
    source = reference_receipt_from_store_row(dict(source_row))

    if source.sequence != source_sequence:
        raise ValueError("outcome receipt references unexpected source observation")
    if source.asset_id != asset_id:
        raise ValueError("outcome source asset does not match bound asset")
    if source.evidence_sha256 != source_evidence_sha256:
        raise ValueError("outcome source evidence SHA does not match bound digest")
    if Decimal(source.reference_price) != Decimal(observed_price):
        raise ValueError("outcome observed price does not match trusted provider receipt")
    if source.observed_at != observed_at or source.captured_at != captured_at:
        raise ValueError("outcome chronology does not match trusted provider receipt")
    if observed_at > captured_at:
        raise ValueError("outcome provider observation cannot follow trusted capture")
    if server_created_at < source.server_created_at or server_created_at < captured_at:
        raise ValueError("outcome binding cannot predate its trusted source observation")

    expected_binding = _sha256(
        _binding_preimage(
            formation_sequence=formation_sequence,
            formation_fingerprint=formation_fingerprint,
            source_reference_sequence=source_sequence,
            asset_id=asset_id,
            source_evidence_sha256=source_evidence_sha256,
            observed_price=observed_price,
            observed_at=observed_at,
            captured_at=captured_at,
        )
    )
    if binding_sha256 != expected_binding:
        raise ValueError("trusted outcome binding SHA-256 does not reproduce")

    return TrustedOutcomeObservationReceipt(
        sequence=sequence,
        formation_sequence=formation_sequence,
        formation_fingerprint=formation_fingerprint,
        source_reference_observation_sequence=source_sequence,
        asset_id=asset_id,
        observed_price=observed_price,
        observed_at=observed_at,
        captured_at=captured_at,
        source_evidence_sha256=source_evidence_sha256,
        binding_sha256=binding_sha256,
        server_created_at=server_created_at,
        source_reference_observation=dict(source_row),
    )


def verify_outcome_observation_receipt(
    forecast: ForwardMoveForecast,
    formation_receipt: TrustedFormationReceipt,
    observation: TrustedOutcomeObservationReceipt,
) -> None:
    """Require exact formation/asset binding and strictly post-formation chronology."""

    verify_formation_receipt(forecast, formation_receipt)
    if observation.formation_sequence != formation_receipt.sequence:
        raise ValueError("outcome observation is bound to a different formation sequence")
    if observation.formation_fingerprint != forecast.fingerprint:
        raise ValueError("outcome observation is bound to a different forecast")
    if observation.asset_id != forecast.asset_id:
        raise ValueError("outcome observation is bound to a different asset")

    # Re-parse provider bytes instead of trusting a previously constructed object.
    source = observation.source_reference_receipt
    if source.asset_id != forecast.asset_id:
        raise ValueError("outcome provider evidence is bound to a different asset")
    if observation.observed_at <= formation_receipt.server_created_at:
        raise ValueError("pre-formation provider evidence cannot count as outcome evidence")
    if observation.captured_at <= formation_receipt.server_created_at:
        raise ValueError("pre-formation capture cannot count as outcome evidence")
    if observation.server_created_at < observation.captured_at:
        raise ValueError("outcome receipt cannot predate its trusted capture")

    expiry = trusted_expires_at(forecast, formation_receipt)
    if observation.observed_at > expiry or observation.captured_at > expiry:
        raise ValueError("outcome observation falls outside the trusted forecast horizon")


def derive_trusted_hit_evidence(
    forecast: ForwardMoveForecast,
    formation_receipt: TrustedFormationReceipt,
    observations: Iterable[TrustedOutcomeObservationReceipt],
) -> TrustedHitEvidence:
    """Derive a target breach only from verified post-formation provider receipts.

    The evidence set ends at the first *trusted stored observation* at or above target.
    It is sufficient to prove a target breach, but not to claim that the supplied list
    is the complete database prefix.  Therefore the result is explicitly not a final
    factory resolution and cannot enter prospective performance metrics yet.
    """

    verify_formation_receipt(forecast, formation_receipt)
    ordered = sorted(observations, key=lambda item: item.sequence)
    if not ordered:
        raise ValueError("trusted HIT evidence requires at least one outcome observation")

    seen_sequences: set[int] = set()
    seen_bindings: set[str] = set()
    target = forecast.target_price
    hit_index: int | None = None
    for index, observation in enumerate(ordered):
        if observation.sequence in seen_sequences:
            raise ValueError("duplicate trusted outcome observation sequence")
        if observation.binding_sha256 in seen_bindings:
            raise ValueError("duplicate trusted outcome observation binding")
        seen_sequences.add(observation.sequence)
        seen_bindings.add(observation.binding_sha256)
        verify_outcome_observation_receipt(forecast, formation_receipt, observation)
        if hit_index is None and Decimal(observation.observed_price) >= target:
            hit_index = index

    if hit_index is None:
        raise ValueError("trusted observations do not prove a target hit")

    prefix = ordered[: hit_index + 1]
    max_price = max(Decimal(item.observed_price) for item in prefix)
    first_hit = prefix[-1]
    evidence_lines = "\n".join(
        f"{item.sequence}:{item.binding_sha256}" for item in prefix
    )
    evidence_set_sha256 = _sha256(
        (
            f"{HIT_EVIDENCE_DOMAIN}\n"
            f"{formation_receipt.sequence}\n"
            f"{forecast.fingerprint}\n"
            f"{formation_receipt.fingerprint}\n"
            f"{evidence_lines}"
        ).encode("utf-8")
    )

    return TrustedHitEvidence(
        formation_sequence=formation_receipt.sequence,
        formation_fingerprint=forecast.fingerprint,
        target_price=_positive_price(target, field="target_price"),
        observed_max_price=_positive_price(max_price, field="observed_max_price"),
        first_trusted_hit_observed_at=first_hit.observed_at,
        observation_sequences=tuple(item.sequence for item in prefix),
        observation_binding_sha256s=tuple(item.binding_sha256 for item in prefix),
        evidence_set_sha256=evidence_set_sha256,
    )


def capture_and_persist_trusted_outcome_observation(
    forecast: ForwardMoveForecast,
    formation_receipt: TrustedFormationReceipt,
) -> TrustedOutcomeObservationReceipt:
    """Ask Postgres to derive instruments, fetch both venues, and bind the observation."""

    verify_formation_receipt(forecast, formation_receipt)

    from config import SUPABASE_URL
    from db import configured, headers, http

    if not configured():
        raise RuntimeError("Supabase is not configured for trusted outcome persistence")
    response = http.post(
        f"{SUPABASE_URL}/rest/v1/rpc/append_big_move_forward_outcome_observation_v1",
        headers=headers(),
        json={"p_formation_sequence": formation_receipt.sequence},
    )
    if response.status_code >= 300:
        raise RuntimeError(
            f"trusted outcome persistence failed: {response.status_code} {response.text}"
        )
    rows = response.json()
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise RuntimeError("trusted outcome persistence returned an invalid receipt")
    receipt = outcome_observation_receipt_from_store_row(rows[0])
    verify_outcome_observation_receipt(forecast, formation_receipt, receipt)
    return receipt
