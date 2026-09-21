"""Point-in-time contract for <=90 day 2x+ forward move research.

Formation and resolution are deliberately separate immutable records.  A forecast
must be frozen before any realized outcome is attached to it; resolution can only
reference the formation fingerprint and cannot rewrite the original evidence.

This module grants no trading, promotion, or OOS-opening authority.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation
from enum import Enum
import hashlib
import json
from typing import Any, Iterable


FORMATION_SCHEMA = "forward_move_forecast.v1"
RESOLUTION_SCHEMA = "forward_move_resolution.v1"
MAX_HORIZON_DAYS = 90


def _utc_iso(value: datetime, *, field: str) -> str:
    if not isinstance(value, datetime) or value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field} must be timezone-aware")
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


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


def _fingerprint(payload: dict[str, Any]) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ForwardMoveForecast:
    """Immutable pre-outcome formation record for a 2x+ research candidate."""

    asset_id: str
    formed_at: datetime
    evidence_cutoff: datetime
    reference_price: str | int | float | Decimal
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
        formed_iso = _utc_iso(self.formed_at, field="formed_at")
        cutoff_iso = _utc_iso(self.evidence_cutoff, field="evidence_cutoff")
        if self.evidence_cutoff > self.formed_at:
            raise ValueError("evidence_cutoff cannot be after formed_at")
        if not isinstance(self.horizon_days, int) or isinstance(self.horizon_days, bool):
            raise ValueError("horizon_days must be an integer")
        if not 1 <= self.horizon_days <= MAX_HORIZON_DAYS:
            raise ValueError(f"horizon_days must be between 1 and {MAX_HORIZON_DAYS}")

        reference_price = _decimal_text(self.reference_price, field="reference_price")
        target_multiple = _decimal_text(self.target_multiple, field="target_multiple")
        if Decimal(target_multiple) < Decimal("2"):
            raise ValueError("target_multiple must be at least 2x")

        object.__setattr__(self, "asset_id", asset_id)
        object.__setattr__(self, "reference_price", reference_price)
        object.__setattr__(self, "target_multiple", target_multiple)
        object.__setattr__(self, "evidence_for", _strings(self.evidence_for, field="evidence_for", require_nonempty=True))
        object.__setattr__(self, "evidence_against", _strings(self.evidence_against, field="evidence_against"))
        object.__setattr__(self, "invalidation_rules", _strings(self.invalidation_rules, field="invalidation_rules", require_nonempty=True))
        object.__setattr__(self, "source_ids", _strings(self.source_ids, field="source_ids"))

        # Execute the timestamp normalizers during construction so malformed
        # timezone inputs fail before a formation fingerprint can exist.
        del formed_iso, cutoff_iso

    @property
    def expires_at(self) -> datetime:
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
            "formed_at": _utc_iso(self.formed_at, field="formed_at"),
            "horizon_days": self.horizon_days,
            "invalidation_rules": list(self.invalidation_rules),
            "reference_price": str(self.reference_price),
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
        payload["expires_at"] = _utc_iso(self.expires_at, field="expires_at")
        return payload


class ForecastOutcome(str, Enum):
    HIT = "HIT"
    EXPIRED = "EXPIRED"
    INVALIDATED = "INVALIDATED"


@dataclass(frozen=True)
class ForwardMoveResolution:
    """Immutable outcome record linked to a frozen formation fingerprint."""

    forecast_fingerprint: str
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
    *,
    resolved_at: datetime,
    observation_start_at: datetime,
    observation_end_at: datetime,
    observed_max_price: str | int | float | Decimal,
    first_target_hit_at: datetime | None = None,
    invalidation_at: datetime | None = None,
) -> ForwardMoveResolution:
    """Create a final immutable resolution without mutating formation evidence.

    The observation window must begin exactly at formation, so an asset that had
    already reached the target before the forecast cannot be backfilled as a hit.
    Unresolved/open observations are intentionally not represented here.
    """

    _utc_iso(resolved_at, field="resolved_at")
    _utc_iso(observation_start_at, field="observation_start_at")
    _utc_iso(observation_end_at, field="observation_end_at")

    if observation_start_at != forecast.formed_at:
        raise ValueError("observation_start_at must equal the frozen formed_at")
    if observation_end_at < observation_start_at:
        raise ValueError("observation_end_at cannot precede observation_start_at")
    if observation_end_at > forecast.expires_at:
        raise ValueError("observation_end_at cannot exceed the frozen forecast horizon")
    if resolved_at < observation_end_at:
        raise ValueError("resolved_at cannot precede observation_end_at")

    max_price_text = _decimal_text(observed_max_price, field="observed_max_price")
    max_price = Decimal(max_price_text)
    target_price = forecast.target_price

    if first_target_hit_at is not None:
        _utc_iso(first_target_hit_at, field="first_target_hit_at")
        if first_target_hit_at <= forecast.formed_at:
            raise ValueError("target hit at or before formation is retroactive and cannot count")
        if first_target_hit_at > observation_end_at:
            raise ValueError("first_target_hit_at must be inside the observed window")
        if max_price < target_price:
            raise ValueError("target hit is inconsistent with observed_max_price")
    elif max_price >= target_price:
        raise ValueError("observed target breach requires a point-in-time first_target_hit_at")

    if invalidation_at is not None:
        _utc_iso(invalidation_at, field="invalidation_at")
        if invalidation_at <= forecast.formed_at:
            raise ValueError("invalidation_at must be after formation")
        if invalidation_at > observation_end_at:
            raise ValueError("invalidation_at must be inside the observed window")

    valid_hit = (
        first_target_hit_at is not None
        and first_target_hit_at <= forecast.expires_at
        and (invalidation_at is None or first_target_hit_at < invalidation_at)
    )
    if valid_hit:
        outcome = ForecastOutcome.HIT
    elif invalidation_at is not None and invalidation_at <= forecast.expires_at:
        outcome = ForecastOutcome.INVALIDATED
    elif observation_end_at == forecast.expires_at and resolved_at >= forecast.expires_at:
        outcome = ForecastOutcome.EXPIRED
    else:
        raise ValueError("forecast is still open; final resolution is premature")

    return ForwardMoveResolution(
        forecast_fingerprint=forecast.fingerprint,
        resolved_at=resolved_at,
        observation_start_at=observation_start_at,
        observation_end_at=observation_end_at,
        observed_max_price=max_price_text,
        first_target_hit_at=first_target_hit_at,
        invalidation_at=invalidation_at,
        outcome=outcome,
    )
