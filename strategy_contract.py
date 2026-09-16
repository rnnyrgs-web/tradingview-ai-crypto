"""Immutable, dataset-bound strategy contracts for scientific validation."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import hashlib
import json
from typing import Any


CONTRACT_SCHEMA_VERSION = 1
REQUIRED_FIELDS = (
    "strategy_family",
    "strategy_version",
    "features",
    "universe",
    "universe_selection_rules",
    "entry_rules",
    "exit_rules",
    "stop_rules",
    "position_sizing",
    "holding_logic",
    "timeframes",
    "horizon",
    "costs",
    "train_range",
    "validation_range",
    "untouched_oos_range",
    "git_sha",
    "research_code_sha256",
    "dataset_id",
    "dataset_sha256",
    "hypothesis_id",
    "experiment_id",
)
DICT_FIELDS = (
    "features",
    "universe_selection_rules",
    "entry_rules",
    "exit_rules",
    "stop_rules",
    "position_sizing",
    "holding_logic",
    "costs",
)
LIST_FIELDS = ("universe", "timeframes")
NON_EMPTY_TEXT_FIELDS = (
    "strategy_family",
    "strategy_version",
    "horizon",
    "git_sha",
    "research_code_sha256",
    "dataset_id",
    "dataset_sha256",
    "hypothesis_id",
    "experiment_id",
)
RANGE_FIELDS = ("train_range", "validation_range", "untouched_oos_range")


def _canonical_json(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")


def _normalized_mapping(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("strategy contract must be an object")
    missing = [field for field in REQUIRED_FIELDS if field not in payload]
    if missing:
        raise ValueError(f"strategy contract missing required fields: {missing}")

    normalized = deepcopy({field: payload[field] for field in REQUIRED_FIELDS})
    for field in NON_EMPTY_TEXT_FIELDS:
        value = str(normalized.get(field) or "").strip()
        if not value:
            raise ValueError(f"strategy contract field {field} must be non-empty")
        normalized[field] = value

    for field in DICT_FIELDS:
        if not isinstance(normalized.get(field), dict):
            raise ValueError(f"strategy contract field {field} must be an object")

    for field in LIST_FIELDS:
        value = normalized.get(field)
        if not isinstance(value, list) or not value:
            raise ValueError(f"strategy contract field {field} must be a non-empty list")

    for field in RANGE_FIELDS:
        value = normalized.get(field)
        if not isinstance(value, list) or len(value) != 2 or not all(str(part or "").strip() for part in value):
            raise ValueError(f"strategy contract field {field} must contain start and end values")

    return normalized


@dataclass(frozen=True)
class StrategyContract:
    """Validated immutable material used to identify one research strategy."""

    payload: dict[str, Any]

    @classmethod
    def from_mapping(cls, payload: dict[str, Any]) -> "StrategyContract":
        return cls(payload=_normalized_mapping(payload))

    def canonical_payload(self) -> dict[str, Any]:
        return deepcopy(self.payload)

    def fingerprint(self) -> str:
        return hashlib.sha256(_canonical_json(self.payload)).hexdigest()


def freeze_strategy_contract(payload: dict[str, Any]) -> dict[str, Any]:
    contract = StrategyContract.from_mapping(payload)
    return {
        "schema_version": CONTRACT_SCHEMA_VERSION,
        "frozen": True,
        "payload": contract.canonical_payload(),
        "fingerprint": contract.fingerprint(),
    }


def assert_contract_unchanged(frozen: dict[str, Any], proposed: dict[str, Any]) -> None:
    if not isinstance(frozen, dict) or frozen.get("frozen") is not True:
        raise RuntimeError("immutable strategy contract is not frozen")
    if frozen.get("schema_version") != CONTRACT_SCHEMA_VERSION:
        raise RuntimeError("unsupported immutable strategy contract schema")

    frozen_contract = StrategyContract.from_mapping(frozen.get("payload") or {})
    frozen_fingerprint = frozen_contract.fingerprint()
    if frozen.get("fingerprint") != frozen_fingerprint:
        raise RuntimeError("immutable strategy contract seal is invalid")

    proposed_fingerprint = StrategyContract.from_mapping(proposed).fingerprint()
    if proposed_fingerprint != frozen_fingerprint:
        raise RuntimeError("immutable strategy contract changed")
