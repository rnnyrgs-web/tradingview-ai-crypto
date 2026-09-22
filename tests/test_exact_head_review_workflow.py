from __future__ import annotations

from pathlib import Path

from orchestration.protected_paths import is_protected


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "exact_head_independent_review.yml"
REVIEWER = ROOT / "orchestration" / "exact_head_review.py"
CONTROL_STATE = ROOT / "orchestration" / "exact_head_control_state.py"


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
    assert '[ "$REQUEST_AUTHOR" != "$REPO_OWNER" ]' in text
    assert "only repository owner $REPO_OWNER may authorize reviewer execution" in text
    assert "Closing without invoking any model/API" in text
    assert "--jq --arg" not in text


def test_control_plane_enumeration_is_complete_not_fixed_limit() -> None:
    text = _text()
    assert 'gh api --paginate "/repos/$GITHUB_REPOSITORY/issues?state=open&per_page=100"' in text
    assert 'gh api --paginate "/repos/$GITHUB_REPOSITORY/issues?state=all&per_page=100"' in text
    assert "--limit 500" not in text
    assert "map(select(.pull_request == null))" in text
    assert "python -m orchestration.exact_head_control_state" in text


def test_control_plane_writer_is_globally_serialized() -> None:
    text = _text()
    assert "concurrency:" in text
    assert "group: exact-head-independent-review" in text
    assert "cancel-in-progress: false" in text


def test_review_validator_and_rejection_predicate_are_canonical_protected_paths() -> None:
    assert is_protected(".github/workflows/exact_head_independent_review.yml")
    assert is_protected("orchestration/exact_head_control_state.py")
    assert is_protected("orchestration/exact_head_review.py")


def test_durable_review_receipts_require_bot_author_and_exact_body_binding() -> None:
    text = _text()
    control = CONTROL_STATE.read_text(encoding="utf-8")
    assert "github-actions[bot]" in control
    assert "Exact reviewed SHA:" in control
    assert 'sha_label="Exact rejected SHA"' in control
    assert "Source attempt issue:" in control
    assert "Outcome:" in control
    assert "Integration authority:" in control
    assert "admin_mutation_is_trusted_boundary" in control
    assert '--workflow-main-sha "$MAIN_SHA"' in text
    assert "Source workflow run:" in text


def test_terminal_rejection_uses_source_attempt_fallback_and_verified_receipt() -> None:
    text = _text()
    assert "validated_rejected_attempts" in text
    assert "validated_rejection_receipts" in text
    assert "SOURCE_STATE" in text
    assert "VERIFIED_STATE" in text
    assert 'test "$SOURCE_MATCH" -eq 1' in text
    assert 'test "$VERIFIED_RECEIPTS" -eq 1' in text
    assert "REJECTION_URL=" in text
    assert "CREATED_REJECTION" in text
    assert "set -euo pipefail" in text


def test_partial_approval_persistence_cannot_trigger_reviewer_shopping() -> None:
    text = _text()
    assert "APPROVED_ATTEMPT_COUNT=" in text
    assert 'if [ "$APPROVED_ATTEMPT_COUNT" -gt 0 ]; then' in text
    assert "no unique verified approval receipt exists" in text
    assert "Closing fail-closed without rerunning reviewers" in text


def test_full_scientific_diff_has_one_consistent_hard_context_bound() -> None:
    workflow = _text()
    reviewer = REVIEWER.read_text(encoding="utf-8")
    assert 'test "$BYTES" -le 256000' in workflow
    assert "MAX_DIFF_BYTES = 256_000" in reviewer
    assert "Diff too large for one coherent exact-head review; fail closed and split the PR." in workflow


def test_protected_paths_are_reviewed_but_never_auto_integrated() -> None:
    text = _text()
    assert 'contents: read' in text
    assert 'contents: write' not in text
    assert 'AUTONOMOUS_MERGE_ENABLED: "false"' in text
    assert "REVIEW_APPROVED_PROTECTED_LEAD_INTEGRATION_REQUIRED" in text
    assert "Run independent exact-head reviewers with bounded transient WAIT" in text
    assert "gh pr merge" not in text
    assert "merge_pull_request" not in text
    assert 'jq -e \'.approve == true and .integration_authority == "NONE"\'' in text


def test_failed_attempts_are_bounded_while_valid_rejections_are_terminal_for_exact_sha() -> None:
    text = _text()
    assert "closed to prevent unbounded paid retries" in text
    assert "FAILED indicates missing/invalid infrastructure evidence rather than a scientific rejection" in text
    assert "retry the same SHA only after the objective runtime cause is materially repaired" in text
    assert "exact-head-review-rejected: pr=$PR_NUMBER sha=$REQUESTED_SHA" in text
    assert "Validated terminal rejection state already exists" in text
    assert "This exact SHA is terminal and cannot be reviewer-shopped" in text
    assert "revise the candidate to a new head" in text
    assert "exact-head-review-approved: pr=$PR_NUMBER sha=$REQUESTED_SHA" in text
    assert "autonomous-review-attempt" not in text


def test_model_review_cannot_run_before_exact_head_green_ci() -> None:
    text = _text()
    selection = text.index("Exact-head Security and Reliability run")
    review = text.index("Run independent exact-head reviewers with bounded transient WAIT")
    assert selection < review
    assert 'if [ "$CONCLUSION" != "success" ]; then' in text
    assert "Review models were not invoked" in text


def test_transient_reviewer_capacity_is_controlled_wait_not_approval() -> None:
    text = _text()
    assert "id: review_models" in text
    assert "WAIT_RETRYABLE" in text
    assert "maximum three attempts" in text
    assert "Bounded reviewer retry limit reached" in text
    assert "Candidate remains **unapproved** and **unmerged**" in text
    assert "steps.review_models.outputs.wait != 'true'" in text
    assert "no valid rejection" in text


def test_valid_rejection_precedes_wait_and_blocks_approval_path() -> None:
    text = _text()
    assert "classify_review_attempt_outcome" in text
    assert 'if [ "$REJECTED" -eq 1 ]; then' in text
    assert 'echo "rejected=true" >> "$GITHUB_OUTPUT"' in text
    assert "valid independent scientific rejection is terminal" in text
    assert "steps.review_models.outputs.rejected != 'true'" in text


def test_every_launched_parallel_reviewer_is_joined_before_rejection_scan() -> None:
    text = _text()
    launched = text.index("PID_CLAUDE=$!")
    joined = text.index('wait "$PID_CLAUDE"')
    scan = text.index('REJECTED="$(python - <<\'PY\'')
    assert launched < joined < scan
    assert "has_terminal_rejection(verdicts)" in text


def test_openai_reviewers_are_serial_while_claude_can_run_in_parallel() -> None:
    text = _text()
    claude = text.index("PID_CLAUDE=$!")
    security = text.index("SECURITY_STATUS=")
    lead = text.index("LEAD_STATUS=")
    assert claude < security < lead
    assert 'if [ "$STATUS" -eq 0 ] && [ "$WAIT" -eq 0 ]; then' in text
