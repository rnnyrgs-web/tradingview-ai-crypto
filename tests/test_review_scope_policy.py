from __future__ import annotations

import copy

import pytest

from orchestration import exact_head_review as review
from orchestration.review_scope_policy import (
    REVIEW_RECEIPT_SCHEMA_VERSION,
    REVIEW_SCOPE_POLICY_VERSION,
    changed_paths_sha256,
    classify_diff_scope,
    protected_path_registry_identity,
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
RUNTIME_SHA = "c" * 40
SCOPE = "REVIEW_INFRASTRUCTURE"
WORKFLOW_REPOSITORY = "rnnyrgs-web/tradingview-ai-crypto"
WORKFLOW_RUN_ID = 123456789
WORKFLOW_REF = (
    "rnnyrgs-web/tradingview-ai-crypto/.github/workflows/"
    "exact_head_independent_review.yml@refs/heads/main"
)


def _receipt() -> dict:
    provenance = {
        "repository": WORKFLOW_REPOSITORY,
        "run_id": WORKFLOW_RUN_ID,
        "workflow_ref": WORKFLOW_REF,
        "runtime_git_sha": RUNTIME_SHA,
    }
    return {
        "review_receipt_schema_version": REVIEW_RECEIPT_SCHEMA_VERSION,
        "review_scope": "READ_ONLY_EXACT_HEAD",
        "review_scope_policy_version": REVIEW_SCOPE_POLICY_VERSION,
        "review_scope_policy_sha256": review_scope_policy_sha256(),
        "changed_paths": INFRA_PATHS,
        "changed_paths_sha256": changed_paths_sha256(INFRA_PATHS),
        "protected_paths": INFRA_PATHS,
        "protected_path_registry": protected_path_registry_identity(),
        "diff_scope_class": SCOPE,
        "pr_number": PR_NUMBER,
        "exact_head_sha": HEAD_SHA,
        "workflow_provenance": provenance,
        "integration_authority": "NONE",
        "review_context_sha256": review_receipt_context_sha256(
            pr_number=PR_NUMBER,
            exact_head_sha=HEAD_SHA,
            changed_paths=INFRA_PATHS,
            diff_scope_class=SCOPE,
            workflow_repository=WORKFLOW_REPOSITORY,
            workflow_run_id=WORKFLOW_RUN_ID,
            workflow_ref=WORKFLOW_REF,
            workflow_runtime_sha=RUNTIME_SHA,
        ),
    }


def _verify(receipt: dict) -> None:
    verify_review_scope_receipt(
        receipt,
        expected_pr_number=PR_NUMBER,
        expected_head_sha=HEAD_SHA,
        expected_changed_paths=INFRA_PATHS,
        expected_diff_scope=SCOPE,
        expected_workflow_repository=WORKFLOW_REPOSITORY,
        expected_workflow_run_id=WORKFLOW_RUN_ID,
        expected_workflow_ref=WORKFLOW_REF,
        expected_workflow_runtime_sha=RUNTIME_SHA,
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


def test_protected_strategy_path_forces_gate_mutation_scope() -> None:
    assert classify_diff_scope(
        [
            "orchestration/exact_head_review.py",
            "orchestration/strategy_predeclaration.py",
        ]
    ) == "PROTECTED_SCIENTIFIC_GATE_MUTATION"


def test_unprotected_research_path_remains_general_scope() -> None:
    assert classify_diff_scope(
        ["research_notes/outcome_blind_hypothesis.md"]
    ) == "GENERAL_RESEARCH_OR_CODE"


def test_empty_changed_path_set_fails_closed() -> None:
    with pytest.raises(RuntimeError, match="no changed paths"):
        classify_diff_scope([])


def test_scope_receipt_digest_and_authority_validate() -> None:
    _verify(_receipt())


def test_scope_receipt_cannot_self_authenticate_without_trusted_context() -> None:
    with pytest.raises(RuntimeError, match="trusted review context"):
        verify_review_scope_receipt(_receipt())


def test_scope_receipt_policy_digest_tamper_fails_closed() -> None:
    receipt = copy.deepcopy(_receipt())
    receipt["review_scope_policy_sha256"] = "0" * 64
    with pytest.raises(RuntimeError, match="digest mismatch"):
        _verify(receipt)


def test_scope_receipt_unknown_version_fails_closed() -> None:
    receipt = copy.deepcopy(_receipt())
    receipt["review_scope_policy_version"] = 999
    with pytest.raises(RuntimeError, match="stale review-scope policy version"):
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
    receipt["protected_paths"] = paths
    receipt["diff_scope_class"] = "REVIEW_INFRASTRUCTURE"
    with pytest.raises(RuntimeError, match="trusted diff|classification mismatch"):
        _verify(receipt)


def test_scope_receipt_noncanonical_or_duplicate_paths_fail_closed() -> None:
    receipt = copy.deepcopy(_receipt())
    receipt["changed_paths"] = list(reversed(INFRA_PATHS)) + [INFRA_PATHS[0]]
    receipt["changed_paths_sha256"] = changed_paths_sha256(receipt["changed_paths"])
    with pytest.raises(RuntimeError, match="canonical and unique"):
        _verify(receipt)


def test_scope_receipt_protected_path_context_tamper_fails_closed() -> None:
    receipt = copy.deepcopy(_receipt())
    receipt["protected_paths"] = []
    with pytest.raises(RuntimeError, match="protected-path context mismatch"):
        _verify(receipt)


def test_scope_receipt_registry_identity_tamper_fails_closed() -> None:
    receipt = copy.deepcopy(_receipt())
    receipt["protected_path_registry"]["sha256"] = "0" * 64
    with pytest.raises(RuntimeError, match="registry identity mismatch"):
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
            expected_workflow_repository=WORKFLOW_REPOSITORY,
            expected_workflow_run_id=WORKFLOW_RUN_ID,
            expected_workflow_ref=WORKFLOW_REF,
            expected_workflow_runtime_sha=RUNTIME_SHA,
        )
    with pytest.raises(RuntimeError, match="head SHA mismatch"):
        verify_review_scope_receipt(
            receipt,
            expected_pr_number=PR_NUMBER,
            expected_head_sha="b" * 40,
            expected_changed_paths=INFRA_PATHS,
            expected_diff_scope=SCOPE,
            expected_workflow_repository=WORKFLOW_REPOSITORY,
            expected_workflow_run_id=WORKFLOW_RUN_ID,
            expected_workflow_ref=WORKFLOW_REF,
            expected_workflow_runtime_sha=RUNTIME_SHA,
        )


def test_scope_receipt_workflow_provenance_replay_fails_closed() -> None:
    receipt = _receipt()
    with pytest.raises(RuntimeError, match="workflow provenance mismatch"):
        verify_review_scope_receipt(
            receipt,
            expected_pr_number=PR_NUMBER,
            expected_head_sha=HEAD_SHA,
            expected_changed_paths=INFRA_PATHS,
            expected_diff_scope=SCOPE,
            expected_workflow_repository=WORKFLOW_REPOSITORY,
            expected_workflow_run_id=WORKFLOW_RUN_ID + 1,
            expected_workflow_ref=WORKFLOW_REF,
            expected_workflow_runtime_sha=RUNTIME_SHA,
        )


def test_scope_receipt_runtime_sha_replay_fails_closed() -> None:
    receipt = _receipt()
    with pytest.raises(RuntimeError, match="workflow provenance mismatch"):
        verify_review_scope_receipt(
            receipt,
            expected_pr_number=PR_NUMBER,
            expected_head_sha=HEAD_SHA,
            expected_changed_paths=INFRA_PATHS,
            expected_diff_scope=SCOPE,
            expected_workflow_repository=WORKFLOW_REPOSITORY,
            expected_workflow_run_id=WORKFLOW_RUN_ID,
            expected_workflow_ref=WORKFLOW_REF,
            expected_workflow_runtime_sha="d" * 40,
        )


def test_scope_receipt_trusted_context_digest_tamper_fails_closed() -> None:
    receipt = copy.deepcopy(_receipt())
    receipt["review_context_sha256"] = "0" * 64
    with pytest.raises(RuntimeError, match="trusted-context digest mismatch"):
        _verify(receipt)


def test_policy_digest_binds_lineage_and_registry_identity() -> None:
    current = review_scope_policy_sha256()
    prior = review_scope_policy_sha256(5)
    assert len(current) == 64
    assert len(prior) == 64
    int(current, 16)
    int(prior, 16)
    assert current != prior
    identity = protected_path_registry_identity()
    assert identity == {
        "version": 1,
        "sha256": "00e9f1a404d1f5b92210f0c172295cd0067ff1078c33e4dcb284a4e3be4c7f25",
    }


def test_exact_head_header_embeds_phase_aware_scope_and_provenance() -> None:
    provenance = {
        "repository": WORKFLOW_REPOSITORY,
        "run_id": WORKFLOW_RUN_ID,
        "workflow_ref": WORKFLOW_REF,
        "runtime_git_sha": RUNTIME_SHA,
    }
    header = review._context_header(
        pr_number=515,
        head_sha=HEAD_SHA,
        protected_hits=["orchestration/cohorts/example.json"],
        diff_scope="PROTECTED_SCIENTIFIC_GATE_MUTATION",
        workflow_provenance=provenance,
    )
    assert "DIFF_SCOPE_CLASS: PROTECTED_SCIENTIFIC_GATE_MUTATION" in header
    assert "REVIEW_SCOPE_DISCIPLINE" in header
    assert "may not be waved away as future evidence" in header
    assert "NOT_APPLICABLE_FOR_THIS_PHASE" in header
    assert "concrete machine-readable or executable controls" in header
    assert "Claims, comments, labels, or prose alone NEVER establish" in header
    assert "offline JSON" in header
    assert f"WORKFLOW_RUN_ID: {WORKFLOW_RUN_ID}" in header
    assert f"WORKFLOW_RUNTIME_GIT_SHA: {RUNTIME_SHA}" in header
    assert "PROTECTED_PATH_REGISTRY_SHA256:" in header
    assert f"REVIEW_SCOPE_POLICY_VERSION: {review.REVIEW_SCOPE_DISCIPLINE_VERSION}" in header
    assert f"REVIEW_SCOPE_POLICY_SHA256: {review._review_scope_policy_sha256()}" in header


def test_context_header_requires_explicit_executable_scope_and_provenance() -> None:
    with pytest.raises(TypeError):
        review._context_header(
            pr_number=515,
            head_sha=HEAD_SHA,
            protected_hits=[],
        )


def test_enriched_verdict_binds_trusted_exact_context_and_workflow() -> None:
    provenance = {
        "repository": WORKFLOW_REPOSITORY,
        "run_id": WORKFLOW_RUN_ID,
        "workflow_ref": WORKFLOW_REF,
        "runtime_git_sha": RUNTIME_SHA,
    }
    enriched = review._enrich_verdict(
        {"approve": True, "reason": "bounded scope is coherent", "risk": "low"},
        pr_number=PR_NUMBER,
        head_sha=HEAD_SHA,
        protected_hits=INFRA_PATHS,
        changed_paths=INFRA_PATHS,
        diff_scope=SCOPE,
        workflow_provenance=provenance,
    )
    assert enriched["integration_authority"] == "NONE"
    assert enriched["review_receipt_schema_version"] == REVIEW_RECEIPT_SCHEMA_VERSION
    assert enriched["review_scope_policy_sha256"] == review_scope_policy_sha256()
    assert enriched["changed_paths_sha256"] == changed_paths_sha256(INFRA_PATHS)
    assert enriched["protected_paths"] == INFRA_PATHS
    assert enriched["protected_path_registry"] == protected_path_registry_identity()
    assert enriched["workflow_provenance"] == provenance
    assert enriched["review_context_sha256"] == review_receipt_context_sha256(
        pr_number=PR_NUMBER,
        exact_head_sha=HEAD_SHA,
        changed_paths=INFRA_PATHS,
        diff_scope_class=SCOPE,
        workflow_repository=WORKFLOW_REPOSITORY,
        workflow_run_id=WORKFLOW_RUN_ID,
        workflow_ref=WORKFLOW_REF,
        workflow_runtime_sha=RUNTIME_SHA,
    )
