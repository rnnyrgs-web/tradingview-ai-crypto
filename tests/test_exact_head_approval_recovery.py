from __future__ import annotations

import pytest

from orchestration.exact_head_approval_recovery import build_approval_recovery_receipt
from orchestration.exact_head_control_state import ControlStateError


PR = 606
SHA = "a" * 40
MAIN = "b" * 40
OLD_MAIN = "c" * 40
REPO = "rnnyrgs-web/tradingview-ai-crypto"
BOT = "github-actions[bot]"
APPROVED = "REVIEW_APPROVED_LEAD_INTEGRATION_REQUIRED"


def _issue(number: int, title: str, body: str, *, author: str = BOT) -> dict[str, object]:
    return {
        "number": number,
        "title": title,
        "body": body,
        "user": {"login": author},
    }


def _attempt(
    number: int,
    *,
    outcome: str = APPROVED,
    main: str = MAIN,
    author: str = BOT,
) -> dict[str, object]:
    run = 9000 + number
    return _issue(
        number,
        f"exact-head-review-attempt: pr={PR} sha={SHA} run={run}",
        "\n".join(
            [
                f"Repository: `{REPO}`",
                f"PR: #{PR}",
                "Candidate branch: `agent/test`",
                f"Exact reviewed SHA: `{SHA}`",
                "Exact-head Security and Reliability run: `12345`",
                f"Workflow run: `{run}`",
                f"Workflow main SHA: `{main}`",
                f"Outcome: `{outcome}`",
                "Integration authority: `NONE`",
            ]
        ),
        author=author,
    )


def _approval_receipt(number: int, source: int, *, main: str = MAIN) -> dict[str, object]:
    run = 9000 + source
    return _issue(
        number,
        f"exact-head-review-approved: pr={PR} sha={SHA}",
        "\n".join(
            [
                f"Repository: `{REPO}`",
                f"PR: #{PR}",
                f"Exact reviewed SHA: `{SHA}`",
                f"Source attempt issue: #{source}",
                f"Source workflow run: `{run}`",
                f"Workflow main SHA: `{main}`",
                f"Outcome: `{APPROVED}`",
                "Integration authority: `NONE`",
            ]
        ),
    )


def _recover(issues: list[dict[str, object]], source: int = 20):
    return build_approval_recovery_receipt(
        issues,
        pr_number=PR,
        head_sha=SHA,
        workflow_main_sha=MAIN,
        repository=REPO,
        source_issue_number=source,
    )


def test_recovery_reconstructs_only_missing_secondary_receipt_without_rerunning_reviewers() -> None:
    receipt = _recover([_attempt(20)])

    assert receipt["receipt_title"] == f"exact-head-review-approved: pr={PR} sha={SHA}"
    assert receipt["source_issue"] == 20
    assert receipt["source_run"] == 9020
    assert receipt["outcome"] == APPROVED
    assert receipt["workflow_main_sha"] == MAIN
    assert receipt["integration_authority"] == "NONE"
    assert f"Source attempt issue: #20" in receipt["receipt_body"]
    assert f"Workflow main SHA: `{MAIN}`" in receipt["receipt_body"]
    assert "No reviewer was rerun" in receipt["receipt_body"]


def test_recovery_is_forbidden_after_any_rejection() -> None:
    with pytest.raises(ControlStateError, match="rejection dominates"):
        _recover([_attempt(20), _attempt(21, outcome="REJECTED")])


def test_recovery_is_forbidden_for_interrupted_started_attempt() -> None:
    with pytest.raises(ControlStateError, match="interrupted"):
        _recover([_attempt(20, outcome="STARTED")])


def test_recovery_is_forbidden_when_receipt_already_exists() -> None:
    with pytest.raises(ControlStateError, match="already complete"):
        _recover([_attempt(20), _approval_receipt(21, 20)])


def test_historical_old_main_approval_cannot_be_recovered_as_current_authority() -> None:
    with pytest.raises(ControlStateError, match="no incomplete current-context"):
        _recover([_attempt(20, main=OLD_MAIN)])


def test_recovery_requires_exactly_one_requested_unreceipted_current_approval() -> None:
    with pytest.raises(ControlStateError, match="exactly the requested"):
        _recover([_attempt(20), _attempt(21)], source=20)


def test_untrusted_owner_authored_lookalike_cannot_be_recovered() -> None:
    with pytest.raises(ControlStateError, match="no incomplete current-context"):
        _recover([_attempt(20, author="rnnyrgs-web")])


def test_recovered_receipt_validates_to_approval_when_persisted() -> None:
    source = _attempt(20)
    recovered = _recover([source])
    receipt = _issue(21, recovered["receipt_title"], recovered["receipt_body"])

    # A second recovery is now forbidden because the exact source/receipt pair
    # is complete; this proves the generated receipt is accepted by the same
    # authoritative control-state parser used by the reviewer workflow.
    with pytest.raises(ControlStateError, match="already complete"):
        _recover([source, receipt])
