import hashlib
import json
from pathlib import Path

import pytest

from big_move_primary_functional_classifier import (
    CONTRACT_ARTIFACT_ID,
    CONTRACT_GIT_BLOB_SHA,
    classify_primary_functional_document,
    load_classifier_contract,
    validate_sector_output_binding,
)


def _write(root: Path, name: str, raw: bytes):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {"artifact_relpath": name, "sha256": hashlib.sha256(raw).hexdigest()}


def _json(root: Path, name: str, value):
    return _write(root, name, json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def _input(root: Path, text: str, claim: str):
    document = _write(root, "doc.txt", text.encode())
    proof = {
        "schema": "primary_document_proof.v1",
        "source_id": "PRIMARY_CONTRACT_OR_GENESIS_DOC",
        "upstream_locator": "https://example.org/protocol-doc",
        "published_at": "2020-01-01T00:00:00Z",
        "effective_at": "2020-01-01T00:00:00Z",
        "document_relpath": document["artifact_relpath"],
        "document_sha256": document["sha256"],
        "media_type": "text/plain",
        "claim_value": claim,
    }
    proof_ref = _json(root, "proof.json", proof)
    record = {
        "schema": "primary_functional_role_input.v1",
        "source_id": "PRIMARY_CONTRACT_OR_GENESIS_DOC",
        "observed_at": "2020-01-01T00:00:00Z",
        "available_at": "2020-01-01T00:00:00Z",
        "value": claim,
        "source_proof": proof_ref,
    }
    return record, _json(root, "input.json", record)


def _sector(root: Path, input_ref, value):
    return {
        "source_id": "PIT_PRIMARY_FUNCTIONAL_CLASSIFIER_V1",
        "source_version": "v1",
        "observed_at": "2024-01-01T00:00:00Z",
        "available_at": "2024-01-01T00:00:00Z",
        "value": value,
        "derivation": {
            "transform_id": "PIT_PRIMARY_FUNCTIONAL_CLASSIFIER_V1",
            "transform_version": "1",
            "parameters": {"classifier": "functional_role", "ambiguous_policy": "exclude"},
            "inputs": [input_ref],
        },
    }


def test_classifier_contract_is_git_blob_pinned():
    contract = load_classifier_contract()
    assert contract["artifact_id"] == CONTRACT_ARTIFACT_ID
    assert len(CONTRACT_GIT_BLOB_SHA) == 40


def test_base_network_classification_is_recomputed_from_primary_text(tmp_path):
    record, input_ref = _input(
        tmp_path,
        "This protocol is a smart contract platform designed for global applications.",
        "smart contract platform",
    )
    classification = classify_primary_functional_document(
        record,
        decision_at="2024-01-01T00:00:00Z",
        artifact_root=tmp_path,
    )
    assert classification["category"] == "GENERAL_PURPOSE_BASE_NETWORK"
    result = validate_sector_output_binding(
        _sector(tmp_path, input_ref, "GENERAL_PURPOSE_BASE_NETWORK"),
        decision_at="2024-01-01T00:00:00Z",
        artifact_root=tmp_path,
    )
    assert result["status"] == "CLASSIFIED"


def test_wrong_claimed_sector_is_rejected(tmp_path):
    _, input_ref = _input(
        tmp_path,
        "A decentralized oracle network for verified external data.",
        "decentralized oracle network",
    )
    with pytest.raises(ValueError, match="does not match frozen"):
        validate_sector_output_binding(
            _sector(tmp_path, input_ref, "DEFI_MARKET_PROTOCOL"),
            decision_at="2024-01-01T00:00:00Z",
            artifact_root=tmp_path,
        )


def test_ambiguous_primary_document_fails_closed(tmp_path):
    record, _ = _input(
        tmp_path,
        "A payment network plus a smart contract platform.",
        "payment network",
    )
    with pytest.raises(ValueError, match="ambiguous"):
        classify_primary_functional_document(
            record,
            decision_at="2024-01-01T00:00:00Z",
            artifact_root=tmp_path,
        )


def test_no_frozen_category_fails_closed(tmp_path):
    record, _ = _input(tmp_path, "An experimental cryptographic system.", "experimental cryptographic system")
    with pytest.raises(ValueError, match="found no frozen category"):
        classify_primary_functional_document(
            record,
            decision_at="2024-01-01T00:00:00Z",
            artifact_root=tmp_path,
        )


def test_transform_parameter_drift_is_rejected(tmp_path):
    _, input_ref = _input(tmp_path, "A payment network for settlement.", "payment network")
    sector = _sector(tmp_path, input_ref, "MONETARY_PAYMENT_NETWORK")
    sector["derivation"]["parameters"]["ambiguous_policy"] = "pick_first"
    with pytest.raises(ValueError, match="parameters drifted"):
        validate_sector_output_binding(
            sector,
            decision_at="2024-01-01T00:00:00Z",
            artifact_root=tmp_path,
        )
