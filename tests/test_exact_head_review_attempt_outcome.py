from itertools import product
from pathlib import Path

from orchestration import exact_head_review as review
from orchestration.exact_head_review import classify_review_attempt_outcome, has_terminal_rejection


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


def test_middle_reviewer_rejection_is_terminal_even_when_others_are_missing() -> None:
    assert classify_review_attempt_outcome(
        [None, _verdict(False), None],
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


def test_non_boolean_approval_cannot_create_rejection_or_approval() -> None:
    invalid = {
        "approve": 0,
        "reason": "not actually boolean",
        "risk": "high",
        "integration_authority": "NONE",
    }
    assert classify_review_attempt_outcome(
        [invalid, None, None],
        controlled_wait=False,
        approved_outcome="",
    ) == "FAILED"
    assert classify_review_attempt_outcome(
        [invalid, _verdict(True), _verdict(True)],
        controlled_wait=False,
        approved_outcome="REVIEW_APPROVED_LEAD_INTEGRATION_REQUIRED",
    ) == "FAILED"


def test_invalid_authority_cannot_create_rejection_or_approval() -> None:
    rejected = _verdict(False)
    rejected["integration_authority"] = "MERGE"
    approved = _verdict(True)
    approved["integration_authority"] = "MERGE"
    assert classify_review_attempt_outcome(
        [rejected, None, None],
        controlled_wait=False,
        approved_outcome="",
    ) == "FAILED"
    assert classify_review_attempt_outcome(
        [approved, _verdict(True), _verdict(True)],
        controlled_wait=False,
        approved_outcome="REVIEW_APPROVED_LEAD_INTEGRATION_REQUIRED",
    ) == "FAILED"


def test_invalid_risk_schema_cannot_create_rejection() -> None:
    invalid = _verdict(False)
    invalid["risk"] = "unknown"
    assert classify_review_attempt_outcome(
        [None, invalid, None],
        controlled_wait=False,
        approved_outcome="",
    ) == "FAILED"


def test_terminal_rejection_predicate_is_invariant_across_live_and_receipt_classification() -> None:
    """Any valid rejection seen by the live path must force receipt classification to REJECTED."""
    choices: list[dict[str, object] | None] = [None, _verdict(True), _verdict(False)]
    for verdict_tuple in product(choices, repeat=3):
        verdicts = list(verdict_tuple)
        if not has_terminal_rejection(verdicts):
            continue
        for controlled_wait in (False, True):
            for approved_outcome in ("", "REVIEW_APPROVED_LEAD_INTEGRATION_REQUIRED"):
                assert classify_review_attempt_outcome(
                    verdicts,
                    controlled_wait=controlled_wait,
                    approved_outcome=approved_outcome,
                ) == "REJECTED"


def test_receipt_classifier_calls_the_same_terminal_rejection_function(monkeypatch) -> None:
    calls: list[list[dict[str, object] | None]] = []

    def sentinel(verdicts: list[dict[str, object] | None]) -> bool:
        calls.append(verdicts)
        return True

    monkeypatch.setattr(review, "has_terminal_rejection", sentinel)
    verdicts = [_verdict(True), None, None]
    assert review.classify_review_attempt_outcome(
        verdicts,
        controlled_wait=True,
        approved_outcome="",
    ) == "REJECTED"
    assert calls == [verdicts]


def test_workflow_persists_and_blocks_terminal_exact_sha_rejections() -> None:
    workflow = WORKFLOW_PATH.read_text(encoding="utf-8")
    assert "exact-head-review-rejected: pr=$PR_NUMBER sha=$REQUESTED_SHA" in workflow
    assert "ALREADY_REJECTED" in workflow
    assert "steps.review_models.outputs.rejected == 'true'" in workflow
    assert "A valid independent scientific rejection is terminal for this exact SHA" in workflow
    assert "revise the candidate to a new head" in workflow
    # The live workflow and durable receipt finalizer both import the canonical
    # exact_head_review module rather than carrying two independent predicates.
    assert "from orchestration.exact_head_review import has_terminal_rejection" in workflow
    assert "from orchestration.exact_head_review import classify_review_attempt_outcome" in workflow
