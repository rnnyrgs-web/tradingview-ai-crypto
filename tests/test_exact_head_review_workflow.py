from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "exact_head_independent_review.yml"
REVIEWER = ROOT / "orchestration" / "exact_head_review.py"


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_review_queue_is_keyed_by_pr_and_exact_sha_not_branch_namespace() -> None:
    text = _text()
    assert "exact-head-review-request:\\ pr=" in text
    assert "sha=([0-9a-f]{40})" in text
    assert "refs/pull/$PR_NUMBER/head" in text
    assert "refs/remotes/origin/auto/*" not in text
    assert "refs/heads/auto/*" not in text
    assert "--commit \"$REQUESTED_SHA\"" in text
    assert "HEAD_SHA\" != \"$REQUESTED_SHA" in text


def test_paid_review_requests_are_repository_owner_authorized_and_fully_paginated() -> None:
    text = _text()
    assert 'REPO_OWNER="${GITHUB_REPOSITORY%%/*}"' in text
    assert '[ "$REQUEST_AUTHOR" != "$REPO_OWNER" ]' in text
    assert "only repository owner $REPO_OWNER may authorize reviewer execution" in text
    assert "Closing without invoking any model/API" in text
    assert 'gh api --paginate "/repos/$GITHUB_REPOSITORY/issues?state=open&per_page=100' in text
    assert 'gh api --paginate "/repos/$GITHUB_REPOSITORY/issues?state=all&per_page=100' in text
    assert "(.user.login // \"\")" in text
    assert "gh issue list --repo \"$GITHUB_REPOSITORY\" --state all --limit 100 --json title" not in text


def test_durable_control_state_not_title_only_memory_authorizes_reviews() -> None:
    text = _text()
    assert "orchestration.exact_head_control_state" in text
    assert "ALREADY_REJECTED" in text
    assert "TERMINAL_NONRETRYABLE" in text
    assert "AMBIGUOUS_CONTROL_STATE" in text
    assert "validated terminal rejection state already exists" in text
    assert "title alone" not in text.lower()
    assert "APPROVALS=\"$(gh issue list" not in text


def test_full_scientific_diff_has_one_consistent_hard_context_bound() -> None:
    workflow = _text()
    reviewer = REVIEWER.read_text(encoding="utf-8")
    assert 'test "$BYTES" -le 256000' in workflow
    assert "MAX_DIFF_BYTES = 256_000" in reviewer
    assert "never truncate it" in workflow


def test_protected_paths_are_reviewed_but_never_auto_integrated() -> None:
    text = _text()
    assert "contents: read" in text
    assert "contents: write" not in text
    assert 'AUTONOMOUS_MERGE_ENABLED: "false"' in text
    assert "REVIEW_APPROVED_PROTECTED_LEAD_INTEGRATION_REQUIRED" in text
    assert "Run independent exact-head reviewers with bounded transient WAIT" in text
    assert "gh pr merge" not in text
    assert "merge_pull_request" not in text
    assert 'integration_authority == "NONE"' in text


def test_retryable_wait_is_bounded_but_valid_rejection_is_terminal() -> None:
    text = _text()
    assert "Bounded reviewer retry limit reached" in text
    assert "WAIT_RETRYABLE" in text
    assert "REJECTED is terminal for the exact SHA" in text
    assert "do not retry the same {pr, sha}" in text
    assert "FAILED/REJECTED does not permanently blacklist the exact SHA" not in text
    assert "exact-head-review-approved: pr=$PR_NUMBER sha=$HEAD_SHA" in text
    assert "autonomous-review-attempt" not in text


def test_model_review_cannot_run_before_exact_head_green_ci() -> None:
    text = _text()
    selection = text.index("Exact-head Security and Reliability run")
    review = text.index("Run independent exact-head reviewers with bounded transient WAIT")
    assert selection < review
    assert 'CONCLUSION\" != \"success\"' in text
    assert "Review models were not invoked" in text


def test_transient_reviewer_capacity_is_controlled_wait_not_approval() -> None:
    text = _text()
    assert "id: review_models" in text
    assert "WAIT_RETRYABLE" in text
    assert "bounded three-attempt limit" in text
    assert "Bounded reviewer retry limit reached" in text
    assert "Candidate remains **unapproved** and **unmerged**" in text
    assert "steps.review_models.outputs.wait != 'true'" in text
    assert "steps.review_models.outputs.rejected != 'true'" in text


def test_openai_reviewers_are_serial_while_claude_can_run_in_parallel() -> None:
    text = _text()
    claude = text.index("PID_CLAUDE=$!")
    security = text.index("SECURITY_STATUS=")
    lead = text.index("LEAD_STATUS=")
    assert claude < security < lead
    assert "same rate-limit bucket" in text


def test_draft_candidates_are_reviewable_without_opening_merge_surface() -> None:
    text = _text()
    assert "--json number,headRefName,headRefOid,baseRefName,isDraft,state" in text
    assert '[ "$PR_STATE" != "OPEN" ] || [ "$BASE_REF" != "main" ]' in text
    assert '[ "$PR_STATE" != "OPEN" ] || [ "$PR_DRAFT" = "true" ]' not in text
    assert "remains DRAFT; exact-head review is allowed without exposing an unapproved PR to mergeability" in text
    assert "gh pr ready" not in text
    assert "pull-requests: write" not in text


def test_independent_review_status_is_exact_head_bound_and_authenticated() -> None:
    text = _text()
    assert "statuses: write" in text
    assert '"repos/$GITHUB_REPOSITORY/statuses/$HEAD_SHA"' in text
    assert "-f context=independent-review" in text
    assert "-f state=pending" in text
    assert "VERIFIED_STATE" in text
    assert "'.rejected'" in text
    assert "'.approved'" in text
    assert "'.terminal_nonretryable'" in text
    assert "'.ambiguous_control_state'" in text
    assert 'STATUS_STATE="failure"' in text
    assert 'STATUS_STATE="success"' in text
    assert 'STATUS_STATE="pending"' in text
    assert 'STATUS_STATE="error"' in text
    assert 'case "$OUTCOME"' not in text
    assert 'REVIEW_APPROVED_*)\n              STATUS_STATE="success"' not in text


def test_positive_status_is_emitted_only_after_source_attempt_and_receipt_reread() -> None:
    text = _text()
    edit_attempt = text.index('gh issue edit "$ATTEMPT_ISSUE"')
    create_approval = text.index('exact-head-review-approved: pr=$PR_NUMBER sha=$HEAD_SHA')
    verified_reread = text.rindex("orchestration.exact_head_control_state")
    status_post = text.rindex('"repos/$GITHUB_REPOSITORY/statuses/$HEAD_SHA"')
    assert edit_attempt < create_approval < verified_reread < status_post
    assert "Source attempt issue: #$ATTEMPT_ISSUE" in text
    assert "Source workflow run: \\`$GITHUB_RUN_ID\\`" in text
