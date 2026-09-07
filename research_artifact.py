"""Canonical, tamper-evident envelopes for research output."""

from __future__ import annotations

import hashlib
import json


def canonical_json(value) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_hex(value) -> str:
    return hashlib.sha256(canonical_json(value)).hexdigest()


def seal_research_payload(payload: dict) -> dict:
    return {
        "schema_version": 1,
        "payload": payload,
        "integrity": {
            "algorithm": "sha256",
            "payload_sha256": sha256_hex(payload),
        },
    }


def verify_research_envelope(envelope: dict) -> bool:
    try:
        return (
            envelope["schema_version"] == 1
            and envelope["integrity"]["algorithm"] == "sha256"
            and envelope["integrity"]["payload_sha256"] == sha256_hex(envelope["payload"])
        )
    except (KeyError, TypeError):
        return False
