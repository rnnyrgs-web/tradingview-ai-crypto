from pathlib import Path


WORKFLOW = Path(".github/workflows/exact_head_independent_review.yml")


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_explicit_owner_exact_head_request_may_review_draft_pr_without_ready_transition() -> None:
    text = _workflow_text()

    # Read-only independent review must not require a candidate PR to become
    # merge-ready merely so the reviewer can inspect its exact head. The request
    # itself remains owner-authored, exact-SHA-bound, and grants no integration
    # authority.
    assert '[ "$PR_DRAFT" = "true" ]' not in text
    assert '[ "$PR_STATE" != "OPEN" ] || [ "$BASE_REF" != "main" ]' in text
    assert 'if [ "$REQUEST_AUTHOR" != "$REPO_OWNER" ]; then' in text
    assert 'Integration authority: \\`NONE\\`' in text
    assert 'AUTONOMOUS_MERGE_ENABLED: "false"' in text


def test_exact_head_identity_and_green_security_gate_remain_required() -> None:
    text = _workflow_text()

    assert 'if [ "$HEAD_SHA" != "$REQUESTED_SHA" ]; then' in text
    assert 'if [ "$FETCHED_SHA" != "$REQUESTED_SHA" ]; then' in text
    assert 'if [ "$MERGE_BASE" != "$MAIN_SHA" ]; then' in text
    assert "if [ \"$CONCLUSION\" != \"success\" ]; then" in text
