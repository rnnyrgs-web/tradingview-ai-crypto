"""Canonical, tamper-evident envelopes for research output."""

from __future__ import annotations

import hashlib
import json

from signal_development import PRIMARY_OBJECTIVE_ID, PRIMARY_MISSION
from strategy_contract import CONTRACT_SCHEMA_VERSION, StrategyContract, freeze_strategy_contract


def canonical_json(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(value) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def seal_research_payload(payload: dict, *, strategy_contract: dict | None = None) -> dict:
    bound_payload = dict(payload)
    existing = bound_payload.get("signal_development_objective")
    if existing is not None and existing != PRIMARY_OBJECTIVE_ID:
        raise RuntimeError("research payload attempted to replace primary signal-development objective")
    bound_payload["signal_development_objective"] = PRIMARY_OBJECTIVE_ID
    bound_payload["primary_signal_development_mission"] = PRIMARY_MISSION

    schema_version = 2
    if strategy_contract is not None:
        frozen = freeze_strategy_contract(strategy_contract)
        fingerprint = str(frozen["fingerprint"])
        existing_fingerprint = str(bound_payload.get("strategy_fingerprint") or "").strip()
        if existing_fingerprint and existing_fingerprint != fingerprint:
            raise RuntimeError("research payload strategy fingerprint conflicts with frozen contract")
        existing_contract = bound_payload.get("strategy_contract")
        if existing_contract is not None and existing_contract != frozen:
            raise RuntimeError("research payload attempted to replace frozen strategy contract")
        bound_payload["strategy_contract"] = frozen
        bound_payload["strategy_fingerprint"] = fingerprint
        schema_version = 3

    return {
        "schema_version": schema_version,
        "payload": bound_payload,
        "integrity": {
            "algorithm": "sha256",
            "payload_sha256": sha256_hex(bound_payload),
        },
    }


def _verify_strategy_contract_binding(payload: dict) -> bool:
    frozen = payload.get("strategy_contract")
    if not isinstance(frozen, dict):
        return False
    if frozen.get("schema_version") != CONTRACT_SCHEMA_VERSION or frozen.get("frozen") is not True:
        return False
    raw_contract = frozen.get("payload")
    if not isinstance(raw_contract, dict):
        return False
    contract = StrategyContract.from_mapping(raw_contract)
    fingerprint = contract.fingerprint()
    return bool(
        frozen.get("fingerprint") == fingerprint
        and payload.get("strategy_fingerprint") == fingerprint
    )


def verify_research_envelope(envelope: dict) -> bool:
    try:
        payload = envelope["payload"]
        schema_version = envelope["schema_version"]
        base_valid = bool(
            schema_version in {1, 2, 3}
            and envelope["integrity"]["algorithm"] == "sha256"
            and envelope["integrity"]["payload_sha256"] == sha256_hex(payload)
            and (schema_version == 1 or payload.get("signal_development_objective") == PRIMARY_OBJECTIVE_ID)
        )
        if not base_valid:
            return False
        if schema_version == 3:
            return _verify_strategy_contract_binding(payload)
        return True
    except (KeyError, TypeError, ValueError):
        return False
