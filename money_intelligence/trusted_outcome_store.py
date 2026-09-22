"""Trusted post-formation price-path evidence for <=90-day 2x research.

The durable database owns provider acquisition and membership.  Public deterministic
hashes are useful for integrity checking, but they are not proof that a caller-created
row ever existed in the append-only store.  Accordingly this module has two distinct
layers:

* ``ParsedOutcomeObservation`` validates bytes, identities, chronology, and hashes but
  is always ``PARSED_UNTRUSTED``;
* ``derive_trusted_hit_evidence`` can mint non-final trusted HIT evidence only by
  invoking a DB-owned RPC that derives the breach from durable stored rows.

This slice still does not create an authoritative final HIT/EXPIRED/INVALIDATED
resolution.  It grants no candidate ranking, factory metrics, promotion, broker, or
trading authority.  Legacy ``resolve_forecast`` values remain UNTRUSTED_RESOLUTION.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import re
from typing import Any

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


FORMATION_RECEIPT_BINDING_DOMAIN = "trusted_forward_formation_receipt_binding.v1"
OUTCOME_BINDING_DOMAIN = "trusted_forward_outcome_observation.v2"
HIT_EVIDENCE_DOMAIN = "trusted_forward_hit_evidence_set.v2"
PARSED_OUTCOME_STATUS = "PARSED_UNTRUSTED"
OUTCOME_TRUST_STATUS = "TRUSTED_PROVIDER_EVIDENCE_NOT_FINAL_RESOLUTION"
BINANCE_VENUE = "BINANCE_SPOT"
OKX_VENUE = "OKX_SPOT"
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


def _formation_receipt_fingerprint(receipt: TrustedFormationReceipt) -> str:
    """Cross-language identity of the already-persisted trusted formation receipt.

    The forecast fingerprint commits the complete frozen formation payload.  Sequence
    plus server-created time distinguish the durable receipt row.  Postgres derives
    the same value from its stored formation; no caller supplies it to the DB RPC.
    """

    return _sha256(
        (
            f"{FORMATION_RECEIPT_BINDING_DOMAIN}\n"
            f"{receipt.sequence}\n"
            f"{receipt.forecast_fingerprint}\n"
            f"{_db_iso(receipt.server_created_at)}"
        ).encode("utf-8")
    )


def _binding_preimage(
    *,
    formation_sequence: int,
    forecast_fingerprint: str,
    formation_receipt_fingerprint: str,
    asset_id: str,
    binance_symbol: str,
    okx_inst_id: str,
    source_reference_sequence: int,
    source_evidence_sha256: str,
    observed_price: str,
    observed_at: datetime,
    captured_at: datetime,
) -> bytes:
    return (
        f"{OUTCOME_BINDING_DOMAIN}\n"
        f"{formation_sequence}\n"
        f"{forecast_fingerprint}\n"
        f"{formation_receipt_fingerprint}\n"
        f"{asset_id}\n"
        f"{BINANCE_VENUE}\n"
        f"{binance_symbol}\n"
        f"{OKX_VENUE}\n"
        f"{okx_inst_id}\n"
        f"{source_reference_sequence}\n"
        f"{source_evidence_sha256}\n"
        f"{observed_price}\n"
        f"{_db_iso(observed_at)}\n"
        f"{_db_iso(captured_at)}"
    ).encode("utf-8")


@dataclass(frozen=True)
class ParsedOutcomeObservation:
    """Integrity-checked transport object with no durable-origin authority."""

    sequence: int
    formation_sequence: int
    forecast_fingerprint: str
    formation_receipt_fingerprint: str
    source_reference_observation_sequence: int
    asset_id: str
    binance_symbol: str
    okx_inst_id: str
    observed_price: str
    observed_at: datetime
    captured_at: datetime
    source_evidence_sha256: str
    binding_sha256: str
    server_created_at: datetime
    source_reference_observation: dict[str, Any]
    trust_status: str = PARSED_OUTCOME_STATUS

    @property
    def source_reference_receipt(self) -> TrustedReferenceReceipt:
        """Re-parse retained provider bytes whenever the parsed row is consumed."""
        return reference_receipt_from_store_row(dict(self.source_reference_observation))


@dataclass(frozen=True)
class TrustedHitEvidence:
    """DB-derived provider evidence that at least one stored sample breached target.

    ``breach_observed_at`` is the event time of the DB-selected stored breach sample;
    it is not a claim about the true first market crossing.  Final time-to-event and
    HIT/EXPIRED/INVALIDATED resolution require the later complete-path contract.
    """

    formation_sequence: int
    forecast_fingerprint: str
    formation_receipt_fingerprint: str
    target_price: str
    observed_price: str
    breach_observed_at: datetime
    observation_sequence: int
    observation_binding_sha256: str
    evidence_set_sha256: str
    trust_status: str = OUTCOME_TRUST_STATUS


def outcome_observation_receipt_from_store_row(
    row: dict[str, Any],
) -> ParsedOutcomeObservation:
    """Parse/reproduce one row, deliberately without granting DB-origin authority."""

    if not isinstance(row, dict):
        raise ValueError("outcome observation row must be an object")
    sequence = _positive_int(row.get("sequence"), field="sequence")
    formation_sequence = _positive_int(
        row.get("formation_sequence"), field="formation_sequence"
    )
    forecast_fingerprint = _sha256_text(
        row.get("forecast_fingerprint"), field="forecast_fingerprint"
    )
    formation_receipt_fingerprint = _sha256_text(
        row.get("formation_receipt_fingerprint"),
        field="formation_receipt_fingerprint",
    )
    source_sequence = _positive_int(
        row.get("source_reference_observation_sequence"),
        field="source_reference_observation_sequence",
    )
    asset_id = str(row.get("asset_id") or "").strip().upper()
    binance_symbol = str(row.get("binance_symbol") or "").strip().upper()
    okx_inst_id = str(row.get("okx_inst_id") or "").strip().upper()
    if not asset_id:
        raise ValueError("outcome observation asset_id missing")
    if not binance_symbol or not okx_inst_id:
        raise ValueError("outcome observation venue instruments missing")
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
        raise ValueError("outcome source reference observation missing")
    source = reference_receipt_from_store_row(dict(source_row))

    if source.sequence != source_sequence:
        raise ValueError("outcome row references unexpected source observation")
    if source.asset_id != asset_id:
        raise ValueError("outcome source asset does not match bound asset")
    if source.evidence_sha256 != source_evidence_sha256:
        raise ValueError("outcome source evidence SHA does not match bound digest")
    if Decimal(source.reference_price) != Decimal(observed_price):
        raise ValueError("outcome observed price does not match provider receipt")
    if source.observed_at != observed_at or source.captured_at != captured_at:
        raise ValueError("outcome chronology does not match provider receipt")
    if observed_at > captured_at:
        raise ValueError("outcome provider observation cannot follow capture")
    if server_created_at < source.server_created_at or server_created_at < captured_at:
        raise ValueError("outcome binding cannot predate its source observation")

    providers = source.evidence.get("providers")
    if not isinstance(providers, list) or len(providers) != 2:
        raise ValueError("outcome source provider evidence missing")
    by_venue = {
        provider.get("venue"): provider
        for provider in providers
        if isinstance(provider, dict)
    }
    binance = by_venue.get(BINANCE_VENUE)
    okx = by_venue.get(OKX_VENUE)
    if not isinstance(binance, dict) or not isinstance(okx, dict):
        raise ValueError("outcome source venue evidence missing")
    if binance.get("symbol") != binance_symbol or okx.get("symbol") != okx_inst_id:
        raise ValueError("outcome source venue/instrument identity mismatch")
    if binance_symbol != asset_id:
        raise ValueError("outcome Binance symbol does not match canonical asset")
    expected_okx = f"{asset_id[:-4]}-USDT" if asset_id.endswith("USDT") else ""
    if okx_inst_id != expected_okx:
        raise ValueError("outcome OKX instrument does not match canonical asset")

    expected_binding = _sha256(
        _binding_preimage(
            formation_sequence=formation_sequence,
            forecast_fingerprint=forecast_fingerprint,
            formation_receipt_fingerprint=formation_receipt_fingerprint,
            asset_id=asset_id,
            binance_symbol=binance_symbol,
            okx_inst_id=okx_inst_id,
            source_reference_sequence=source_sequence,
            source_evidence_sha256=source_evidence_sha256,
            observed_price=observed_price,
            observed_at=observed_at,
            captured_at=captured_at,
        )
    )
    if binding_sha256 != expected_binding:
        raise ValueError("outcome binding SHA-256 does not reproduce")

    return ParsedOutcomeObservation(
        sequence=sequence,
        formation_sequence=formation_sequence,
        forecast_fingerprint=forecast_fingerprint,
        formation_receipt_fingerprint=formation_receipt_fingerprint,
        source_reference_observation_sequence=source_sequence,
        asset_id=asset_id,
        binance_symbol=binance_symbol,
        okx_inst_id=okx_inst_id,
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
    observation: ParsedOutcomeObservation,
) -> None:
    """Verify identity/chronology only; this does not upgrade origin authority."""

    verify_formation_receipt(forecast, formation_receipt)
    if observation.formation_sequence != formation_receipt.sequence:
        raise ValueError("outcome observation is bound to a different formation sequence")
    if observation.forecast_fingerprint != forecast.fingerprint:
        raise ValueError("outcome observation is bound to a different forecast")
    expected_receipt_fingerprint = _formation_receipt_fingerprint(formation_receipt)
    if observation.formation_receipt_fingerprint != expected_receipt_fingerprint:
        raise ValueError("outcome observation is bound to a different formation receipt fingerprint")
    if observation.asset_id != forecast.asset_id:
        raise ValueError("outcome observation is bound to a different asset")

    source = observation.source_reference_receipt
    if source.asset_id != forecast.asset_id:
        raise ValueError("outcome provider evidence is bound to a different asset")
    if observation.observed_at <= formation_receipt.server_created_at:
        raise ValueError("pre-formation provider evidence cannot count as outcome evidence")
    if observation.captured_at <= formation_receipt.server_created_at:
        raise ValueError("pre-formation capture cannot count as outcome evidence")
    if observation.server_created_at < observation.captured_at:
        raise ValueError("outcome row cannot predate its capture")

    expiry = trusted_expires_at(forecast, formation_receipt)
    if observation.observed_at > expiry or observation.captured_at > expiry:
        raise ValueError("outcome observation falls outside the trusted forecast horizon")


def _post_rpc(path: str, payload: dict[str, Any]) -> Any:
    from config import SUPABASE_URL
    from db import configured, headers, http

    if not configured():
        raise RuntimeError("Supabase is not configured for trusted outcome persistence")
    response = http.post(
        f"{SUPABASE_URL}/rest/v1/rpc/{path}",
        headers=headers(),
        json=payload,
    )
    if response.status_code >= 300:
        raise RuntimeError(
            f"trusted outcome database RPC failed: {response.status_code} {response.text}"
        )
    return response.json()


def _db_derived_hit_row(formation_sequence: int) -> dict[str, Any] | None:
    rows = _post_rpc(
        "derive_big_move_forward_hit_evidence_v1",
        {"p_formation_sequence": formation_sequence},
    )
    if not isinstance(rows, list):
        raise RuntimeError("trusted HIT derivation returned an invalid response")
    if not rows:
        return None
    if len(rows) != 1 or not isinstance(rows[0], dict):
        raise RuntimeError("trusted HIT derivation returned an ambiguous response")
    return rows[0]


def derive_trusted_hit_evidence(
    forecast: ForwardMoveForecast,
    formation_receipt: TrustedFormationReceipt,
) -> TrustedHitEvidence:
    """Derive non-final HIT evidence only through the DB-owned stored-row query.

    There is intentionally no caller-supplied observations argument.  Locally parsed
    rows, even with perfectly reproduced public hashes, can never mint this object.
    """

    verify_formation_receipt(forecast, formation_receipt)
    row = _db_derived_hit_row(formation_receipt.sequence)
    if row is None:
        raise ValueError("authoritative stored observations do not prove a target hit")

    target_price = _positive_price(row.get("target_price"), field="target_price")
    expected_target = _positive_price(forecast.target_price, field="target_price")
    if Decimal(target_price) != Decimal(expected_target):
        raise ValueError("DB-derived target price does not match frozen forecast")

    observation_row = row.get("breach_observation")
    if not isinstance(observation_row, dict):
        raise ValueError("DB-derived HIT evidence is missing its durable breach observation")
    observation = outcome_observation_receipt_from_store_row(observation_row)
    verify_outcome_observation_receipt(forecast, formation_receipt, observation)
    if Decimal(observation.observed_price) < Decimal(target_price):
        raise ValueError("DB-derived observation does not actually breach the frozen target")

    expected_receipt_fingerprint = _formation_receipt_fingerprint(formation_receipt)
    if row.get("forecast_fingerprint") != forecast.fingerprint:
        raise ValueError("DB-derived HIT is bound to a different forecast")
    if row.get("formation_receipt_fingerprint") != expected_receipt_fingerprint:
        raise ValueError("DB-derived HIT is bound to a different formation receipt")

    evidence_set_sha256 = _sha256(
        (
            f"{HIT_EVIDENCE_DOMAIN}\n"
            f"{formation_receipt.sequence}\n"
            f"{forecast.fingerprint}\n"
            f"{expected_receipt_fingerprint}\n"
            f"{target_price}\n"
            f"{observation.sequence}\n"
            f"{observation.binding_sha256}"
        ).encode("utf-8")
    )

    return TrustedHitEvidence(
        formation_sequence=formation_receipt.sequence,
        forecast_fingerprint=forecast.fingerprint,
        formation_receipt_fingerprint=expected_receipt_fingerprint,
        target_price=target_price,
        observed_price=observation.observed_price,
        breach_observed_at=observation.observed_at,
        observation_sequence=observation.sequence,
        observation_binding_sha256=observation.binding_sha256,
        evidence_set_sha256=evidence_set_sha256,
    )


def capture_and_persist_trusted_outcome_observation(
    forecast: ForwardMoveForecast,
    formation_receipt: TrustedFormationReceipt,
) -> ParsedOutcomeObservation:
    """Append through Postgres, then return an integrity-checked *parsed* row.

    The append itself is DB-authoritative.  The returned Python object deliberately
    remains ``PARSED_UNTRUSTED`` so it cannot be confused with durable-membership
    authority.  ``derive_trusted_hit_evidence`` must re-enter the DB-owned boundary.
    """

    verify_formation_receipt(forecast, formation_receipt)
    rows = _post_rpc(
        "append_big_move_forward_outcome_observation_v1",
        {"p_formation_sequence": formation_receipt.sequence},
    )
    if not isinstance(rows, list) or len(rows) != 1 or not isinstance(rows[0], dict):
        raise RuntimeError("trusted outcome persistence returned an invalid receipt")
    parsed = outcome_observation_receipt_from_store_row(rows[0])
    verify_outcome_observation_receipt(forecast, formation_receipt, parsed)
    return parsed
