from __future__ import annotations

import pytest

from orchestration.exact_head_control_state import ControlStateError, exact_head_control_state


REPO = "rnnyrgs-web/tradingview-ai-crypto"
SHA = "a" * 40
MAIN = "b" * 40


def _issue(number: int, title: str, body: str, *, author: str = "github-actions[bot]") -> dict:
    return {
        "number": number,
        "title": title,
        "body": body,
        "user": {"login": author},
        "repository_url": f"https://api.github.com/repos/{REPO}",
    }


def _attempt(number: int, outcome: str, *, run: int | None = None, author: str = "github-actions[bot]") -> dict:
    run_id = run or (9000 + number)
    return _issue(
        number,
        f"exact-head-review-attempt: pr=772 sha={SHA} run={run_id}",
        "\n".join(
            [
                "PR: #772",
                f"Exact reviewed SHA: `{SHA}`",
                f"Workflow run: `{run_id}`",
                f"Workflow main SHA: `{MAIN}`",
                f"Outcome: `{outcome}`",
                "Integration authority: `NONE`",
            ]
        ),
        author=author,
    )


def _receipt(number: int, source: dict, outcome: str, *, rejected: bool = False) -> dict:
    source_number = source["number"]
    source_run = int(source["title"].rsplit("=", 1)[1])
    kind = "rejected" if rejected else "approved"
    sha_label = "Exact rejected SHA" if rejected else "Exact reviewed SHA"
    return _issue(
        number,
        f"exact-head-review-{kind}: pr=772 sha={SHA}",
        "\n".join(
            [
                "PR: #772",
                f"{sha_label}: `{SHA}`",
                f"Source attempt issue: #{source_number}",
                f"Source workflow run: `{source_run}`",
                f"Workflow main SHA: `{MAIN}`",
                f"Outcome: `{outcome}`",
                "Integration authority: `NONE`",
            ]
        ),
    )


def _state(issues: list[dict]) -> dict:
    return exact_head_control_state(
        issues,
        pr_number=772,
        head_sha=SHA,
        workflow_main_sha=MAIN,
        repository=REPO,
    )


def test_public_or_owner_lookalike_titles_have_zero_authority() -> None:
    fake = _attempt(1, "REJECTED", author="rnnyrgs-web")
    state = _state([fake])
    assert state["rejected"] is False
    assert state["attempt_count"] == 0


def test_rejected_source_attempt_is_terminal_even_without_secondary_receipt() -> None:
    rejected = _attempt(2, "REJECTED")
    state = _state([rejected])
    assert state["rejected"] is True
    assert state["terminal_nonretryable"] is True
    assert state["approved"] is False
    assert state["validated_rejected_attempts"] == [2]


def test_approval_requires_unique_authenticated_receipt_bound_to_source_attempt() -> None:
    approved = _attempt(3, "REVIEW_APPROVED_LEAD_INTEGRATION_REQUIRED")
    before = _state([approved])
    assert before["approved"] is False
    assert before["approval_persistence_incomplete"] is True
    assert before["terminal_nonretryable"] is True

    receipt = _receipt(4, approved, "REVIEW_APPROVED_LEAD_INTEGRATION_REQUIRED")
    after = _state([approved, receipt])
    assert after["approved"] is True
    assert after["rejected"] is False
    assert after["ambiguous_control_state"] is False
    assert after["validated_approval_receipts"] == [4]


def test_rejection_dominates_prior_authenticated_approval_forever_for_same_sha() -> None:
    approved = _attempt(5, "REVIEW_APPROVED_LEAD_INTEGRATION_REQUIRED")
    approval_receipt = _receipt(6, approved, "REVIEW_APPROVED_LEAD_INTEGRATION_REQUIRED")
    rejected = _attempt(7, "REJECTED")
    state = _state([approved, approval_receipt, rejected])
    assert state["rejected"] is True
    assert state["approved"] is False
    assert state["terminal_precedence"] == "REJECTION_DOMINATES_APPROVAL"


def test_wait_is_counted_but_remains_retryable() -> None:
    wait = _attempt(8, "WAIT_RETRYABLE")
    state = _state([wait])
    assert state["attempt_count"] == 1
    assert state["terminal_nonretryable"] is False
    assert state["approved"] is False
    assert state["rejected"] is False


def test_invalid_trusted_target_control_issue_is_explicit_ambiguity_not_forgotten() -> None:
    broken = _issue(
        9,
        f"exact-head-review-approved: pr=772 sha={SHA}",
        "PR: #772\nIntegration authority: `NONE`\n",
    )
    state = _state([broken])
    assert state["approved"] is False
    assert state["ambiguous_control_state"] is True
    assert state["invalid_trusted_control_issues"] == [9]


def test_large_unrelated_history_cannot_age_out_terminal_rejection() -> None:
    unrelated = [
        _issue(i, f"ordinary issue {i}", "not control state") for i in range(1000, 1700)
    ]
    rejected = _attempt(10, "REJECTED")
    state = _state(unrelated + [rejected])
    assert state["rejected"] is True
    assert state["validated_rejected_attempts"] == [10]


def test_duplicate_issue_identity_fails_closed() -> None:
    wait = _attempt(11, "WAIT_RETRYABLE")
    with pytest.raises(ControlStateError, match="duplicate issue number"):
        _state([wait, dict(wait)])


def test_repository_mismatch_cannot_authenticate_control_state() -> None:
    rejected = _attempt(12, "REJECTED")
    rejected["repository_url"] = "https://api.github.com/repos/other/repo"
    state = _state([rejected])
    assert state["rejected"] is False
    assert state["ambiguous_control_state"] is True
