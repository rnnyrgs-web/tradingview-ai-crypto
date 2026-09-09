"""Canonical, tamper-evident envelopes for research output."""

from __future__ import annotations

import hashlib
import json

from signal_development import PRIMARY_OBJECTIVE_ID, PRIMARY_MISSION


def canonical_json(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(value) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def seal_research_payload(payload: dict) -> dict:
    bound_payload = dict(payload)
    existing = bound_payload.get("signal_development_objective")
    if existing is not None and existing != PRIMARY_OBJECTIVE_ID:
        raise RuntimeError("research payload attempted to replace primary signal-development objective")
    bound_payload["signal_development_objective"] = PRIMARY_OBJECTIVE_ID
    bound_payload["primary_signal_development_mission"] = PRIMARY_MISSION
    return {
        "schema_version": 2,
        "payload": bound_payload,
        "integrity": {
            "algorithm": "sha256",
            "payload_sha256": sha256_hex(bound_payload),
        },
    }


def verify_research_envelope(envelope: dict) -> bool:
    try:
        payload = envelope["payload"]
        return (
            envelope["schema_version"] in {1, 2}
            and envelope["integrity"]["algorithm"] == "sha256"
            and envelope["integrity"]["payload_sha256"] == sha256_hex(payload)
            and (envelope["schema_version"] == 1 or payload.get("signal_development_objective") == PRIMARY_OBJECTIVE_ID)
        )
    except (KeyError, TypeError):
        return False
