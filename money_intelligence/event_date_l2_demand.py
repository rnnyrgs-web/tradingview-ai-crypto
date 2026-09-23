"""Deterministic event-date L2 demand planning for the 90-day 2x research lane.

This module does not acquire market data and does not classify a historical case as
tradable.  It converts an already-authorized survivor-safe historical event/control
handoff into the smallest set of overlapping event-date L2 requests needed by the
frozen #519/#643 tradability consumer.

Scientific authority is intentionally narrow:
- no outcome inference or label opening;
- no proxy depth from OHLCV/ADV/quote volume;
- no provider purchase or dispatch;
- no candidate/model/broker/trading authority;
- missing cohort input is a blocker, not permission to synthesize cases.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import re
from typing import Any, Iterable

CONTRACT_ID = "2X-EVENT-DATE-L2-DEMAND-001-v1"
INPUT_SCHEMA = "2X-HISTORICAL-EVENT-CONTROL-L2-HANDOFF-001-v1"
OUTPUT_SCHEMA = "2X-EVENT-DATE-L2-DEMAND-MANIFEST-001-v1"
PROVIDER_CONTRACT = "TARDIS_BINANCE_SPOT_INCREMENTAL_BOOK_L2"
VENUE = "BINANCE_SPOT"
CHRONOLOGY_CONTRACT = "CROSSING_EXECUTION_INTERVAL_INTERSECTION_V1"
ALLOWED_ROLES = {"EVENT", "MATCHED_CONTROL"}
ALLOWED_BANDS = (1_000, 10_000, 50_000, 100_000)
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
SYMBOL_RE = re.compile(r"^[A-Z0-9]{3,24}USDT$")


class DemandManifestError(ValueError):
    """Raised when a handoff cannot safely produce an L2 demand manifest."""


def _parse_utc(value: Any, *, field: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise DemandManifestError(f"{field} must be a non-empty RFC3339 UTC timestamp")
    text = value.strip()
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError as exc:
        raise DemandManifestError(f"{field} must be valid RFC3339") from exc
    if parsed.tzinfo is None or parsed.utcoffset() != timezone.utc.utcoffset(parsed):
        raise DemandManifestError(f"{field} must be UTC")
    return parsed.astimezone(timezone.utc)


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _sha256_json(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _require_exact_keys(record: dict[str, Any], *, required: set[str], optional: set[str], where: str) -> None:
    missing = required - set(record)
    extra = set(record) - required - optional
    if missing:
        raise DemandManifestError(f"{where} missing required keys: {sorted(missing)}")
    if extra:
        raise DemandManifestError(f"{where} contains undeclared keys: {sorted(extra)}")


def _bands(value: Any) -> tuple[int, ...]:
    if not isinstance(value, list) or not value:
        raise DemandManifestError("required_notional_bands_usd must be a non-empty list")
    if any(isinstance(item, bool) or not isinstance(item, int) for item in value):
        raise DemandManifestError("required_notional_bands_usd must contain integers")
    bands = tuple(sorted(set(value)))
    if any(item not in ALLOWED_BANDS for item in bands):
        raise DemandManifestError(f"unsupported notional band; allowed={list(ALLOWED_BANDS)}")
    return bands


@dataclass(frozen=True)
class L2CaseDemand:
    case_id: str
    role: str
    canonical_asset_id: str
    venue: str
    instrument: str
    window_start: datetime
    window_end: datetime
    required_notional_bands_usd: tuple[int, ...]
    chronology_contract: str
    strict_l2_reason: str

    @classmethod
    def from_json(cls, value: Any) -> "L2CaseDemand":
        if not isinstance(value, dict):
            raise DemandManifestError("each case must be an object")
        _require_exact_keys(
            value,
            required={
                "case_id",
                "role",
                "canonical_asset_id",
                "venue",
                "instrument",
                "window_start",
                "window_end",
                "required_notional_bands_usd",
                "chronology_contract",
                "strict_l2_required",
                "strict_l2_reason",
                "tradability_state",
            },
            optional=set(),
            where="case",
        )
        for field in ("case_id", "canonical_asset_id", "chronology_contract", "strict_l2_reason"):
            if not isinstance(value[field], str) or not value[field].strip():
                raise DemandManifestError(f"{field} must be a non-empty string")
        if value["role"] not in ALLOWED_ROLES:
            raise DemandManifestError(f"role must be one of {sorted(ALLOWED_ROLES)}")
        if value["venue"] != VENUE:
            raise DemandManifestError(f"venue must be {VENUE}")
        if not isinstance(value["instrument"], str) or SYMBOL_RE.fullmatch(value["instrument"]) is None:
            raise DemandManifestError("instrument must be an uppercase Binance USDT spot symbol")
        if value["chronology_contract"] != CHRONOLOGY_CONTRACT:
            raise DemandManifestError(f"chronology_contract must be {CHRONOLOGY_CONTRACT}")
        if value["strict_l2_required"] is not True:
            raise DemandManifestError("only cases explicitly requiring strict L2 may enter the demand manifest")
        if value["tradability_state"] != "UNKNOWN_TRADABILITY":
            raise DemandManifestError("input case must remain UNKNOWN_TRADABILITY before event-date L2 evidence")
        start = _parse_utc(value["window_start"], field="window_start")
        end = _parse_utc(value["window_end"], field="window_end")
        if end <= start:
            raise DemandManifestError("window_end must be later than window_start")
        return cls(
            case_id=value["case_id"].strip(),
            role=value["role"],
            canonical_asset_id=value["canonical_asset_id"].strip(),
            venue=value["venue"],
            instrument=value["instrument"],
            window_start=start,
            window_end=end,
            required_notional_bands_usd=_bands(value["required_notional_bands_usd"]),
            chronology_contract=value["chronology_contract"].strip(),
            strict_l2_reason=value["strict_l2_reason"].strip(),
        )


@dataclass
class _MergedDemand:
    instrument: str
    canonical_asset_id: str
    chronology_contract: str
    start: datetime
    end: datetime
    bands: set[int]
    case_ids: set[str]
    roles: set[str]
    reasons: set[str]

    def accepts(self, case: L2CaseDemand) -> bool:
        return (
            self.instrument == case.instrument
            and self.canonical_asset_id == case.canonical_asset_id
            and self.chronology_contract == case.chronology_contract
            and case.window_start <= self.end
            and case.window_end >= self.start
        )

    def add(self, case: L2CaseDemand) -> None:
        self.start = min(self.start, case.window_start)
        self.end = max(self.end, case.window_end)
        self.bands.update(case.required_notional_bands_usd)
        self.case_ids.add(case.case_id)
        self.roles.add(case.role)
        self.reasons.add(case.strict_l2_reason)


def _merge_cases(cases: Iterable[L2CaseDemand]) -> list[_MergedDemand]:
    ordered = sorted(
        cases,
        key=lambda item: (
            item.instrument,
            item.canonical_asset_id,
            item.chronology_contract,
            item.window_start,
            item.window_end,
            item.case_id,
        ),
    )
    merged: list[_MergedDemand] = []
    for case in ordered:
        target = next((item for item in reversed(merged) if item.accepts(case)), None)
        if target is None:
            merged.append(
                _MergedDemand(
                    instrument=case.instrument,
                    canonical_asset_id=case.canonical_asset_id,
                    chronology_contract=case.chronology_contract,
                    start=case.window_start,
                    end=case.window_end,
                    bands=set(case.required_notional_bands_usd),
                    case_ids={case.case_id},
                    roles={case.role},
                    reasons={case.strict_l2_reason},
                )
            )
        else:
            target.add(case)
    return merged


def build_demand_manifest(handoff: dict[str, Any]) -> dict[str, Any]:
    """Build a deterministic, no-purchase L2 demand manifest from a trusted handoff."""

    if not isinstance(handoff, dict):
        raise DemandManifestError("handoff must be an object")
    _require_exact_keys(
        handoff,
        required={"schema_version", "cohort_id", "dataset_fingerprint", "authority", "cases"},
        optional=set(),
        where="handoff",
    )
    if handoff["schema_version"] != INPUT_SCHEMA:
        raise DemandManifestError(f"unsupported handoff schema: {handoff['schema_version']!r}")
    if handoff["authority"] != "HISTORICAL_EVENT_CONTROL_ONLY":
        raise DemandManifestError("handoff authority must be HISTORICAL_EVENT_CONTROL_ONLY")
    if not isinstance(handoff["cohort_id"], str) or not handoff["cohort_id"].strip():
        raise DemandManifestError("cohort_id must be a non-empty string")
    if not isinstance(handoff["dataset_fingerprint"], str) or SHA256_RE.fullmatch(handoff["dataset_fingerprint"]) is None:
        raise DemandManifestError("dataset_fingerprint must be lowercase SHA-256")
    if not isinstance(handoff["cases"], list):
        raise DemandManifestError("cases must be a list")

    cases = [L2CaseDemand.from_json(item) for item in handoff["cases"]]
    ids = [case.case_id for case in cases]
    if len(ids) != len(set(ids)):
        raise DemandManifestError("case_id values must be unique")

    instrument_assets: dict[str, str] = {}
    for case in cases:
        prior_asset = instrument_assets.setdefault(case.instrument, case.canonical_asset_id)
        if prior_asset != case.canonical_asset_id:
            raise DemandManifestError(
                "one Binance instrument cannot be bound to multiple canonical_asset_id values"
            )

    merged = _merge_cases(cases)
    requests: list[dict[str, Any]] = []
    for item in merged:
        request_payload = {
            "provider_contract": PROVIDER_CONTRACT,
            "venue": VENUE,
            "instrument": item.instrument,
            "canonical_asset_id": item.canonical_asset_id,
            "window_start": _iso(item.start),
            "window_end": _iso(item.end),
            "required_notional_bands_usd": sorted(item.bands),
            "chronology_contract": item.chronology_contract,
            "source_case_ids": sorted(item.case_ids),
            "source_roles": sorted(item.roles),
            "strict_l2_reasons": sorted(item.reasons),
            "tradability_state_before_acquisition": "UNKNOWN_TRADABILITY",
            "purchase_authority": "NONE",
        }
        request_payload["demand_fingerprint"] = _sha256_json(request_payload)
        requests.append(request_payload)

    requests.sort(
        key=lambda item: (
            item["instrument"],
            item["canonical_asset_id"],
            item["window_start"],
            item["window_end"],
            item["demand_fingerprint"],
        )
    )
    total_source_cases = len(cases)
    status = "NO_L2_DEMAND" if not requests else "USER_APPROVAL_REQUIRED_FOR_ANY_NONZERO_PAID_ACQUISITION"
    manifest = {
        "schema_version": OUTPUT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "source_handoff_schema": INPUT_SCHEMA,
        "source_cohort_id": handoff["cohort_id"],
        "source_dataset_fingerprint": handoff["dataset_fingerprint"],
        "provider_contract": PROVIDER_CONTRACT,
        "chronology_contract": CHRONOLOGY_CONTRACT,
        "status": status,
        "source_case_count": total_source_cases,
        "deduplicated_request_count": len(requests),
        "requests": requests,
        "cost_quote": "NOT_OBTAINED_NO_PURCHASE_OR_PLAN_SELECTION",
        "purchase_authority": "NONE",
        "label_authority": "NONE",
        "candidate_authority": "NONE",
        "model_authority": "NONE",
        "broker_trading_authority": "NONE",
    }
    manifest["manifest_fingerprint"] = _sha256_json(manifest)
    return manifest


def blocked_manifest(*, reason: str, main_sha: str) -> dict[str, Any]:
    """Return a durable fail-closed blocker when the trusted cohort handoff is absent."""

    if not isinstance(reason, str) or not reason.strip():
        raise DemandManifestError("reason must be non-empty")
    if not isinstance(main_sha, str) or len(main_sha) != 40 or any(ch not in "0123456789abcdef" for ch in main_sha):
        raise DemandManifestError("main_sha must be a lowercase 40-character SHA")
    value = {
        "schema_version": OUTPUT_SCHEMA,
        "contract_id": CONTRACT_ID,
        "status": "BLOCKED_INPUT_COHORT_NOT_POPULATED",
        "blocker": reason.strip(),
        "canonical_main_sha": main_sha,
        "source_case_count": 0,
        "deduplicated_request_count": 0,
        "requests": [],
        "purchase_authority": "NONE",
        "label_authority": "NONE",
        "candidate_authority": "NONE",
        "model_authority": "NONE",
        "broker_trading_authority": "NONE",
    }
    value["manifest_fingerprint"] = _sha256_json(value)
    return value
