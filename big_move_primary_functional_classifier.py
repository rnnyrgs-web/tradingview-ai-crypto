"""Frozen PIT functional-sector classifier for 2x Cohort 001.

Classification is computed only from the normalized visible text of one retained
primary document that is independently PIT-valid and byte-bound. The classifier uses
a Git-blob-pinned phrase taxonomy frozen before outcome labels are opened. Exactly one
coarse category must match; zero or multiple categories fail closed.

The result is a matching stratum only, never a return signal or candidate score.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import re
from typing import Any

from big_move_primary_document_binding import (
    load_retained_record,
    normalized_primary_document_text,
    validate_primary_document_literal_claim,
)

CONTRACT_PATH = "money_intelligence/2x_primary_functional_classifier_v1.json"
CONTRACT_ARTIFACT_ID = "2X-PRIMARY-FUNCTIONAL-CLASSIFIER-001-v1"
CONTRACT_GIT_BLOB_SHA = "ae68a304ae0113b676d11ae856cb079fe856a195"
TRANSFORM_ID = "PIT_PRIMARY_FUNCTIONAL_CLASSIFIER_V1"
TRANSFORM_VERSION = "1"
EXPECTED_PARAMETERS = {
    "classifier": "functional_role",
    "ambiguous_policy": "exclude",
}
PRIMARY_ROLE_SOURCE_ID = "PRIMARY_CONTRACT_OR_GENESIS_DOC"


def _git_blob_sha(raw: bytes) -> str:
    header = f"blob {len(raw)}\0".encode("ascii")
    return hashlib.sha1(header + raw, usedforsecurity=False).hexdigest()


def load_classifier_contract(repo_root: str | Path | None = None) -> dict[str, Any]:
    root = Path(repo_root) if repo_root is not None else Path(__file__).resolve().parent
    path = (root / CONTRACT_PATH).resolve()
    try:
        raw = path.read_bytes()
    except OSError as exc:
        raise ValueError("primary functional-classifier contract is unavailable") from exc
    if _git_blob_sha(raw) != CONTRACT_GIT_BLOB_SHA:
        raise ValueError("primary functional-classifier contract drifted from frozen Git blob")
    try:
        contract = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("primary functional-classifier contract is malformed") from exc
    if not isinstance(contract, dict) or contract.get("artifact_id") != CONTRACT_ARTIFACT_ID:
        raise ValueError("unexpected primary functional-classifier contract identity")
    categories = contract.get("categories")
    if not isinstance(categories, dict) or not categories:
        raise ValueError("primary functional-classifier categories missing")
    for category, phrases in categories.items():
        if not isinstance(category, str) or not category or not isinstance(phrases, list) or not phrases:
            raise ValueError("primary functional-classifier category malformed")
        if any(not isinstance(phrase, str) or not phrase.strip() for phrase in phrases):
            raise ValueError("primary functional-classifier phrase malformed")
    return contract


def _phrase_present(text: str, phrase: str) -> bool:
    normalized_phrase = " ".join(phrase.casefold().split())
    return re.search(r"(?<!\w)" + re.escape(normalized_phrase) + r"(?!\w)", text) is not None


def classify_primary_functional_document(
    input_record: dict[str, Any],
    *,
    decision_at: str,
    artifact_root: str | Path,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Return one frozen coarse category or fail closed on no/ambiguous match."""
    contract = load_classifier_contract(repo_root)
    if not isinstance(input_record, dict) or input_record.get("source_id") != PRIMARY_ROLE_SOURCE_ID:
        raise ValueError("sector classifier requires PRIMARY_CONTRACT_OR_GENESIS_DOC input")

    # Bind the input record's own declared role phrase to the document too. This stops
    # a caller from attaching an unrelated primary document while classification scans
    # its text. The category itself is computed from the whole document, not from this
    # caller-selected claim.
    validate_primary_document_literal_claim(
        input_record,
        decision_at=decision_at,
        artifact_root=artifact_root,
        repo_root=repo_root,
    )
    text = normalized_primary_document_text(
        input_record,
        decision_at=decision_at,
        artifact_root=artifact_root,
        repo_root=repo_root,
    )

    matches: dict[str, list[str]] = {}
    for category, phrases in contract["categories"].items():
        hit = [phrase for phrase in phrases if _phrase_present(text, phrase)]
        if hit:
            matches[category] = hit
    if not matches:
        raise ValueError("primary functional classifier found no frozen category")
    if len(matches) != 1:
        raise ValueError("primary functional classifier is ambiguous across frozen categories")
    category = next(iter(matches))
    return {
        "schema": "two_x_primary_functional_classification.v1",
        "status": "CLASSIFIED",
        "artifact_id": CONTRACT_ARTIFACT_ID,
        "category": category,
        "matched_phrases": matches[category],
        "authority": "MATCHING_STRATUM_ONLY_NO_RETURN_OR_FORECAST_AUTHORITY",
    }


def validate_sector_output_binding(
    sector_record: dict[str, Any],
    *,
    decision_at: str,
    artifact_root: str | Path,
    repo_root: str | Path | None = None,
) -> dict[str, Any]:
    """Recompute and compare one `sector` output from its retained primary input."""
    if not isinstance(sector_record, dict) or sector_record.get("source_id") != TRANSFORM_ID:
        raise ValueError("sector must use PIT_PRIMARY_FUNCTIONAL_CLASSIFIER_V1")
    derivation = sector_record.get("derivation")
    if not isinstance(derivation, dict):
        raise ValueError("sector derivation missing")
    if derivation.get("transform_id") != TRANSFORM_ID:
        raise ValueError("sector transform_id drifted")
    if str(derivation.get("transform_version")) != TRANSFORM_VERSION:
        raise ValueError("sector transform_version drifted")
    if derivation.get("parameters") != EXPECTED_PARAMETERS:
        raise ValueError("sector transform parameters drifted")
    inputs = derivation.get("inputs")
    if not isinstance(inputs, list) or len(inputs) != 1 or not isinstance(inputs[0], dict):
        raise ValueError("sector requires exactly one retained primary-document input")
    input_record = load_retained_record(
        inputs[0],
        artifact_root=artifact_root,
        field="sector.derivation.inputs[0]",
    )
    classification = classify_primary_functional_document(
        input_record,
        decision_at=decision_at,
        artifact_root=artifact_root,
        repo_root=repo_root,
    )
    claimed = sector_record.get("value")
    if claimed != classification["category"]:
        raise ValueError("sector output does not match frozen primary functional classification")
    return classification
