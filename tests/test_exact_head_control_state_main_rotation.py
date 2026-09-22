from __future__ import annotations

from orchestration.exact_head_control_state import exact_head_control_state


PR = 606
HEAD = "a" * 40
OLD_MAIN = "b" * 40
NEW_MAIN = "c" * 40
REPO = "rnnyrgs-web/tradingview-ai-crypto"
BOT = "github-actions[bot]"
APPROVED = "REVIEW_APPROVED_LEAD_INTEGRATION_REQUIRED"


def _attempt(number: int, *, outcome: str, workflow_main_sha: str = OLD_MAIN) -> dict[str, object]:
    run = 9100 + number
    return {
        "number": number,
        "title": f"exact-head-review-attempt: pr={PR} sha={HEAD} run={run}",
        "body": "\n".join(
            [
                f"Repository: `{REPO}`",
                f"PR: #{PR}",
                "Candidate branch: `agent/test`",
                f"Exact reviewed SHA: `{HEAD}`",
                "Exact-head Security and Reliability run: `12345`",
                f"Workflow run: `{run}`",
                f"Workflow main SHA: `{workflow_main_sha}`",
                f"Outcome: `{outcome}`",
                "Integration authority: `NONE`",
            ]
        ),
        "user": {"login": BOT},
    }


def _approval_receipt(number: int, source_attempt: int, *, workflow_main_sha: str = OLD_MAIN) -> dict[str, object]:
    source_run = 9100 + source_attempt
    return {
        "number": number,
        "title": f"exact-head-review-approved: pr={PR} sha={HEAD}",
        "body": "\n".join(
            [
                f"Repository: `{REPO}`",
                f"PR: #{PR}",
                "Candidate branch: `agent/test`",
                f"Exact reviewed SHA: `{HEAD}`",
                "Exact-head Security and Reliability run: `12345` — PASS",
                f"Source attempt issue: #{source_attempt}",
                f"Source workflow run: `{source_run}`",
                f"Workflow main SHA: `{workflow_main_sha}`",
                f"Outcome: `{APPROVED}`",
                "Protected paths: `[]`",
                "Integration authority: `NONE`",
            ]
        ),
        "user": {"login": BOT},
    }


def _state(issues: list[dict[str, object]], *, current_main: str = NEW_MAIN) -> dict[str, object]:
    return exact_head_control_state(
        issues,
        pr_number=PR,
        head_sha=HEAD,
        workflow_main_sha=current_main,
        repository=REPO,
    )


def test_rejection_survives_canonical_main_rotation_for_same_candidate_sha() -> None:
    """A new canonical reviewer-runtime SHA must not reopen a rejected candidate SHA."""
    state = _state([_attempt(11, outcome="REJECTED")])
    assert state["rejected"] is True
    assert state["terminal_nonretryable"] is True


def test_interrupted_attempt_survives_canonical_main_rotation() -> None:
    """Unknown/lost reviewer judgment stays non-retryable even after main changes."""
    state = _state([_attempt(12, outcome="STARTED")])
    assert state["interrupted"] is True
    assert state["terminal_nonretryable"] is True


def test_completed_approval_is_history_but_not_current_authority_after_main_rotation() -> None:
    """Approval is contextual; negative memory is global, but integration authority is not."""
    source = _attempt(13, outcome=APPROVED)
    receipt = _approval_receipt(14, 13)
    state = _state([source, receipt])

    # Preserve the authenticated historical approval pair for audit.
    assert state["validated_approved_attempts"] == [13]
    assert state["validated_approval_receipts"] == [14]
    assert state["validated_approval_receipt_sources"] == [13]

    # But an approval created under OLD_MAIN cannot authorize integration after
    # canonical main has moved. Revalidation is allowed because there is no
    # rejection/interrupted attempt; this avoids both stale approval reuse and
    # turning a prior positive review into permanent no-review-shopping state.
    assert state["approved"] is False
    assert state["rejected"] is False
    assert state["interrupted"] is False
    assert state["terminal_nonretryable"] is False
    assert state["ambiguous_control_state"] is False


def test_completed_approval_remains_authoritative_while_reviewer_main_is_unchanged() -> None:
    source = _attempt(16, outcome=APPROVED)
    receipt = _approval_receipt(17, 16)
    state = _state([source, receipt], current_main=OLD_MAIN)
    assert state["approved"] is True
    assert state["terminal_nonretryable"] is True


def test_wait_attempt_does_not_become_invalid_control_state_only_because_main_rotated() -> None:
    """A genuine WAIT remains bounded retry evidence; main rotation is not corruption."""
    state = _state([_attempt(15, outcome="WAIT_RETRYABLE")])
    assert state["rejected"] is False
    assert state["approved"] is False
    assert state["terminal_nonretryable"] is False
    assert state["ambiguous_control_state"] is False
    assert state["attempt_count"] == 1
