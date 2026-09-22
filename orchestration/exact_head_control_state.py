from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable

TRUSTED_CONTROL_AUTHOR = "github-actions[bot]"
_SHA_RE = re.compile(r"^[0-9a-f]{40}$")
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


def _validate_identity_inputs(pr_number: int, head_sha: str, workflow_main_sha: str) -> None:
    if isinstance(pr_number, bool) or not isinstance(pr_number, int) or pr_number <= 0:
        raise ControlStateError("pr_number must be a positive integer")
    if not isinstance(head_sha, str) or _SHA_RE.fullmatch(head_sha) is None:
        raise ControlStateError("head_sha must be an exact lowercase 40-character SHA")
    if not isinstance(workflow_main_sha, str) or _SHA_RE.fullmatch(workflow_main_sha) is None:
        raise ControlStateError("workflow_main_sha must be an exact lowercase 40-character SHA")


def _attempt_record(
    issue: dict[str, Any],
    *,
    pr_number: int,
    head_sha: str,
    workflow_main_sha: str,
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
    if main_match.group("value") != workflow_main_sha:
        return None
    outcome = outcome_match.group("value")
    if outcome not in ATTEMPT_OUTCOMES:
        return None
    if authority_match.group("value") != "NONE":
        return None
    try:
        number = int(issue["number"])
    except (KeyError, TypeError, ValueError):
        return None
    if number <= 0:
        return None
    return {
        "number": number,
        "run": int(title_match.group("run")),
        "workflow_main_sha": workflow_main_sha,
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
) -> tuple[int, int, str] | None:
    if not _trusted(issue):
        return None
    title = issue.get("title")
    if not isinstance(title, str):
        return None
    match = title_re.fullmatch(title)
    if match is None or int(match.group("pr")) != pr_number or match.group("sha") != head_sha:
        return None

    body = _body(issue)
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
    if main_match.group("value") != workflow_main_sha:
        return None
    outcome = outcome_match.group("value")
    if outcome not in allowed_outcomes or authority_match.group("value") != "NONE":
        return None
    return int(source_match.group("value")), int(source_run_match.group("value")), outcome


def exact_head_control_state(
    issues: Iterable[dict[str, Any]],
    *,
    pr_number: int,
    head_sha: str,
    workflow_main_sha: str,
) -> dict[str, Any]:
    _validate_identity_inputs(pr_number, head_sha, workflow_main_sha)
    issue_list = [issue for issue in issues if isinstance(issue, dict)]

    attempts: dict[int, dict[str, Any]] = {}
    for issue in issue_list:
        record = _attempt_record(
            issue,
            pr_number=pr_number,
            head_sha=head_sha,
            workflow_main_sha=workflow_main_sha,
        )
        if record is not None:
            attempts[record["number"]] = record

    approved_attempts = sorted(
        number for number, record in attempts.items() if record["outcome"] in APPROVED_OUTCOMES
    )
    rejected_attempts = sorted(
        number for number, record in attempts.items() if record["outcome"] == "REJECTED"
    )

    approval_receipts: list[int] = []
    rejection_receipts: list[int] = []
    for issue in issue_list:
        try:
            issue_number = int(issue["number"])
        except (KeyError, TypeError, ValueError):
            continue
        if issue_number <= 0:
            continue

        approval_source = _receipt_source(
            issue,
            title_re=_APPROVAL_TITLE_RE,
            sha_label="Exact reviewed SHA",
            allowed_outcomes=APPROVED_OUTCOMES,
            pr_number=pr_number,
            head_sha=head_sha,
            workflow_main_sha=workflow_main_sha,
        )
        if approval_source is not None:
            source_issue, source_run, outcome = approval_source
            source = attempts.get(source_issue)
            if (
                source is not None
                and issue_number > source_issue
                and source["run"] == source_run
                and source["outcome"] == outcome
                and source["outcome"] in APPROVED_OUTCOMES
            ):
                approval_receipts.append(issue_number)

        rejection_source = _receipt_source(
            issue,
            title_re=_REJECTION_TITLE_RE,
            sha_label="Exact rejected SHA",
            allowed_outcomes={"REJECTED"},
            pr_number=pr_number,
            head_sha=head_sha,
            workflow_main_sha=workflow_main_sha,
        )
        if rejection_source is not None:
            source_issue, source_run, outcome = rejection_source
            source = attempts.get(source_issue)
            if (
                source is not None
                and issue_number > source_issue
                and source["run"] == source_run
                and source["outcome"] == outcome == "REJECTED"
            ):
                rejection_receipts.append(issue_number)

    approval_receipts.sort()
    rejection_receipts.sort()
    rejected = bool(rejected_attempts or rejection_receipts)
    ambiguous = len(approval_receipts) > 1 or len(rejection_receipts) > 1
    approved = len(approval_receipts) == 1 and not rejected and not ambiguous

    return {
        "approved": approved,
        "rejected": rejected,
        "ambiguous_control_state": ambiguous,
        "attempt_count": len(attempts),
        "validated_attempts": sorted(attempts),
        "validated_approved_attempts": approved_attempts,
        "validated_rejected_attempts": rejected_attempts,
        "validated_approval_receipts": approval_receipts,
        "validated_rejection_receipts": rejection_receipts,
        "workflow_main_sha": workflow_main_sha,
        "trusted_control_author": TRUSTED_CONTROL_AUTHOR,
        "admin_mutation_is_trusted_boundary": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issues", required=True)
    parser.add_argument("--pr-number", required=True, type=int)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--workflow-main-sha", required=True)
    args = parser.parse_args()

    data = json.loads(Path(args.issues).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ControlStateError("issues input must be a JSON array")
    state = exact_head_control_state(
        data,
        pr_number=args.pr_number,
        head_sha=args.head_sha,
        workflow_main_sha=args.workflow_main_sha,
    )
    print(json.dumps(state, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
