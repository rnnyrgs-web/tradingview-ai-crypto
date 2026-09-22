from pathlib import Path

from orchestration.exact_head_review import classify_review_attempt_outcome


WORKFLOW_PATH = Path(".github/workflows/exact_head_independent_review.yml")


def _verdict(approve: bool) -> dict[str, object]:
    return {
        "approve": approve,
        "reason": "test verdict",
        "risk": "low" if approve else "high",
        "integration_authority": "NONE",
    }


def test_transient_security_plus_valid_claude_rejection_is_terminal() -> None:
    assert classify_review_attempt_outcome(
        [None, None, _verdict(False)],
        controlled_wait=True,
        approved_outcome="",
    ) == "REJECTED"


def test_transient_claude_plus_valid_security_rejection_is_terminal() -> None:
    assert classify_review_attempt_outcome(
        [_verdict(False), None, None],
        controlled_wait=True,
        approved_outcome="",
    ) == "REJECTED"


def test_partial_approval_plus_transient_without_rejection_remains_wait() -> None:
    assert classify_review_attempt_outcome(
        [_verdict(True), None, None],
        controlled_wait=True,
        approved_outcome="",
    ) == "WAIT_RETRYABLE"


def test_all_three_valid_approvals_can_record_approval() -> None:
    outcome = "REVIEW_APPROVED_PROTECTED_LEAD_INTEGRATION_REQUIRED"
    assert classify_review_attempt_outcome(
        [_verdict(True), _verdict(True), _verdict(True)],
        controlled_wait=False,
        approved_outcome=outcome,
    ) == outcome


def test_approval_receipt_cannot_override_a_valid_rejection() -> None:
    assert classify_review_attempt_outcome(
        [_verdict(True), _verdict(False), _verdict(True)],
        controlled_wait=False,
        approved_outcome="REVIEW_APPROVED_LEAD_INTEGRATION_REQUIRED",
    ) == "REJECTED"


def test_workflow_persists_and_blocks_terminal_exact_sha_rejections() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "exact-head-review-rejected: pr=$PR_NUMBER sha=$REQUESTED_SHA" in workflow
    assert "ALREADY_REJECTED" in workflow
    assert "steps.review_models.outputs.rejected == 'true'" in workflow
    assert "A valid independent scientific rejection is terminal for this exact SHA" in workflow
    assert "revise the candidate to a new head" in workflow
