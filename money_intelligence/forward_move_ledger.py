"""Point-in-time contract for <=90 day 2x+ forward move research.

Formation and resolution are deliberately separate immutable records. A forecast
may be proposed locally, but it counts as prospective evidence only after a trusted
append-only store has issued a server-created formation receipt. The receipt time,
not caller-supplied chronology, is the effective start of the outcome window.

This module grants no trading, promotion, or OOS-opening authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
import hashlib
import json
import re
from typing import Any, Iterable


FORMATION_SCHEMA = "forward_move_forecast.v1"
RECEIPT_SCHEMA = "forward_move_formation_receipt.v1"
RESOLUTION_SCHEMA = "forward_move_resolution.v1"
MAX_HORIZON_DAYS = 90
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _utc_iso(value: datetime, *, field: str) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _parse_utc(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError(f"{field} must be an RFC3339 UTC timestamp ending in Z")
    try:
        parsed = datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as exc:
        raise ValueError(f"{field} must be a valid RFC3339 timestamp") from exc
    return parsed.astimezone(timezone.utc)


def _decimal_text(value: str | int | float | Decimal, *, field: str) -> str:
    if isinstance(value, bool):
        raise ValueError(f"{field} must be a finite positive number")
    try:
        parsed = Decimal(str(value))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field} must be a finite positive number") from exc
    if not parsed.is_finite() or parsed <= 0:
        raise ValueError(f"{field} must be a finite positive number")
    normalized = parsed.normalize()
    text = format(normalized, "f")
    return text.rstrip("0").rstrip(".") if "." in text else text


def _strings(values: Iterable[str], *, field: str, require_nonempty: bool = False) -> tuple[str, ...]:
    normalized = tuple(sorted({str(value).strip() for value in values if str(value).strip()}))
    if require_nonempty and not normalized:
        raise ValueError(f"{field} must contain at least one non-empty item")
    return normalized


def _sha256_text(value: str, *, field: str) -> str:
    text = str(value).strip().lower()
    if not SHA256_RE.fullmatch(text):
        raise ValueError(f"{field} must be lowercase SHA-256")
    return text


def _fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ForwardMoveForecast:
    """Immutable pre-outcome proposal that still requires a trusted receipt."""

    asset_id: str
    formed_at: datetime
    evidence_cutoff: datetime
    reference_price: str | int | float | Decimal
    reference_price_observed_at: datetime
    reference_price_source_id: str
    reference_price_observation_id: str
    reference_price_observation_sha256: str
    evidence_manifest_sha256: str
    horizon_days: int
    evidence_for: tuple[str, ...]
    evidence_against: tuple[str, ...]
    invalidation_rules: tuple[str, ...]
    target_multiple: str | int | float | Decimal = "2"
    source_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        asset_id = self.asset_id.strip()
        if not asset_id:
            raise ValueError("asset_id must be non-empty")
        _utc_iso(self.formed_at, field="formed_at")
        _utc_iso(self.evidence_cutoff, field="evidence_cutoff")
        _utc_iso(self.reference_price_observed_at, field="reference_price_observed_at")
        if self.evidence_cutoff > self.formed_at:
            raise ValueError("evidence_cutoff cannot be after formed_at")
        if self.reference_price_observed_at > self.evidence_cutoff:
            raise ValueError("reference_price_observed_at cannot be after evidence_cutoff")
        if not isinstance(self.horizon_days, int) or isinstance(self.horizon_days, bool):
            raise ValueError("horizon_days must be an integer")
        if not 1 <= self.horizon_days <= MAX_HORIZON_DAYS:
            raise ValueError(f"horizon_days must be between 1 and {MAX_HORIZON_DAYS}")

        reference_price = _decimal_text(self.reference_price, field="reference_price")
        target_multiple = _decimal_text(self.target_multiple, field="target_multiple")
        if Decimal(target_multiple) < Decimal("2"):
            raise ValueError("target_multiple must be at least 2x")

        source_ids = _strings(self.source_ids, field="source_ids", require_nonempty=True)
        reference_source = self.reference_price_source_id.strip()
        observation_id = self.reference_price_observation_id.strip()
        if not reference_source:
            raise ValueError("reference_price_source_id must be non-empty")
        if not observation_id:
            raise ValueError("reference_price_observation_id must be non-empty")
        if reference_source not in source_ids:
            raise ValueError("reference_price_source_id must be included in source_ids")

        object.__setattr__(self, "asset_id", asset_id)
        object.__setattr__(self, "reference_price", reference_price)
        object.__setattr__(self, "target_multiple", target_multiple)
        object.__setattr__(self, "reference_price_source_id", reference_source)
        object.__setattr__(self, "reference_price_observation_id", observation_id)
        object.__setattr__(self, "reference_price_observation_sha256", _sha256_text(self.reference_price_observation_sha256, field="reference_price_observation_sha256"))
        object.__setattr__(self, "evidence_manifest_sha256", _sha256_text(self.evidence_manifest_sha256, field="evidence_manifest_sha256"))
        object.__setattr__(self, "evidence_for", _strings(self.evidence_for, field="evidence_for", require_nonempty=True))
        object.__setattr__(self, "evidence_against", _strings(self.evidence_against, field="evidence_against"))
        object.__setattr__(self, "invalidation_rules", _strings(self.invalidation_rules, field="invalidation_rules", require_nonempty=True))
        object.__setattr__(self, "source_ids", source_ids)

    @property
    def declared_expires_at(self) -> datetime:
        """Caller-declared horizon only; trusted resolution uses receipt time."""
        return self.formed_at + timedelta(days=self.horizon_days)

    @property
    def target_price(self) -> Decimal:
        return Decimal(str(self.reference_price)) * Decimal(str(self.target_multiple))

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "evidence_against": list(self.evidence_against),
            "evidence_cutoff": _utc_iso(self.evidence_cutoff, field="evidence_cutoff"),
            "evidence_for": list(self.evidence_for),
            "evidence_manifest_sha256": self.evidence_manifest_sha256,
            "formed_at": _utc_iso(self.formed_at, field="formed_at"),
            "horizon_days": self.horizon_days,
            "invalidation_rules": list(self.invalidation_rules),
            "reference_price": str(self.reference_price),
            "reference_price_observation_id": self.reference_price_observation_id,
            "reference_price_observation_sha256": self.reference_price_observation_sha256,
            "reference_price_observed_at": _utc_iso(self.reference_price_observed_at, field="reference_price_observed_at"),
            "reference_price_source_id": self.reference_price_source_id,
            "schema": FORMATION_SCHEMA,
            "source_ids": list(self.source_ids),
            "target_multiple": str(self.target_multiple),
        }

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.canonical_payload())

    def to_record(self) -> dict[str, Any]:
        payload = self.canonical_payload()
        payload["forecast_fingerprint"] = self.fingerprint
        payload["declared_expires_at"] = _utc_iso(self.declared_expires_at, field="declared_expires_at")
        payload["prospective_status"] = "UNTRUSTED_UNTIL_SERVER_RECEIPT"
        return payload


@dataclass(frozen=True)
class TrustedFormationReceipt:
    """Receipt issued by the append-only store using its own server clock."""

    sequence: int
    forecast_fingerprint: str
    server_created_at: datetime
    formation_payload: dict[str, Any]

    def __post_init__(self) -> None:
        if not isinstance(self.sequence, int) or isinstance(self.sequence, bool) or self.sequence <= 0:
            raise ValueError("receipt sequence must be a positive integer")
        object.__setattr__(self, "forecast_fingerprint", _sha256_text(self.forecast_fingerprint, field="forecast_fingerprint"))
        _utc_iso(self.server_created_at, field="server_created_at")
        if not isinstance(self.formation_payload, dict):
            raise ValueError("formation_payload must be an object")

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "forecast_fingerprint": self.forecast_fingerprint,
            "formation_payload": self.formation_payload,
            "schema": RECEIPT_SCHEMA,
            "sequence": self.sequence,
            "server_created_at": _utc_iso(self.server_created_at, field="server_created_at"),
        }

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.canonical_payload())


def receipt_from_store_row(row: dict[str, Any]) -> TrustedFormationReceipt:
    """Parse a row returned by the trusted append RPC; no caller timestamp accepted."""
    if not isinstance(row, dict):
        raise ValueError("trusted receipt row must be an object")
    return TrustedFormationReceipt(
        sequence=row.get("sequence"),
        forecast_fingerprint=row.get("forecast_fingerprint"),
        server_created_at=_parse_utc(row.get("created_at"), field="created_at"),
        formation_payload=row.get("formation_payload"),
    )


def verify_formation_receipt(
    forecast: ForwardMoveForecast, receipt: TrustedFormationReceipt
) -> None:
    expected_record = forecast.to_record()
    if receipt.forecast_fingerprint != forecast.fingerprint:
        raise ValueError("trusted receipt fingerprint does not match forecast")
    if receipt.formation_payload != expected_record:
        raise ValueError("trusted receipt payload does not match full frozen formation")
    if receipt.server_created_at < forecast.formed_at:
        raise ValueError("trusted server receipt cannot predate declared formation")
    if receipt.server_created_at < forecast.evidence_cutoff:
        raise ValueError("trusted server receipt cannot predate evidence cutoff")


def trusted_expires_at(
    forecast: ForwardMoveForecast, receipt: TrustedFormationReceipt
) -> datetime:
    verify_formation_receipt(forecast, receipt)
    return receipt.server_created_at + timedelta(days=forecast.horizon_days)


class ForecastOutcome(str, Enum):
    HIT = "HIT"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"


@dataclass(frozen=True)
class ForwardMoveResolution:
    """Immutable outcome record linked to a trusted formation receipt."""

    forecast_fingerprint: str
    formation_receipt_fingerprint: str
    formation_receipt_sequence: int
    formation_receipt_created_at: datetime
    resolved_at: datetime
    observation_start_at: datetime
    observation_end_at: datetime
    observed_max_price: str
    first_target_hit_at: datetime | None
    invalidation_at: datetime | None
    outcome: ForecastOutcome

    def canonical_payload(self) -> dict[str, Any]:
        return {
            "first_target_hit_at": (
                _utc_iso(self.first_target_hit_at, field="first_target_hit_at")
                if self.first_target_hit_at is not None
                else None
            ),
            "forecast_fingerprint": self.forecast_fingerprint,
            "formation_receipt_created_at": _utc_iso(self.formation_receipt_created_at, field="formation_receipt_created_at"),
            "formation_receipt_fingerprint": self.formation_receipt_fingerprint,
            "formation_receipt_sequence": self.formation_receipt_sequence,
            "invalidation_at": (
                _utc_iso(self.invalidation_at, field="invalidation_at")
                if self.invalidation_at is not None
                else None
            ),
            "observation_end_at": _utc_iso(self.observation_end_at, field="observation_end_at"),
            "observation_start_at": _utc_iso(self.observation_start_at, field="observation_start_at"),
            "observed_max_price": self.observed_max_price,
            "outcome": self.outcome.value,
            "resolved_at": _utc_iso(self.resolved_at, field="resolved_at"),
            "schema": RESOLUTION_SCHEMA,
        }

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.canonical_payload())

    def to_record(self) -> dict[str, Any]:
        payload = self.canonical_payload()
        payload["resolution_fingerprint"] = self.fingerprint
        return payload


def resolve_forecast(
    forecast: ForwardMoveForecast,
    receipt: TrustedFormationReceipt,
    *,
    resolved_at: datetime,
    observation_start_at: datetime,
    observation_end_at: datetime,
    observed_max_price: str | int | float | Decimal,
    first_target_hit_at: datetime | None = None,
    invalidation_at: datetime | None = None,
) -> ForwardMoveResolution:
    """Create a final immutable resolution anchored to trusted server formation time."""

    verify_formation_receipt(forecast, receipt)
    _utc_iso(resolved_at, field="resolved_at")
    _utc_iso(observation_start_at, field="observation_start_at")
    _utc_iso(observation_end_at, field="observation_end_at")

    effective_formation = receipt.server_created_at
    effective_expiry = trusted_expires_at(forecast, receipt)
    if observation_start_at != effective_formation:
        raise ValueError("observation_start_at must equal trusted server receipt time")
    if observation_end_at < observation_start_at:
        raise ValueError("observation_end_at cannot precede observation_start_at")
    if observation_end_at > effective_expiry:
        raise ValueError("observation_end_at cannot exceed the trusted forecast horizon")
    if resolved_at < observation_end_at:
        raise ValueError("resolved_at cannot precede observation_end_at")

    max_price_text = _decimal_text(observed_max_price, field="observed_max_price")
    max_price = Decimal(max_price_text)
    target_price = forecast.target_price

    if first_target_hit_at is not None:
        _utc_iso(first_target_hit_at, field="first_target_hit_at")
        if first_target_hit_at <= effective_formation:
            raise ValueError("target hit at or before trusted formation is retroactive and cannot count")
        if first_target_hit_at > observation_end_at:
            raise ValueError("first_target_hit_at must be inside the observed window")
        if max_price < target_price:
            raise ValueError("target hit is inconsistent with observed_max_price")
    elif max_price >= target_price:
        raise ValueError("observed target breach requires a point-in-time first_target_hit_at")

    if invalidation_at is not None:
        _utc_iso(invalidation_at, field="invalidation_at")
        if invalidation_at <= effective_formation:
            raise ValueError("invalidation_at must be after trusted formation")
        if invalidation_at > observation_end_at:
            raise ValueError("invalidation_at must be inside the observed window")

    valid_hit = (
        first_target_hit_at is not None
        and first_target_hit_at <= effective_expiry
        and (invalidation_at is None or first_target_hit_at < invalidation_at)
    )
    if valid_hit:
        outcome = ForecastOutcome.HIT
    elif invalidation_at is not None and invalidation_at <= effective_expiry:
        outcome = ForecastOutcome.INVALIDATED
    elif observation_end_at == effective_expiry and resolved_at >= effective_expiry:
        outcome = ForecastOutcome.EXPIRED
    else:
        raise ValueError("forecast is still open; final resolution is premature")

    return ForwardMoveResolution(
        forecast_fingerprint=forecast.fingerprint,
        formation_receipt_fingerprint=receipt.fingerprint,
        formation_receipt_sequence=receipt.sequence,
        formation_receipt_created_at=receipt.server_created_at,
        resolved_at=resolved_at,
        observation_start_at=observation_start_at,
        observation_end_at=observation_end_at,
        observed_max_price=max_price_text,
        first_target_hit_at=first_target_hit_at,
        invalidation_at=invalidation_at,
        outcome=outcome,
    )
