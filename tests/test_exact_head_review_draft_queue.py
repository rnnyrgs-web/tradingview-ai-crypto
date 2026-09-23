from pathlib import Path


WORKFLOW = Path(".github/workflows/exact_head_independent_review.yml")


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_draft_state_is_not_a_review_eligibility_gate() -> None:
    text = _workflow_text()

    assert '[ "$PR_DRAFT" = "true" ]' not in text
    assert 'if [ "$PR_STATE" != "OPEN" ] || [ "$BASE_REF" != "main" ]; then' in text
    assert "Draft state is intentionally NOT a review-eligibility gate" in text


def test_draft_review_path_preserves_exact_head_fail_closed_gates() -> None:
    text = _workflow_text()

    required_fragments = (
        'if [ "$REQUEST_AUTHOR" != "$REPO_OWNER" ]; then',
        'if [ "$HEAD_SHA" != "$REQUESTED_SHA" ]; then',
        'if [ "$MERGE_BASE" != "$MAIN_SHA" ]; then',
        "--workflow 'Security and Reliability' --commit \"$REQUESTED_SHA\"",
        'if [ "$CONCLUSION" != "success" ]; then',
        'if [ "$ATTEMPT_COUNT" -ge 3 ]; then',
        'integration_authority == "NONE"',
    )
    for fragment in required_fragments:
        assert fragment in text
