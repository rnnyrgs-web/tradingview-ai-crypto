from __future__ import annotations

from orchestration.exact_head_control_state import exact_head_control_state


SHA = "a" * 40
MAIN = "b" * 40
PR = 606
BOT = "github-actions[bot]"
APPROVED = "REVIEW_APPROVED_LEAD_INTEGRATION_REQUIRED"


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
                f"Workflow main SHA: `{MAIN}`",
                f"Outcome: `{outcome}`",
                "Integration authority: `NONE`",
            ]
        ),
        author=author,
    )


def _rejection_receipt(number: int, source_attempt: int, *, author: str = BOT, sha: str = SHA) -> dict[str, object]:
    source_run = 9000 + source_attempt
    return _issue(
        number,
        f"exact-head-review-rejected: pr={PR} sha={sha}",
        "\n".join(
            [
                f"PR: #{PR}",
                "Candidate branch: `agent/test`",
                f"Exact rejected SHA: `{sha}`",
                f"Source attempt issue: #{source_attempt}",
                f"Source workflow run: `{source_run}`",
                f"Workflow main SHA: `{MAIN}`",
                "Outcome: `REJECTED`",
                "Integration authority: `NONE`",
            ]
        ),
        author=author,
    )


def _approval_receipt(number: int, source_attempt: int, *, author: str = BOT, sha: str = SHA) -> dict[str, object]:
    source_run = 9000 + source_attempt
    return _issue(
        number,
        f"exact-head-review-approved: pr={PR} sha={sha}",
        "\n".join(
            [
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
        author=author,
    )


def _state(issues: list[dict[str, object]]) -> dict[str, object]:
    return exact_head_control_state(
        issues,
        pr_number=PR,
        head_sha=SHA,
        workflow_main_sha=MAIN,
    )


def _as_real_api_issue(issue: dict[str, object]) -> dict[str, object]:
    """Mirror the relevant shape returned by GET /repos/{owner}/{repo}/issues."""
    number = int(issue["number"])
    return {
        "url": f"https://api.github.com/repos/example/repo/issues/{number}",
        "repository_url": "https://api.github.com/repos/example/repo",
        "labels_url": f"https://api.github.com/repos/example/repo/issues/{number}/labels{{/name}}",
        "comments_url": f"https://api.github.com/repos/example/repo/issues/{number}/comments",
        "events_url": f"https://api.github.com/repos/example/repo/issues/{number}/events",
        "html_url": f"https://github.com/example/repo/issues/{number}",
        "id": 100000 + number,
        "node_id": f"I_kw_TEST_{number}",
        "number": number,
        "title": issue["title"],
        "user": {"login": BOT, "id": 41898282, "type": "Bot", "site_admin": False},
        "labels": [],
        "state": "open",
        "locked": False,
        "assignee": None,
        "assignees": [],
        "milestone": None,
        "comments": 0,
        "created_at": "2026-09-22T05:00:00Z",
        "updated_at": "2026-09-22T05:00:00Z",
        "closed_at": None,
        "author_association": "NONE",
        "active_lock_reason": None,
        "body": issue["body"],
        "reactions": {"total_count": 0},
        "timeline_url": f"https://api.github.com/repos/example/repo/issues/{number}/timeline",
        "performed_via_github_app": {"id": 15368, "slug": "github-actions"},
        "state_reason": None,
    }


def test_rejected_source_attempt_is_terminal_without_separate_receipt() -> None:
    state = _state([_attempt(11)])
    assert state["rejected"] is True
    assert state["validated_rejected_attempts"] == [11]
    assert state["validated_rejection_receipts"] == []
    assert state["attempt_count"] == 1


def test_rejection_receipt_must_bind_a_valid_rejected_source_attempt() -> None:
    rejected = _attempt(11)
    receipt = _rejection_receipt(12, 11)
    state = _state([rejected, receipt])
    assert state["rejected"] is True
    assert state["validated_rejection_receipts"] == [12]

    missing_source = _state([receipt])
    assert missing_source["validated_rejection_receipts"] == []
    assert missing_source["rejected"] is False


def test_public_or_owner_lookalikes_cannot_create_control_state() -> None:
    issues = [
        _attempt(11, author="attacker"),
        _attempt(12, author="rnnyrgs-web"),
        _rejection_receipt(13, 11, author="attacker"),
        _approval_receipt(14, 12, author="rnnyrgs-web"),
    ]
    state = _state(issues)
    assert state["attempt_count"] == 0
    assert state["rejected"] is False
    assert state["approved"] is False


def test_tampered_body_cannot_be_rescued_by_exact_title() -> None:
    issue = _attempt(11)
    issue["body"] = str(issue["body"]).replace("Integration authority: `NONE`", "Integration authority: `MERGE`")
    state = _state([issue])
    assert state["attempt_count"] == 0
    assert state["rejected"] is False


def test_duplicate_conflicting_binding_line_fails_closed() -> None:
    issue = _attempt(11)
    issue["body"] = str(issue["body"]) + f"\nExact reviewed SHA: `{'c' * 40}`\n"
    state = _state([issue])
    assert state["attempt_count"] == 0


def test_wrong_sha_or_nonterminal_outcome_does_not_create_rejection() -> None:
    other_sha = "d" * 40
    issues = [
        _attempt(11, sha=other_sha),
        _attempt(12, outcome="WAIT_RETRYABLE"),
    ]
    state = _state(issues)
    assert state["attempt_count"] == 1
    assert state["rejected"] is False


def test_wrong_workflow_main_sha_is_not_valid_control_state() -> None:
    state = exact_head_control_state(
        [_attempt(11)],
        pr_number=PR,
        head_sha=SHA,
        workflow_main_sha="c" * 40,
    )
    assert state["attempt_count"] == 0
    assert state["rejected"] is False
    assert state["approved"] is False


def test_legacy_title_only_approval_is_deliberately_not_grandfathered() -> None:
    legacy = _issue(
        21,
        f"exact-head-review-approved: pr={PR} sha={SHA}",
        f"PR: #{PR}\nExact reviewed SHA: `{SHA}`\nOutcome: `{APPROVED}`\nIntegration authority: `NONE`",
    )
    state = _state([legacy])
    assert state["approved"] is False
    assert state["validated_approval_receipts"] == []


def test_valid_approval_requires_exact_source_attempt_and_body_binding() -> None:
    source = _attempt(20, outcome=APPROVED)
    approval = _approval_receipt(21, 20)
    state = _state([source, approval])
    assert state["approved"] is True
    assert state["validated_approved_attempts"] == [20]
    assert state["validated_approval_receipts"] == [21]

    missing_source = _state([approval])
    assert missing_source["approved"] is False

    tampered = _approval_receipt(22, 20)
    tampered["body"] = str(tampered["body"]).replace(
        f"Outcome: `{APPROVED}`",
        "Outcome: `WAIT_RETRYABLE`",
    )
    state = _state([source, tampered])
    assert state["approved"] is False


def test_receipt_must_be_created_after_its_source_attempt() -> None:
    source = _attempt(20, outcome=APPROVED)
    stale_or_impossible_receipt = _approval_receipt(19, 20)
    state = _state([source, stale_or_impossible_receipt])
    assert state["validated_approval_receipts"] == []
    assert state["approved"] is False


def test_receipt_source_workflow_run_must_match_source_attempt() -> None:
    source = _attempt(20, outcome=APPROVED)
    receipt = _approval_receipt(21, 20)
    receipt["body"] = str(receipt["body"]).replace("Source workflow run: `9020`", "Source workflow run: `9999`")
    state = _state([source, receipt])
    assert state["validated_approval_receipts"] == []
    assert state["approved"] is False


def test_duplicate_valid_receipts_are_ambiguous_and_fail_closed() -> None:
    source = _attempt(20, outcome=APPROVED)
    state = _state([source, _approval_receipt(21, 20), _approval_receipt(22, 20)])
    assert state["ambiguous_control_state"] is True
    assert state["approved"] is False


def test_real_github_api_issue_shape_is_accepted_only_when_bindings_are_valid() -> None:
    source = _as_real_api_issue(_attempt(20, outcome=APPROVED))
    receipt = _as_real_api_issue(_approval_receipt(21, 20))
    state = _state([source, receipt])
    assert state["approved"] is True
    assert state["validated_attempts"] == [20]
    assert state["validated_approval_receipts"] == [21]


def test_rejection_dominates_even_a_valid_approval_receipt() -> None:
    state = _state(
        [
            _attempt(20, outcome=APPROVED),
            _approval_receipt(21, 20),
            _attempt(22),
        ]
    )
    assert state["rejected"] is True
    assert state["approved"] is False


def test_old_rejection_is_not_hidden_by_more_than_500_unrelated_issues() -> None:
    issues = [_attempt(1)]
    issues.extend(
        _issue(1000 + index, f"unrelated-{index}", "not control state")
        for index in range(750)
    )
    state = _state(issues)
    assert state["rejected"] is True
    assert state["validated_rejected_attempts"] == [1]
    assert state["attempt_count"] == 1


def test_pull_request_objects_never_count_as_control_issues() -> None:
    issue = _attempt(11)
    issue["pull_request"] = {"url": "https://api.github.com/example"}
    state = _state([issue])
    assert state["attempt_count"] == 0
    assert state["rejected"] is False
