from __future__ import annotations

from orchestration.exact_head_control_state import exact_head_control_state


SHA = "a" * 40
PR = 606
BOT = "github-actions[bot]"


def _issue(number: int, title: str, body: str, *, author: str = BOT) -> dict[str, object]:
    return {
        "number": number,
        "title": title,
        "body": body,
        "user": {"login": author},
    }


def _attempt(number: int, *, outcome: str = "REJECTED", author: str = BOT, sha: str = SHA) -> dict[str, object]:
    run = 9000 + number
    return _issue(
        number,
        f"exact-head-review-attempt: pr={PR} sha={sha} run={run}",
        "\n".join(
            [
                f"PR: #{PR}",
                "Candidate branch: `agent/test`",
                f"Exact reviewed SHA: `{sha}`",
                "Exact-head Security and Reliability run: `12345`",
                f"Workflow run: `{run}`",
                "Workflow main SHA: `" + "b" * 40 + "`",
                f"Outcome: `{outcome}`",
                "Integration authority: `NONE`",
            ]
        ),
        author=author,
    )


def _rejection_receipt(number: int, source_attempt: int, *, author: str = BOT, sha: str = SHA) -> dict[str, object]:
    return _issue(
        number,
        f"exact-head-review-rejected: pr={PR} sha={sha}",
        "\n".join(
            [
                f"PR: #{PR}",
                "Candidate branch: `agent/test`",
                f"Exact rejected SHA: `{sha}`",
                f"Source attempt issue: #{source_attempt}",
                "Outcome: `REJECTED`",
                "Integration authority: `NONE`",
            ]
        ),
        author=author,
    )


def _approval_receipt(number: int, *, author: str = BOT, sha: str = SHA) -> dict[str, object]:
    return _issue(
        number,
        f"exact-head-review-approved: pr={PR} sha={sha}",
        "\n".join(
            [
                f"PR: #{PR}",
                "Candidate branch: `agent/test`",
                f"Exact reviewed SHA: `{sha}`",
                "Exact-head Security and Reliability run: `12345` — PASS",
                "Outcome: `REVIEW_APPROVED_LEAD_INTEGRATION_REQUIRED`",
                "Protected paths: `[]`",
                "Integration authority: `NONE`",
            ]
        ),
        author=author,
    )


def test_rejected_source_attempt_is_terminal_without_separate_receipt() -> None:
    state = exact_head_control_state([_attempt(11)], pr_number=PR, head_sha=SHA)
    assert state["rejected"] is True
    assert state["validated_rejected_attempts"] == [11]
    assert state["validated_rejection_receipts"] == []
    assert state["attempt_count"] == 1


def test_rejection_receipt_must_bind_a_valid_rejected_source_attempt() -> None:
    rejected = _attempt(11)
    receipt = _rejection_receipt(12, 11)
    state = exact_head_control_state([rejected, receipt], pr_number=PR, head_sha=SHA)
    assert state["rejected"] is True
    assert state["validated_rejection_receipts"] == [12]

    missing_source = exact_head_control_state([receipt], pr_number=PR, head_sha=SHA)
    assert missing_source["validated_rejection_receipts"] == []
    assert missing_source["rejected"] is False


def test_public_or_owner_lookalikes_cannot_create_control_state() -> None:
    issues = [
        _attempt(11, author="attacker"),
        _attempt(12, author="rnnyrgs-web"),
        _rejection_receipt(13, 11, author="attacker"),
        _approval_receipt(14, author="rnnyrgs-web"),
    ]
    state = exact_head_control_state(issues, pr_number=PR, head_sha=SHA)
    assert state["attempt_count"] == 0
    assert state["rejected"] is False
    assert state["approved"] is False


def test_tampered_body_cannot_be_rescued_by_exact_title() -> None:
    issue = _attempt(11)
    issue["body"] = str(issue["body"]).replace("Integration authority: `NONE`", "Integration authority: `MERGE`")
    state = exact_head_control_state([issue], pr_number=PR, head_sha=SHA)
    assert state["attempt_count"] == 0
    assert state["rejected"] is False


def test_duplicate_conflicting_binding_line_fails_closed() -> None:
    issue = _attempt(11)
    issue["body"] = str(issue["body"]) + f"\nExact reviewed SHA: `{'c' * 40}`\n"
    state = exact_head_control_state([issue], pr_number=PR, head_sha=SHA)
    assert state["attempt_count"] == 0


def test_wrong_sha_or_nonterminal_outcome_does_not_create_rejection() -> None:
    other_sha = "d" * 40
    issues = [
        _attempt(11, sha=other_sha),
        _attempt(12, outcome="WAIT_RETRYABLE"),
    ]
    state = exact_head_control_state(issues, pr_number=PR, head_sha=SHA)
    assert state["attempt_count"] == 1
    assert state["rejected"] is False


def test_valid_approval_requires_exact_body_binding() -> None:
    approval = _approval_receipt(21)
    state = exact_head_control_state([approval], pr_number=PR, head_sha=SHA)
    assert state["approved"] is True
    assert state["validated_approval_receipts"] == [21]

    tampered = _approval_receipt(22)
    tampered["body"] = str(tampered["body"]).replace(
        "Outcome: `REVIEW_APPROVED_LEAD_INTEGRATION_REQUIRED`",
        "Outcome: `WAIT_RETRYABLE`",
    )
    state = exact_head_control_state([tampered], pr_number=PR, head_sha=SHA)
    assert state["approved"] is False


def test_rejection_dominates_even_a_valid_approval_receipt() -> None:
    state = exact_head_control_state(
        [_approval_receipt(21), _attempt(22)],
        pr_number=PR,
        head_sha=SHA,
    )
    assert state["rejected"] is True
    assert state["approved"] is False


def test_old_rejection_is_not_hidden_by_more_than_500_unrelated_issues() -> None:
    issues = [_attempt(1)]
    issues.extend(
        _issue(1000 + index, f"unrelated-{index}", "not control state")
        for index in range(750)
    )
    state = exact_head_control_state(issues, pr_number=PR, head_sha=SHA)
    assert state["rejected"] is True
    assert state["validated_rejected_attempts"] == [1]
    assert state["attempt_count"] == 1


def test_pull_request_objects_never_count_as_control_issues() -> None:
    issue = _attempt(11)
    issue["pull_request"] = {"url": "https://api.github.com/example"}
    state = exact_head_control_state([issue], pr_number=PR, head_sha=SHA)
    assert state["attempt_count"] == 0
    assert state["rejected"] is False
