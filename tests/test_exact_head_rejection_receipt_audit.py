from __future__ import annotations

from orchestration.exact_head_control_state import exact_head_control_state


PR = 606
SHA = "a" * 40
NEW_SHA = "c" * 40
MAIN = "b" * 40
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


def _attempt(number: int, *, outcome: str, sha: str = SHA) -> dict[str, object]:
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


def _rejection_receipt(number: int, source_attempt: int) -> dict[str, object]:
    source_run = 9000 + source_attempt
    return _issue(
        number,
        f"exact-head-review-rejected: pr={PR} sha={SHA}",
        "\n".join(
            [
                f"Repository: `{REPO}`",
                f"PR: #{PR}",
                "Candidate branch: `agent/test`",
                f"Exact rejected SHA: `{SHA}`",
                f"Source attempt issue: #{source_attempt}",
                f"Source workflow run: `{source_run}`",
                f"Workflow main SHA: `{MAIN}`",
                "Outcome: `REJECTED`",
                "Integration authority: `NONE`",
            ]
        ),
    )


def _approval_receipt(number: int, source_attempt: int) -> dict[str, object]:
    source_run = 9000 + source_attempt
    return _issue(
        number,
        f"exact-head-review-approved: pr={PR} sha={SHA}",
        "\n".join(
            [
                f"Repository: `{REPO}`",
                f"PR: #{PR}",
                "Candidate branch: `agent/test`",
                f"Exact reviewed SHA: `{SHA}`",
                f"Source attempt issue: #{source_attempt}",
                f"Source workflow run: `{source_run}`",
                f"Workflow main SHA: `{MAIN}`",
                f"Outcome: `{APPROVED}`",
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


def test_duplicate_secondary_rejection_receipts_never_reopen_source_rejection() -> None:
    source = _attempt(11, outcome="REJECTED")
    state = _state([source, _rejection_receipt(12, 11), _rejection_receipt(13, 11)])

    assert state["rejected"] is True
    assert state["approved"] is False
    assert state["validated_rejected_attempts"] == [11]
    assert state["validated_rejection_receipts"] == [12, 13]
    assert state["ambiguous_control_state"] is True
    assert state["terminal_precedence"] == "REJECTION_DOMINATES_APPROVAL"


def test_late_rejection_dominates_prior_valid_approval_even_with_duplicate_audit_receipts() -> None:
    approved_source = _attempt(20, outcome=APPROVED)
    rejected_source = _attempt(22, outcome="REJECTED")
    state = _state(
        [
            approved_source,
            _approval_receipt(21, 20),
            rejected_source,
            _rejection_receipt(23, 22),
            _rejection_receipt(24, 22),
        ]
    )

    assert state["rejected"] is True
    assert state["approved"] is False
    assert state["validated_approval_receipts"] == [21]
    assert state["validated_rejected_attempts"] == [22]
    assert state["ambiguous_control_state"] is True


def test_materially_new_exact_sha_has_no_inherited_terminal_state() -> None:
    state = _state([], sha=NEW_SHA)
    assert state["rejected"] is False
    assert state["approved"] is False
    assert state["ambiguous_control_state"] is False
    assert state["attempt_count"] == 0
