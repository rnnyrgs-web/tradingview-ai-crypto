import hashlib
import json
from pathlib import Path

import pytest

from big_move_primary_document_binding import (
    CONTRACT_ARTIFACT_ID,
    CONTRACT_GIT_BLOB_SHA,
    load_primary_claim_contract,
    validate_primary_document_literal_claim,
)


def _write(root: Path, name: str, raw: bytes):
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return {"artifact_relpath": name, "sha256": hashlib.sha256(raw).hexdigest()}


def _json(root: Path, name: str, value):
    return _write(root, name, json.dumps(value, sort_keys=True, separators=(",", ":")).encode())


def _record(root: Path, *, value="Bitcoin", document=b"Bitcoin is peer-to-peer electronic cash.", media_type="text/plain"):
    doc = _write(root, "doc/source.txt", document)
    proof = {
        "schema": "primary_document_proof.v1",
        "source_id": "PRIMARY_CONTRACT_OR_GENESIS_DOC",
        "upstream_locator": "https://example.org/original-document",
        "published_at": "2020-01-01T00:00:00Z",
        "effective_at": "2020-01-01T00:00:00Z",
        "document_relpath": doc["artifact_relpath"],
        "document_sha256": doc["sha256"],
        "media_type": media_type,
        # This legacy field is deliberately not trusted by the new binder.
        "claim_value": "caller-can-write-anything-here",
    }
    proof_ref = _json(root, "proof.json", proof)
    return {
        "source_id": "PRIMARY_CONTRACT_OR_GENESIS_DOC",
        "source_version": "v1",
        "observed_at": "2020-01-01T00:00:00Z",
        "available_at": "2020-01-01T00:00:00Z",
        "value": value,
        "source_proof": proof_ref,
    }, proof_ref


def test_primary_claim_contract_is_git_blob_pinned():
    contract = load_primary_claim_contract()
    assert contract["artifact_id"] == CONTRACT_ARTIFACT_ID
    assert len(CONTRACT_GIT_BLOB_SHA) == 40


def test_literal_claim_is_reproduced_from_retained_plain_text(tmp_path):
    record, _ = _record(tmp_path)
    result = validate_primary_document_literal_claim(
        record,
        decision_at="2024-01-01T00:00:00Z",
        artifact_root=tmp_path,
    )
    assert result["status"] == "BOUND"
    assert result["claim"] == "bitcoin"
    assert result["literal_occurrences"] == 1
    assert result["authority"] == "EVIDENCE_ONLY_NO_SEMANTIC_OR_OUTCOME_AUTHORITY"


def test_self_asserted_claim_value_cannot_substitute_for_document_bytes(tmp_path):
    record, _ = _record(tmp_path, value="Ethereum")
    with pytest.raises(ValueError, match="claim is not present"):
        validate_primary_document_literal_claim(
            record,
            decision_at="2024-01-01T00:00:00Z",
            artifact_root=tmp_path,
        )


def test_html_visible_text_is_allowed_but_script_text_is_not_evidence(tmp_path):
    visible, _ = _record(
        tmp_path,
        value="Layer 1",
        document=b"<html><body><h1>Layer 1 network</h1><script>fake secret claim</script></body></html>",
        media_type="text/html",
    )
    assert validate_primary_document_literal_claim(
        visible,
        decision_at="2024-01-01T00:00:00Z",
        artifact_root=tmp_path,
    )["status"] == "BOUND"

    hidden, _ = _record(
        tmp_path,
        value="fake secret claim",
        document=b"<html><body>ordinary visible text<script>fake secret claim</script></body></html>",
        media_type="text/html",
    )
    with pytest.raises(ValueError, match="claim is not present"):
        validate_primary_document_literal_claim(
            hidden,
            decision_at="2024-01-01T00:00:00Z",
            artifact_root=tmp_path,
        )


def test_binary_or_unfrozen_media_type_fails_closed(tmp_path):
    record, _ = _record(tmp_path, document=b"Bitcoin", media_type="application/pdf")
    with pytest.raises(ValueError, match="media_type is unsupported"):
        validate_primary_document_literal_claim(
            record,
            decision_at="2024-01-01T00:00:00Z",
            artifact_root=tmp_path,
        )


def test_post_decision_publication_cannot_be_backdated_by_record_metadata(tmp_path):
    record, proof_ref = _record(tmp_path)
    proof_path = tmp_path / proof_ref["artifact_relpath"]
    proof = json.loads(proof_path.read_text())
    proof["published_at"] = "2025-01-01T00:00:00Z"
    raw = json.dumps(proof, sort_keys=True, separators=(",", ":")).encode()
    proof_path.write_bytes(raw)
    record["source_proof"] = {
        "artifact_relpath": proof_ref["artifact_relpath"],
        "sha256": hashlib.sha256(raw).hexdigest(),
    }
    with pytest.raises(ValueError, match="not published/effective"):
        validate_primary_document_literal_claim(
            record,
            decision_at="2024-01-01T00:00:00Z",
            artifact_root=tmp_path,
        )
