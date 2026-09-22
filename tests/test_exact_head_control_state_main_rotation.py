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


def _state(issues: list[dict[str, object]]) -> dict[str, object]:
    return exact_head_control_state(
        issues,
        pr_number=PR,
        head_sha=HEAD,
        workflow_main_sha=NEW_MAIN,
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


def test_completed_approval_and_receipt_survive_canonical_main_rotation() -> None:
    """Exact-head clearance is invalidated by a new candidate head, not unrelated main drift."""
    source = _attempt(13, outcome=APPROVED)
    receipt = _approval_receipt(14, 13)
    state = _state([source, receipt])
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
