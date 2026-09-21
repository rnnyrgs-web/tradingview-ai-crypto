from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "exact_head_independent_review.yml"
REVIEWER = ROOT / "orchestration" / "exact_head_review.py"


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_review_queue_is_keyed_by_pr_and_exact_sha_not_branch_namespace() -> None:
    text = _text()
    # Bash's [[ =~ ]] regex escapes literal spaces, so the durable request
    # prefix appears in the workflow source as `request:\ pr=`.
    assert "exact-head-review-request:\\ pr=" in text
    assert "sha=([0-9a-f]{40})" in text
    assert "refs/pull/$PR_NUMBER/head" in text
    assert "refs/remotes/origin/auto/*" not in text
    assert "refs/heads/auto/*" not in text
    assert "--commit \"$REQUESTED_SHA\"" in text
    assert "HEAD_SHA\" != \"$REQUESTED_SHA" in text


def test_paid_review_requests_are_repository_owner_authorized() -> None:
    text = _text()
    assert 'REPO_OWNER="${GITHUB_REPOSITORY%%/*}"' in text
    assert "--json number,title,createdAt,author" in text
    assert '[ "$REQUEST_AUTHOR" != "$REPO_OWNER" ]' in text
    assert "only repository owner $REPO_OWNER may authorize reviewer execution" in text
    assert "Closing without invoking any model/API" in text
    # Keep jq argument passing in jq itself rather than forwarding unsupported
    # `--arg` flags through the GitHub CLI's `--jq` option.
    assert "--jq --arg" not in text
    assert "jq --arg title \"$APPROVED_TITLE\"" in text


def test_full_scientific_diff_has_one_consistent_hard_context_bound() -> None:
    workflow = _text()
    reviewer = REVIEWER.read_text(encoding="utf-8")
    assert 'test "$BYTES" -le 256000' in workflow
    assert "MAX_DIFF_BYTES = 256_000" in reviewer
    assert "never truncate it" in workflow


def test_protected_paths_are_reviewed_but_never_auto_integrated() -> None:
    text = _text()
    assert 'contents: read' in text
    assert 'contents: write' not in text
    assert 'AUTONOMOUS_MERGE_ENABLED: "false"' in text
    assert "REVIEW_APPROVED_PROTECTED_LEAD_INTEGRATION_REQUIRED" in text
    assert "Run Security, Lead and Claude adversarial exact-head reviews in parallel" in text
    assert "gh pr merge" not in text
    assert "merge_pull_request" not in text
    assert "integration_authority == \"NONE\"" in text


def test_failed_attempts_are_bounded_but_not_permanent_blacklist() -> None:
    text = _text()
    assert "closed to prevent unbounded paid retries" in text
    assert "FAILED/REJECTED does not permanently blacklist the exact SHA" in text
    # Only durable approval blocks a duplicate request; failed attempts are not searched
    # as an exclusion condition by the selector.
    assert "exact-head-review-approved: pr=$PR_NUMBER sha=$REQUESTED_SHA" in text
    assert "autonomous-review-attempt" not in text


def test_model_review_cannot_run_before_exact_head_green_ci() -> None:
    text = _text()
    selection = text.index("Exact-head Security and Reliability run")
    review = text.index("Run Security, Lead and Claude adversarial exact-head reviews in parallel")
    assert selection < review
    assert 'CONCLUSION\" != \"success\"' in text
    assert "Review models were not invoked" in text


def test_transient_reviewer_capacity_is_controlled_wait_not_approval() -> None:
    text = _text()
    assert "id: review_models" in text
    assert "WAIT_RETRYABLE" in text
    assert "maximum three attempts" in text
    assert "Bounded reviewer retry limit reached" in text
    assert "Candidate remains **unapproved** and **unmerged**" in text
    assert "steps.review_models.outputs.wait != 'true'" in text


def test_openai_reviewers_are_serial_while_claude_can_run_in_parallel() -> None:
    text = _text()
    claude = text.index("PID_CLAUDE=$!")
    security = text.index("SECURITY_STATUS=")
    lead = text.index("LEAD_STATUS=")
    assert claude < security < lead
    assert "same rate-limit bucket" in text
