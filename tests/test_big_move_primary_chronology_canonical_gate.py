"""RED regression for #698: canonical primary-document chronology must be non-backdateable.

These tests intentionally exercise the canonical source-authenticity entry point, not
only the lower-level Common Crawl validator.  A caller-authored published/effective
clock plus retained bytes is not proof that those exact bytes existed by decision_at.
"""

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

import pytest

from big_move_source_authenticity import validate_record_authenticity

PRIMARY = "PRIMARY_CONTRACT_OR_GENESIS_DOC"
DERIVED = "PIT_PRIMARY_FUNCTIONAL_CLASSIFIER_V1"
DECISION = datetime(2024, 1, 1, tzinfo=timezone.utc)


def _write(root: Path, name: str, raw: bytes) -> dict[str, str]:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {"artifact_relpath": name, "sha256": hashlib.sha256(raw).hexdigest()}


def _write_json(root: Path, name: str, value) -> dict[str, str]:
    return _write(
        root,
        name,
        json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8"),
    )


def _untrusted_primary(root: Path, *, prefix: str = "primary") -> dict:
    document = _write(root, f"{prefix}/document.txt", b"immutable primary document fixture")
    proof = {
        "schema": "primary_document_proof.v1",
        "source_id": PRIMARY,
        "upstream_locator": "https://example.org/primary/document",
        # Deliberately caller-authored old clocks.  There is no trusted archive capture.
        "published_at": "2020-01-01T00:00:00Z",
        "effective_at": "2020-01-01T00:00:00Z",
        "document_relpath": document["artifact_relpath"],
        "document_sha256": document["sha256"],
        "claim_value": "L1",
    }
    proof_ref = _write_json(root, f"{prefix}/proof.json", proof)
    return {
        "source_id": PRIMARY,
        "source_version": "v1",
        "observed_at": "2020-01-01T00:00:00Z",
        "available_at": "2020-01-01T00:00:00Z",
        "value": "L1",
        "source_proof": proof_ref,
    }


def test_direct_primary_cannot_enter_canonical_gate_without_trusted_capture(tmp_path):
    record = _untrusted_primary(tmp_path)
    with pytest.raises(ValueError, match="historical|capture|trusted"):
        validate_record_authenticity(
            record,
            artifact_root=tmp_path,
            decision_at=DECISION,
            field="identity",
        )


def test_derived_primary_input_cannot_bypass_canonical_chronology_gate(tmp_path):
    primary = _untrusted_primary(tmp_path, prefix="derived-primary")
    input_ref = _write_json(tmp_path, "derived/input.json", primary)
    derived = {
        "source_id": DERIVED,
        "source_version": "v1",
        "observed_at": "2020-01-01T00:00:00Z",
        "available_at": "2020-01-01T00:00:00Z",
        "value": "L1",
        "derivation": {
            "transform_id": DERIVED,
            "transform_version": "1",
            "parameters": {"classifier": "functional_role", "ambiguous_policy": "exclude"},
            "inputs": [input_ref],
        },
    }
    with pytest.raises(ValueError, match="historical|capture|trusted"):
        validate_record_authenticity(
            derived,
            artifact_root=tmp_path,
            decision_at=DECISION,
            field="sector",
        )
