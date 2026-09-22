from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "exact_head_independent_review.yml"


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_selector_consumes_terminal_nonretryable_before_model_invocation() -> None:
    text = _text()
    selector = text[: text.index("Run independent exact-head reviewers with bounded transient WAIT")]

    assert 'TERMINAL_NONRETRYABLE="$(printf' in selector
    assert "jq -r '.terminal_nonretryable'" in selector
    assert 'if [ "$TERMINAL_NONRETRYABLE" = "true" ]; then' in selector
    assert "This SHA cannot invoke reviewers again" in selector
    assert "revise the candidate to a materially new SHA" in selector


def test_approval_receipt_is_not_created_before_source_attempt_finalization() -> None:
    text = _text()

    assert "Create provisional exact-head approval receipt" not in text
    assert "Freeze intended exact-head approval outcome" in text

    finalize_step = text.index("Finalize durable attempt receipt and bound retries")
    source_finalize = text.index('gh issue edit "$ATTEMPT_ISSUE"', finalize_step)
    approved_branch = text.index('elif [[ "$OUTCOME" == REVIEW_APPROVED_* ]]; then', source_finalize)
    approval_create = text.index(
        'gh issue create --repo "$GITHUB_REPOSITORY" --title "exact-head-review-approved:',
        approved_branch,
    )

    assert source_finalize < approved_branch < approval_create
    assert text.count(
        'gh issue create --repo "$GITHUB_REPOSITORY" --title "exact-head-review-approved:'
    ) == 1


def test_approved_source_without_receipt_is_verified_terminal_before_receipt_creation() -> None:
    text = _text()
    approved_branch_start = text.index('elif [[ "$OUTCOME" == REVIEW_APPROVED_* ]]; then')
    approval_create = text.index(
        'gh issue create --repo "$GITHUB_REPOSITORY" --title "exact-head-review-approved:',
        approved_branch_start,
    )
    pre_receipt = text[approved_branch_start:approval_create]

    assert "'.rejected'" in pre_receipt
    assert "'.interrupted'" in pre_receipt
    assert "'.terminal_nonretryable'" in pre_receipt
    assert "'.approval_persistence_incomplete'" in pre_receipt
    assert "validated_approved_attempts" in pre_receipt
    assert "validated_approval_receipts | length" in pre_receipt
    assert "invalid_trusted_control_issues | length" in pre_receipt


def test_approval_receipt_is_reread_and_must_bind_exact_source_pair() -> None:
    text = _text()
    approved_branch_start = text.index('elif [[ "$OUTCOME" == REVIEW_APPROVED_* ]]; then')
    after = text[approved_branch_start:]

    approval_create = after.index(
        'gh issue create --repo "$GITHUB_REPOSITORY" --title "exact-head-review-approved:'
    )
    verified_state = after.index("VERIFIED_STATE=", approval_create)
    approved_check = after.index("'.approved'", verified_state)
    receipt_match = after.index("validated_approval_receipts", approved_check)

    assert approval_create < verified_state < approved_check < receipt_match
    assert 'test "$RECEIPT_MATCH" -eq 1' in after[receipt_match:]
