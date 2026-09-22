from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from typing import Any, Iterable

TRUSTED_CONTROL_AUTHOR = "github-actions[bot]"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
_REPOSITORY_RE = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
_ATTEMPT_TITLE_RE = re.compile(
    r"^exact-head-review-attempt: pr=(?P<pr>[0-9]+) sha=(?P<sha>[0-9a-f]{40}) run=(?P<run>[0-9]+)$"
)
_APPROVAL_TITLE_RE = re.compile(
    r"^exact-head-review-approved: pr=(?P<pr>[0-9]+) sha=(?P<sha>[0-9a-f]{40})$"
)
_REJECTION_TITLE_RE = re.compile(
    r"^exact-head-review-rejected: pr=(?P<pr>[0-9]+) sha=(?P<sha>[0-9a-f]{40})$"
)

APPROVED_OUTCOMES = {
    "REVIEW_APPROVED_LEAD_INTEGRATION_REQUIRED",
    "REVIEW_APPROVED_PROTECTED_LEAD_INTEGRATION_REQUIRED",
}
ATTEMPT_OUTCOMES = {
    "STARTED",
    "WAIT_RETRYABLE",
    "FAILED",
    "REJECTED",
    *APPROVED_OUTCOMES,
}


class ControlStateError(ValueError):
    """Control-plane evidence is malformed or cannot be interpreted safely."""


def _author(issue: dict[str, Any]) -> str:
    user = issue.get("user")
    if isinstance(user, dict):
        return str(user.get("login") or "")
    author = issue.get("author")
    if isinstance(author, dict):
        return str(author.get("login") or "")
    return ""


def _body(issue: dict[str, Any]) -> str:
    value = issue.get("body")
    return value if isinstance(value, str) else ""


def _single_match(body: str, pattern: re.Pattern[str]) -> re.Match[str] | None:
    matches = [match for line in body.splitlines() if (match := pattern.fullmatch(line.strip()))]
    if len(matches) != 1:
        return None
    return matches[0]


def _trusted(issue: dict[str, Any]) -> bool:
    # Repository administrators can rewrite/delete GitHub state. That is the
    # explicit trusted control-plane boundary; public/owner-authored lookalikes
    # are not receipts. Future changes to this validator themselves must pass the
    # exact-head review gate before becoming canonical main.
    return _author(issue) == TRUSTED_CONTROL_AUTHOR and "pull_request" not in issue


def _matching_control_kind(
    issue: dict[str, Any], *, pr_number: int, head_sha: str
) -> str | None:
    """Return the trusted exact-head control title kind, independent of body validity.

    This is deliberately broader than validation. A trusted bot issue whose title
    claims authority for the target PR/SHA but whose body cannot satisfy the new
    structured contract must be surfaced as an explicit migration/integrity
    blocker rather than silently disappearing from history.
    """

    if not _trusted(issue):
        return None
    title = issue.get("title")
    if not isinstance(title, str):
        return None
    for kind, pattern in (
        ("attempt", _ATTEMPT_TITLE_RE),
        ("approval", _APPROVAL_TITLE_RE),
        ("rejection", _REJECTION_TITLE_RE),
    ):
        match = pattern.fullmatch(title)
        if match is None:
            continue
        if int(match.group("pr")) == pr_number and match.group("sha") == head_sha:
            return kind
    return None


def _validate_identity_inputs(
    pr_number: int,
    head_sha: str,
    workflow_main_sha: str,
    repository: str,
) -> None:
    if isinstance(pr_number, bool) or not isinstance(pr_number, int) or pr_number <= 0:
        raise ControlStateError("pr_number must be a positive integer")
    if not isinstance(head_sha, str) or _SHA_RE.fullmatch(head_sha) is None:
        raise ControlStateError("head_sha must be an exact lowercase 40-character SHA")
    if not isinstance(workflow_main_sha, str) or _SHA_RE.fullmatch(workflow_main_sha) is None:
        raise ControlStateError("workflow_main_sha must be an exact lowercase 40-character SHA")
    if not isinstance(repository, str) or _REPOSITORY_RE.fullmatch(repository) is None:
        raise ControlStateError("repository must be an exact owner/name identity")


def _issue_number(issue: dict[str, Any]) -> int | None:
    try:
        number = int(issue["number"])
    except (KeyError, TypeError, ValueError):
        return None
    return number if number > 0 else None


def _unique_issue_list(issues: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """Fail closed on pagination/race artifacts that duplicate an issue identity.

    GitHub issue numbers are unique repository identities. Seeing the same positive
    issue number twice in one purported authoritative snapshot means the snapshot
    is not safe to reason from, even if the duplicate bytes happen to agree.
    """

    output: list[dict[str, Any]] = []
    seen: set[int] = set()
    for issue in issues:
        if not isinstance(issue, dict):
            continue
        number = _issue_number(issue)
        if number is None:
            continue
        if number in seen:
            raise ControlStateError(f"duplicate issue number in control snapshot: {number}")
        seen.add(number)
        output.append(issue)
    return output


def _repository_match(issue: dict[str, Any], body: str, repository: str) -> bool:
    """Bind evidence to the repository without breaking pre-binding receipts.

    Real GitHub issue snapshots carry an authoritative ``repository_url``. Use
    that transport identity first so receipts created before the explicit body
    ``Repository:`` line existed remain auditable rather than silently
    disappearing from terminal memory. Synthetic/unit fixtures without an API
    repository URL must still provide the explicit body binding. If a real issue
    also carries the body binding, it must agree exactly; duplicate/tampered
    body bindings fail closed.
    """

    pattern = re.compile(r"Repository: `(?P<value>[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+)`")
    body_matches = [match for line in body.splitlines() if (match := pattern.fullmatch(line.strip()))]
    if len(body_matches) > 1:
        return False
    if body_matches and body_matches[0].group("value") != repository:
        return False

    repository_url = issue.get("repository_url")
    if isinstance(repository_url, str) and repository_url:
        return repository_url == f"https://api.github.com/repos/{repository}"

    return len(body_matches) == 1


def _attempt_record(
    issue: dict[str, Any],
    *,
    pr_number: int,
    head_sha: str,
    workflow_main_sha: str,
    repository: str,
) -> dict[str, Any] | None:
    if not _trusted(issue):
        return None
    title = issue.get("title")
    if not isinstance(title, str):
        return None
    title_match = _ATTEMPT_TITLE_RE.fullmatch(title)
    if title_match is None:
        return None
    if int(title_match.group("pr")) != pr_number or title_match.group("sha") != head_sha:
        return None

    body = _body(issue)
    if not _repository_match(issue, body, repository):
        return None
    pr_match = _single_match(body, re.compile(r"PR: #(?P<value>[0-9]+)"))
    sha_match = _single_match(body, re.compile(r"Exact reviewed SHA: `(?P<value>[0-9a-f]{40})`"))
    run_match = _single_match(body, re.compile(r"Workflow run: `(?P<value>[0-9]+)`"))
    main_match = _single_match(body, re.compile(r"Workflow main SHA: `(?P<value>[0-9a-f]{40})`"))
    outcome_match = _single_match(body, re.compile(r"Outcome: `(?P<value>[^`]+)`"))
    authority_match = _single_match(body, re.compile(r"Integration authority: `(?P<value>[^`]+)`"))
    required = (pr_match, sha_match, run_match, main_match, outcome_match, authority_match)
    if any(match is None for match in required):
        return None
    assert pr_match and sha_match and run_match and main_match and outcome_match and authority_match
    if int(pr_match.group("value")) != pr_number:
        return None
    if sha_match.group("value") != head_sha:
        return None
    if run_match.group("value") != title_match.group("run"):
        return None
    # The source attempt's reviewer-main SHA is durable audit provenance. It is
    # intentionally not required to equal the *current* reviewer-main SHA: an
    # unrelated canonical-main advance must never erase rejection/interruption/
    # approval history for an unchanged candidate PR/SHA.
    recorded_main_sha = main_match.group("value")
    outcome = outcome_match.group("value")
    if outcome not in ATTEMPT_OUTCOMES:
        return None
    if authority_match.group("value") != "NONE":
        return None
    number = _issue_number(issue)
    if number is None:
        return None
    return {
        "number": number,
        "run": int(title_match.group("run")),
        "workflow_main_sha": recorded_main_sha,
        "repository": repository,
        "outcome": outcome,
    }


def _receipt_source(
    issue: dict[str, Any],
    *,
    title_re: re.Pattern[str],
    sha_label: str,
    allowed_outcomes: set[str],
    pr_number: int,
    head_sha: str,
    workflow_main_sha: str,
    repository: str,
) -> tuple[int, int, str, str] | None:
    if not _trusted(issue):
        return None
    title = issue.get("title")
    if not isinstance(title, str):
        return None
    match = title_re.fullmatch(title)
    if match is None or int(match.group("pr")) != pr_number or match.group("sha") != head_sha:
        return None

    body = _body(issue)
    if not _repository_match(issue, body, repository):
        return None
    pr_match = _single_match(body, re.compile(r"PR: #(?P<value>[0-9]+)"))
    sha_match = _single_match(body, re.compile(rf"{re.escape(sha_label)}: `(?P<value>[0-9a-f]{{40}})`"))
    source_match = _single_match(body, re.compile(r"Source attempt issue: #(?P<value>[0-9]+)"))
    source_run_match = _single_match(body, re.compile(r"Source workflow run: `(?P<value>[0-9]+)`"))
    main_match = _single_match(body, re.compile(r"Workflow main SHA: `(?P<value>[0-9a-f]{40})`"))
    outcome_match = _single_match(body, re.compile(r"Outcome: `(?P<value>[^`]+)`"))
    authority_match = _single_match(body, re.compile(r"Integration authority: `(?P<value>[^`]+)`"))
    required = (
        pr_match,
        sha_match,
        source_match,
        source_run_match,
        main_match,
        outcome_match,
        authority_match,
    )
    if any(value is None for value in required):
        return None
    assert pr_match and sha_match and source_match and source_run_match and main_match
    assert outcome_match and authority_match
    if int(pr_match.group("value")) != pr_number or sha_match.group("value") != head_sha:
        return None
    recorded_main_sha = main_match.group("value")
    outcome = outcome_match.group("value")
    if outcome not in allowed_outcomes or authority_match.group("value") != "NONE":
        return None
    return (
        int(source_match.group("value")),
        int(source_run_match.group("value")),
        outcome,
        recorded_main_sha,
    )


def exact_head_control_state(
    issues: Iterable[dict[str, Any]],
    *,
    pr_number: int,
    head_sha: str,
    workflow_main_sha: str,
    repository: str,
) -> dict[str, Any]:
    _validate_identity_inputs(pr_number, head_sha, workflow_main_sha, repository)
    issue_list = _unique_issue_list(issues)

    claimed_control_issues: dict[int, str] = {}
    for issue in issue_list:
        kind = _matching_control_kind(issue, pr_number=pr_number, head_sha=head_sha)
        number = _issue_number(issue)
        if kind is not None and number is not None:
            claimed_control_issues[number] = kind

    attempts: dict[int, dict[str, Any]] = {}
    for issue in issue_list:
        record = _attempt_record(
            issue,
            pr_number=pr_number,
            head_sha=head_sha,
            workflow_main_sha=workflow_main_sha,
            repository=repository,
        )
        if record is not None:
            attempts[record["number"]] = record

    approved_attempts = sorted(
        number for number, record in attempts.items() if record["outcome"] in APPROVED_OUTCOMES
    )
    rejected_attempts = sorted(
        number for number, record in attempts.items() if record["outcome"] == "REJECTED"
    )
    interrupted_attempts = sorted(
        number for number, record in attempts.items() if record["outcome"] == "STARTED"
    )

    approval_receipts: list[int] = []
    approval_receipt_sources: list[int] = []
    rejection_receipts: list[int] = []
    for issue in issue_list:
        issue_number = _issue_number(issue)
        if issue_number is None:
            continue

        approval_source = _receipt_source(
            issue,
            title_re=_APPROVAL_TITLE_RE,
            sha_label="Exact reviewed SHA",
            allowed_outcomes=APPROVED_OUTCOMES,
            pr_number=pr_number,
            head_sha=head_sha,
            workflow_main_sha=workflow_main_sha,
            repository=repository,
        )
        if approval_source is not None:
            source_issue, source_run, outcome, receipt_main_sha = approval_source
            source = attempts.get(source_issue)
            if (
                source is not None
                and source["run"] == source_run
                and source["outcome"] == outcome
                and source["outcome"] in APPROVED_OUTCOMES
                and source["workflow_main_sha"] == receipt_main_sha
            ):
                approval_receipts.append(issue_number)
                approval_receipt_sources.append(source_issue)

        rejection_source = _receipt_source(
            issue,
            title_re=_REJECTION_TITLE_RE,
            sha_label="Exact rejected SHA",
            allowed_outcomes={"REJECTED"},
            pr_number=pr_number,
            head_sha=head_sha,
            workflow_main_sha=workflow_main_sha,
            repository=repository,
        )
        if rejection_source is not None:
            source_issue, source_run, outcome, receipt_main_sha = rejection_source
            source = attempts.get(source_issue)
            if (
                source is not None
                and source["run"] == source_run
                and source["outcome"] == outcome == "REJECTED"
                and source["workflow_main_sha"] == receipt_main_sha
            ):
                rejection_receipts.append(issue_number)

    approval_receipts.sort()
    approval_receipt_sources.sort()
    rejection_receipts.sort()
    validated_control_issue_numbers = set(attempts) | set(approval_receipts) | set(rejection_receipts)
    invalid_trusted_control_issues = sorted(
        number for number in claimed_control_issues if number not in validated_control_issue_numbers
    )

    rejected = bool(rejected_attempts or rejection_receipts)
    interrupted = bool(interrupted_attempts)
    receipted_approved_attempts = sorted(set(approval_receipt_sources))
    unreceipted_approved_attempts = sorted(
        set(approved_attempts) - set(receipted_approved_attempts)
    )
    multiple_approved_attempts = len(approved_attempts) > 1
    approval_persistence_incomplete = bool(unreceipted_approved_attempts)
    ambiguous = (
        interrupted
        or approval_persistence_incomplete
        or multiple_approved_attempts
        or len(approval_receipts) > 1
        or len(rejection_receipts) > 1
        or bool(invalid_trusted_control_issues)
    )
    approved = (
        len(approved_attempts) == 1
        and len(approval_receipts) == 1
        and receipted_approved_attempts == approved_attempts
        and not rejected
        and not interrupted
        and not ambiguous
    )
    # Any completed scientific approval attempt is non-retryable even if its
    # secondary approval receipt is temporarily invisible or failed to persist.
    # That state can become approved later if the exact bound receipt appears,
    # but the expensive scientific reviewers must never be invoked again merely
    # to repair control-plane persistence.
    terminal_nonretryable = bool(rejected or interrupted or approved_attempts)

    return {
        "control_state_schema_version": 4,
        "approved": approved,
        "rejected": rejected,
        "interrupted": interrupted,
        "approval_persistence_incomplete": approval_persistence_incomplete,
        "terminal_nonretryable": terminal_nonretryable,
        "ambiguous_control_state": ambiguous,
        "attempt_count": len(attempts),
        "validated_attempts": sorted(attempts),
        "validated_approved_attempts": approved_attempts,
        "validated_rejected_attempts": rejected_attempts,
        "validated_interrupted_attempts": interrupted_attempts,
        "validated_approval_receipts": approval_receipts,
        "validated_approval_receipt_sources": receipted_approved_attempts,
        "unreceipted_approved_attempts": unreceipted_approved_attempts,
        "validated_rejection_receipts": rejection_receipts,
        "invalid_trusted_control_issues": invalid_trusted_control_issues,
        "claimed_control_issue_kinds": {
            str(number): claimed_control_issues[number] for number in sorted(claimed_control_issues)
        },
        "terminal_precedence": "REJECTION_DOMINATES_APPROVAL",
        "legacy_unvalidated_control_is_blocking": True,
        "workflow_main_sha": workflow_main_sha,
        "repository": repository,
        "trusted_control_author": TRUSTED_CONTROL_AUTHOR,
        "admin_mutation_is_trusted_boundary": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issues", required=True)
    parser.add_argument("--pr-number", required=True, type=int)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--workflow-main-sha", required=True)
    parser.add_argument("--repository")
    args = parser.parse_args()

    environment_repository = os.environ.get("GITHUB_REPOSITORY")
    if args.repository and environment_repository and args.repository != environment_repository:
        raise ControlStateError("--repository must match GITHUB_REPOSITORY when both are present")
    repository = args.repository or environment_repository
    if not repository:
        raise ControlStateError("repository identity is required via --repository or GITHUB_REPOSITORY")

    data = json.loads(Path(args.issues).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ControlStateError("issues input must be a JSON array")
    state = exact_head_control_state(
        data,
        pr_number=args.pr_number,
        head_sha=args.head_sha,
        workflow_main_sha=args.workflow_main_sha,
        repository=repository,
    )
    print(json.dumps(state, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())