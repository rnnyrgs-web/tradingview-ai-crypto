"""Authoritative entrypoint for the frozen Cohort-001 tradability contract.

`big_move_tradability_preflight.validate_tradability_contract` remains intentionally
useful as a generic structural validator for research/testing. Structural validity is
not authority to change an already frozen economic threshold after outcomes exist.

This wrapper loads exactly the committed 2X-TRADABILITY-001-v1 bytes and verifies the
Git blob identity before returning READY_FOR_DATA. A caller cannot supply or weaken a
contract through this API. READY_FOR_DATA still means data collection only: it does
not establish historical tradability, open outcomes, form a candidate, or grant any
trading/promotion authority.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from big_move_tradability_preflight import (
    ARTIFACT_ID,
    validate_tradability_contract,
)

CANONICAL_TRADABILITY_CONTRACT_PATH = (
    "money_intelligence/2x_tradability_precommitment_v1.json"
)
CANONICAL_TRADABILITY_CONTRACT_GIT_BLOB_SHA = (
    "525b6a794e763569fbc9430f70fc725b10388b85"
)
CANONICAL_GATE_SCHEMA = "two_x_tradability_canonical_gate.v1"


def _git_blob_sha(raw: bytes) -> str:
    header = f"blob {len(raw)}\0".encode("ascii")
    return hashlib.sha1(header + raw, usedforsecurity=False).hexdigest()


def load_canonical_tradability_contract(
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parent
    path = (root / CANONICAL_TRADABILITY_CONTRACT_PATH).resolve()
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError("canonical tradability contract is unavailable") from exc
    if _git_blob_sha(raw) != CANONICAL_TRADABILITY_CONTRACT_GIT_BLOB_SHA:
        raise ValueError("canonical tradability contract drifted from frozen Git blob")
    try:
        contract = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("canonical tradability contract is malformed") from exc
    if not isinstance(contract, dict) or contract.get("artifact_id") != ARTIFACT_ID:
        raise ValueError("unexpected canonical tradability contract identity")
    return contract


def evaluate_authoritative_tradability_preflight(
    *, repo_root: str | Path | None = None
) -> dict[str, Any]:
    """Validate only the exact frozen bytes; accepts no caller contract override."""
    contract = load_canonical_tradability_contract(repo_root)
    structural = validate_tradability_contract(contract)
    if structural.get("status") != "READY_FOR_DATA":
        raise ValueError("canonical tradability contract failed structural validation")
    return {
        "schema": CANONICAL_GATE_SCHEMA,
        "artifact_id": ARTIFACT_ID,
        "canonical_contract_git_blob_sha": CANONICAL_TRADABILITY_CONTRACT_GIT_BLOB_SHA,
        "status": "READY_FOR_DATA",
        "execution_bands_usd": structural["execution_bands_usd"],
        "outcomes_opened": False,
        "strict_tradability_established": False,
        "prediction_authority": False,
        "promotion_authority": False,
        "broker_connected": False,
        "live_trading": False,
    }
