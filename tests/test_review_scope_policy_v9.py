from orchestration.review_scope_policy import (
    REVIEW_SCOPE_DISCIPLINE,
    REVIEW_SCOPE_POLICY_VERSION,
    review_scope_policy_sha256,
)
from orchestration.reviewer_trust_root import reviewer_trust_root_identity


def test_v9_is_append_only_successor_to_frozen_v8_policy() -> None:
    assert REVIEW_SCOPE_POLICY_VERSION == 9
    current = review_scope_policy_sha256()
    v8 = review_scope_policy_sha256(8)
    v7 = review_scope_policy_sha256(7)
    assert len({current, v8, v7}) == 3
    assert all(len(value) == 64 for value in (current, v8, v7))
    assert "REVIEW_QUEUE_V9" in REVIEW_SCOPE_DISCIPLINE
    assert "OPEN DRAFT pull request" in REVIEW_SCOPE_DISCIPLINE
    assert "must never mark the candidate ready, merge it, or grant integration authority" in REVIEW_SCOPE_DISCIPLINE


def test_v9_binds_the_draft_safe_workflow_trust_root() -> None:
    assert reviewer_trust_root_identity() == {
        "schema_version": 2,
        "trust_boundary_id": "EXACT_HEAD_REVIEW_TRUST_ROOT_V2",
        "sha256": "5cf45d9cd44a8728ecd894fcfc1d79d9f43c0dfb24a579ed688dc5f800ec86dc",
    }
