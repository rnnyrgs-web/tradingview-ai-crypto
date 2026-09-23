from __future__ import annotations

import copy

import pytest

from orchestration import exact_head_review as review
from orchestration.review_scope_policy import (
    REVIEW_RECEIPT_SCHEMA_VERSION,
    REVIEW_SCOPE_POLICY_VERSION,
    changed_paths_sha256,
    classify_diff_scope,
    review_receipt_context_sha256,
    review_scope_policy_sha256,
    verify_review_scope_receipt,
)


INFRA_PATHS = [
    "orchestration/exact_head_review.py",
    "orchestration/review_scope_policy.py",
]
PR_NUMBER = 579
HEAD_SHA = "a" * 40
SCOPE = "REVIEW_INFRASTRUCTURE"


def _receipt() -> dict:
    return {
        "review_receipt_schema_version": REVIEW_RECEIPT_SCHEMA_VERSION,
        "review_scope": "READ_ONLY_EXACT_HEAD",
        "review_scope_policy_version": REVIEW_SCOPE_POLICY_VERSION,
        "review_scope_policy_sha256": review_scope_policy_sha256(),
        "changed_paths": INFRA_PATHS,
        "changed_paths_sha256": changed_paths_sha256(INFRA_PATHS),
        "diff_scope_class": SCOPE,
        "pr_number": PR_NUMBER,
        "exact_head_sha": HEAD_SHA,
        "integration_authority": "NONE",
        "review_context_sha256": review_receipt_context_sha256(
            pr_number=PR_NUMBER,
            exact_head_sha=HEAD_SHA,
            changed_paths=INFRA_PATHS,
            diff_scope_class=SCOPE,
        ),
    }


def _verify(receipt: dict) -> None:
    verify_review_scope_receipt(
        receipt,
        expected_pr_number=PR_NUMBER,
        expected_head_sha=HEAD_SHA,
        expected_changed_paths=INFRA_PATHS,
        expected_diff_scope=SCOPE,
    )


def test_review_infrastructure_scope_is_exact_allowlist_only() -> None:
    assert classify_diff_scope(
        [
            "orchestration/exact_head_review.py",
            "orchestration/review_scope_policy.py",
            "tests/test_exact_head_review.py",
            "tests/test_review_scope_policy.py",
        ]
    ) == "REVIEW_INFRASTRUCTURE"


def test_any_strategy_path_forces_general_scope() -> None:
    assert classify_diff_scope(
        [
            "orchestration/exact_head_review.py",
            "orchestration/strategy_predeclaration.py",
        ]
    ) == "GENERAL_RESEARCH_OR_CODE"


def test_empty_changed_path_set_fails_closed() -> None:
    with pytest.raises(RuntimeError, match="no changed paths"):
        classify_diff_scope([])


def test_scope_receipt_digest_and_authority_validate() -> None:
    _verify(_receipt())


def test_scope_receipt_cannot_self_authenticate_without_trusted_context() -> None:
    with pytest.raises(RuntimeError, match="trusted review context required"):
        verify_review_scope_receipt(_receipt())


def test_scope_receipt_policy_digest_tamper_fails_closed() -> None:
    receipt = copy.deepcopy(_receipt())
    receipt["review_scope_policy_sha256"] = "0" * 64
    with pytest.raises(RuntimeError, match="digest mismatch"):
        _verify(receipt)


def test_scope_receipt_unknown_version_fails_closed() -> None:
    receipt = copy.deepcopy(_receipt())
    receipt["review_scope_policy_version"] = 999
    with pytest.raises(RuntimeError, match="unknown review-scope policy version"):
        _verify(receipt)


def test_scope_receipt_boolean_version_fails_closed() -> None:
    receipt = copy.deepcopy(_receipt())
    receipt["review_scope_policy_version"] = True
    with pytest.raises(RuntimeError, match="invalid review-scope policy version"):
        _verify(receipt)


def test_legacy_unversioned_receipt_is_not_reinterpreted() -> None:
    legacy = {
        "review_scope": "READ_ONLY_EXACT_HEAD",
        "diff_scope_class": SCOPE,
        "integration_authority": "NONE",
    }
    with pytest.raises(RuntimeError, match="unsupported review receipt schema version"):
        _verify(legacy)


def test_scope_receipt_boolean_schema_version_fails_closed() -> None:
    receipt = copy.deepcopy(_receipt())
    receipt["review_receipt_schema_version"] = True
    with pytest.raises(RuntimeError, match="unsupported review receipt schema version"):
        _verify(receipt)


def test_scope_receipt_changed_path_tamper_fails_closed() -> None:
    receipt = copy.deepcopy(_receipt())
    receipt["changed_paths"].append("orchestration/strategy_predeclaration.py")
    with pytest.raises(RuntimeError, match="trusted diff|digest mismatch"):
        _verify(receipt)


def test_scope_receipt_scope_class_cannot_misrepresent_changed_paths() -> None:
    paths = ["orchestration/exact_head_review.py", "orchestration/strategy_predeclaration.py"]
    receipt = copy.deepcopy(_receipt())
    receipt["changed_paths"] = paths
    receipt["changed_paths_sha256"] = changed_paths_sha256(paths)
    receipt["diff_scope_class"] = "REVIEW_INFRASTRUCTURE"
    with pytest.raises(RuntimeError, match="trusted diff|classification mismatch"):
        _verify(receipt)


def test_scope_receipt_noncanonical_or_duplicate_paths_fail_closed() -> None:
    receipt = copy.deepcopy(_receipt())
    receipt["changed_paths"] = list(reversed(INFRA_PATHS)) + [INFRA_PATHS[0]]
    receipt["changed_paths_sha256"] = changed_paths_sha256(receipt["changed_paths"])
    with pytest.raises(RuntimeError, match="canonical and unique"):
        _verify(receipt)


def test_scope_receipt_cannot_grant_integration_authority() -> None:
    receipt = copy.deepcopy(_receipt())
    receipt["integration_authority"] = "MERGE"
    with pytest.raises(RuntimeError, match="must not grant integration authority"):
        _verify(receipt)


def test_scope_receipt_pr_or_head_replay_fails_closed() -> None:
    receipt = _receipt()
    with pytest.raises(RuntimeError, match="PR number mismatch"):
        verify_review_scope_receipt(
            receipt,
            expected_pr_number=PR_NUMBER + 1,
            expected_head_sha=HEAD_SHA,
            expected_changed_paths=INFRA_PATHS,
            expected_diff_scope=SCOPE,
        )
    with pytest.raises(RuntimeError, match="head SHA mismatch"):
        verify_review_scope_receipt(
            receipt,
            expected_pr_number=PR_NUMBER,
            expected_head_sha="b" * 40,
            expected_changed_paths=INFRA_PATHS,
            expected_diff_scope=SCOPE,
        )


def test_scope_receipt_trusted_context_digest_tamper_fails_closed() -> None:
    receipt = copy.deepcopy(_receipt())
    receipt["review_context_sha256"] = "0" * 64
    with pytest.raises(RuntimeError, match="trusted-context digest mismatch"):
        _verify(receipt)


def test_policy_digest_binds_infrastructure_allowlist() -> None:
    digest = review_scope_policy_sha256()
    assert len(digest) == 64
    int(digest, 16)
    assert digest == review_scope_policy_sha256(REVIEW_SCOPE_POLICY_VERSION)


def test_exact_head_header_embeds_phase_aware_scope_discipline() -> None:
    header = review._context_header(
        pr_number=515,
        head_sha=HEAD_SHA,
        protected_hits=["orchestration/cohorts/example.json"],
        diff_scope="GENERAL_RESEARCH_OR_CODE",
    )
    assert "DIFF_SCOPE_CLASS: GENERAL_RESEARCH_OR_CODE" in header
    assert "REVIEW_SCOPE_DISCIPLINE" in header
    assert "unavailable future-evidence category" in header
    assert "NOT_APPLICABLE_FOR_THIS_PHASE" in header
    assert "concrete machine-readable or executable controls" in header
    assert "Claims, comments, labels, or prose alone NEVER satisfy" in header
    assert "REJECT" in header
    assert "premature protected access" in header
    assert f"REVIEW_SCOPE_POLICY_VERSION: {review.REVIEW_SCOPE_DISCIPLINE_VERSION}" in header
    assert f"REVIEW_SCOPE_POLICY_SHA256: {review._review_scope_policy_sha256()}" in header


def test_context_header_requires_explicit_executable_scope() -> None:
    with pytest.raises(TypeError):
        review._context_header(
            pr_number=515,
            head_sha=HEAD_SHA,
            protected_hits=[],
        )


def test_enriched_verdict_binds_trusted_exact_context() -> None:
    enriched = review._enrich_verdict(
        {"approve": True, "reason": "bounded scope is coherent", "risk": "low"},
        pr_number=PR_NUMBER,
        head_sha=HEAD_SHA,
        protected_hits=[],
        changed_paths=INFRA_PATHS,
        diff_scope=SCOPE,
    )
    assert enriched["integration_authority"] == "NONE"
    assert enriched["review_receipt_schema_version"] == REVIEW_RECEIPT_SCHEMA_VERSION
    assert enriched["review_scope_policy_sha256"] == review_scope_policy_sha256()
    assert enriched["changed_paths_sha256"] == changed_paths_sha256(INFRA_PATHS)
    assert enriched["review_context_sha256"] == review_receipt_context_sha256(
        pr_number=PR_NUMBER,
        exact_head_sha=HEAD_SHA,
        changed_paths=INFRA_PATHS,
        diff_scope_class=SCOPE,
    )
