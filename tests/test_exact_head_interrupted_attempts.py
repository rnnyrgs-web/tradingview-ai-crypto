from __future__ import annotations

from orchestration.exact_head_control_state import exact_head_control_state


SHA = "a" * 40
OTHER_SHA = "c" * 40
MAIN = "b" * 40
PR = 606
REPO = "rnnyrgs-web/tradingview-ai-crypto"
BOT = "github-actions[bot]"
APPROVED = "REVIEW_APPROVED_LEAD_INTEGRATION_REQUIRED"


def _issue(number: int, title: str, body: str) -> dict[str, object]:
    return {
        "number": number,
        "title": title,
        "body": body,
        "user": {"login": BOT},
    }


def _attempt(number: int, outcome: str, *, sha: str = SHA) -> dict[str, object]:
    run = 9000 + number
    return _issue(
        number,
        f"exact-head-review-attempt: pr={PR} sha={sha} run={run}",
        "\n".join(
            [
                f"Repository: `{REPO}`",
                f"PR: #{PR}",
                "Candidate branch: `agent/test`",
                f"Exact reviewed SHA: `{sha}`",
                "Exact-head Security and Reliability run: `12345`",
                f"Workflow run: `{run}`",
                f"Workflow main SHA: `{MAIN}`",
                f"Outcome: `{outcome}`",
                "Integration authority: `NONE`",
            ]
        ),
    )


def _approval_receipt(number: int, source_attempt: int, *, sha: str = SHA) -> dict[str, object]:
    source_run = 9000 + source_attempt
    return _issue(
        number,
        f"exact-head-review-approved: pr={PR} sha={sha}",
        "\n".join(
            [
                f"Repository: `{REPO}`",
                f"PR: #{PR}",
                "Candidate branch: `agent/test`",
                f"Exact reviewed SHA: `{sha}`",
                "Exact-head Security and Reliability run: `12345` — PASS",
                f"Source attempt issue: #{source_attempt}",
                f"Source workflow run: `{source_run}`",
                f"Workflow main SHA: `{MAIN}`",
                f"Outcome: `{APPROVED}`",
                "Protected paths: `[]`",
                "Integration authority: `NONE`",
            ]
        ),
    )


def _state(issues: list[dict[str, object]], *, sha: str = SHA) -> dict[str, object]:
    return exact_head_control_state(
        issues,
        pr_number=PR,
        head_sha=sha,
        workflow_main_sha=MAIN,
        repository=REPO,
    )


def test_lingering_started_attempt_is_interrupted_terminal_nonretryable() -> None:
    state = _state([_attempt(11, "STARTED")])

    assert state["interrupted"] is True
    assert state["terminal_nonretryable"] is True
    assert state["ambiguous_control_state"] is True
    assert state["approved"] is False
    assert state["rejected"] is False
    assert state["validated_interrupted_attempts"] == [11]
    assert state["attempt_count"] == 1


def test_started_plus_wait_remains_interrupted_and_nonretryable() -> None:
    state = _state(
        [
            _attempt(11, "STARTED"),
            _attempt(12, "WAIT_RETRYABLE"),
        ]
    )

    assert state["interrupted"] is True
    assert state["terminal_nonretryable"] is True
    assert state["ambiguous_control_state"] is True
    assert state["approved"] is False
    assert state["rejected"] is False
    assert state["validated_interrupted_attempts"] == [11]
    assert state["attempt_count"] == 2


def test_approval_receipt_cannot_rescue_started_source_attempt() -> None:
    state = _state(
        [
            _attempt(20, "STARTED"),
            _approval_receipt(21, 20),
        ]
    )

    assert state["interrupted"] is True
    assert state["terminal_nonretryable"] is True
    assert state["approved"] is False
    assert state["validated_approval_receipts"] == []
    assert state["invalid_trusted_control_issues"] == [21]
    assert state["ambiguous_control_state"] is True


def test_approved_source_without_receipt_never_grants_approval_or_retry() -> None:
    state = _state([_attempt(20, APPROVED)])

    assert state["interrupted"] is False
    assert state["rejected"] is False
    assert state["approved"] is False
    assert state["terminal_nonretryable"] is True
    assert state["approval_persistence_incomplete"] is True
    assert state["ambiguous_control_state"] is True
    assert state["validated_approved_attempts"] == [20]
    assert state["validated_approval_receipts"] == []
    assert state["unreceipted_approved_attempts"] == [20]


def test_provisional_approval_receipt_has_zero_authority_until_source_finalizes() -> None:
    before_finalization = _state(
        [
            _attempt(20, "STARTED"),
            _approval_receipt(21, 20),
        ]
    )
    after_finalization = _state(
        [
            _attempt(20, APPROVED),
            _approval_receipt(21, 20),
        ]
    )

    assert before_finalization["approved"] is False
    assert before_finalization["interrupted"] is True
    assert before_finalization["terminal_nonretryable"] is True
    assert before_finalization["validated_approval_receipts"] == []
    assert after_finalization["approved"] is True
    assert after_finalization["interrupted"] is False
    assert after_finalization["terminal_nonretryable"] is True
    assert after_finalization["approval_persistence_incomplete"] is False
    assert after_finalization["validated_approval_receipts"] == [21]


def test_interrupted_old_sha_does_not_poison_materially_new_sha() -> None:
    state = _state(
        [
            _attempt(11, "STARTED", sha=SHA),
            _attempt(12, "WAIT_RETRYABLE", sha=OTHER_SHA),
        ],
        sha=OTHER_SHA,
    )

    assert state["interrupted"] is False
    assert state["terminal_nonretryable"] is False
    assert state["ambiguous_control_state"] is False
    assert state["approved"] is False
    assert state["rejected"] is False
    assert state["validated_interrupted_attempts"] == []
    assert state["attempt_count"] == 1


def test_clean_finalized_approval_still_validates_and_is_nonretryable() -> None:
    state = _state(
        [
            _attempt(20, APPROVED),
            _approval_receipt(21, 20),
        ]
    )

    assert state["interrupted"] is False
    assert state["terminal_nonretryable"] is True
    assert state["ambiguous_control_state"] is False
    assert state["approved"] is True
    assert state["approval_persistence_incomplete"] is False
    assert state["validated_approved_attempts"] == [20]
    assert state["validated_approval_receipts"] == [21]
