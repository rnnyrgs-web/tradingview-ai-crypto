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
    # GitHub repository administrators can rewrite/delete issue state. That is a
    # trusted control-plane boundary, not something this receipt format can make
    # cryptographically immutable. Automation nevertheless rejects public-user
    # lookalikes and malformed/tampered bot receipts fail closed.
    return _author(issue) == TRUSTED_CONTROL_AUTHOR and "pull_request" not in issue


def _attempt_record(issue: dict[str, Any], *, pr_number: int, head_sha: str) -> dict[str, Any] | None:
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
    outcome_match = _single_match(body, re.compile(r"Outcome: `(?P<value>[^`]+)`"))
    authority_match = _single_match(body, re.compile(r"Integration authority: `(?P<value>[^`]+)`"))
    required = (pr_match, sha_match, run_match, outcome_match, authority_match)
    if any(match is None for match in required):
        return None
    assert pr_match and sha_match and run_match and outcome_match and authority_match
    if int(pr_match.group("value")) != pr_number:
        return None
    if sha_match.group("value") != head_sha:
        return None
    if run_match.group("value") != title_match.group("run"):
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
    return {"number": number, "run": int(title_match.group("run")), "outcome": outcome}


def _approval_receipt_valid(issue: dict[str, Any], *, pr_number: int, head_sha: str) -> bool:
    if not _trusted(issue):
        return False
    title = issue.get("title")
    if not isinstance(title, str):
        return False
    match = _APPROVAL_TITLE_RE.fullmatch(title)
    if match is None or int(match.group("pr")) != pr_number or match.group("sha") != head_sha:
        return False
    body = _body(issue)
    pr_match = _single_match(body, re.compile(r"PR: #(?P<value>[0-9]+)"))
    sha_match = _single_match(body, re.compile(r"Exact reviewed SHA: `(?P<value>[0-9a-f]{40})`"))
    outcome_match = _single_match(body, re.compile(r"Outcome: `(?P<value>[^`]+)`"))
    authority_match = _single_match(body, re.compile(r"Integration authority: `(?P<value>[^`]+)`"))
    if any(value is None for value in (pr_match, sha_match, outcome_match, authority_match)):
        return False
    assert pr_match and sha_match and outcome_match and authority_match
    return (
        int(pr_match.group("value")) == pr_number
        and sha_match.group("value") == head_sha
        and outcome_match.group("value") in APPROVED_OUTCOMES
        and authority_match.group("value") == "NONE"
    )


def _rejection_receipt_source(
    issue: dict[str, Any],
    *,
    pr_number: int,
    head_sha: str,
) -> int | None:
    if not _trusted(issue):
        return None
    title = issue.get("title")
    if not isinstance(title, str):
        return None
    match = _REJECTION_TITLE_RE.fullmatch(title)
    if match is None or int(match.group("pr")) != pr_number or match.group("sha") != head_sha:
        return None
    body = _body(issue)
    pr_match = _single_match(body, re.compile(r"PR: #(?P<value>[0-9]+)"))
    sha_match = _single_match(body, re.compile(r"Exact rejected SHA: `(?P<value>[0-9a-f]{40})`"))
    source_match = _single_match(body, re.compile(r"Source attempt issue: #(?P<value>[0-9]+)"))
    outcome_match = _single_match(body, re.compile(r"Outcome: `(?P<value>[^`]+)`"))
    authority_match = _single_match(body, re.compile(r"Integration authority: `(?P<value>[^`]+)`"))
    if any(value is None for value in (pr_match, sha_match, source_match, outcome_match, authority_match)):
        return None
    assert pr_match and sha_match and source_match and outcome_match and authority_match
    if int(pr_match.group("value")) != pr_number:
        return None
    if sha_match.group("value") != head_sha:
        return None
    if outcome_match.group("value") != "REJECTED" or authority_match.group("value") != "NONE":
        return None
    return int(source_match.group("value"))


def exact_head_control_state(
    issues: Iterable[dict[str, Any]],
    *,
    pr_number: int,
    head_sha: str,
) -> dict[str, Any]:
    if isinstance(pr_number, bool) or not isinstance(pr_number, int) or pr_number <= 0:
        raise ControlStateError("pr_number must be a positive integer")
    if not isinstance(head_sha, str) or _SHA_RE.fullmatch(head_sha) is None:
        raise ControlStateError("head_sha must be an exact lowercase 40-character SHA")

    issue_list = [issue for issue in issues if isinstance(issue, dict)]
    attempts: dict[int, dict[str, Any]] = {}
    for issue in issue_list:
        record = _attempt_record(issue, pr_number=pr_number, head_sha=head_sha)
        if record is not None:
            attempts[record["number"]] = record

    rejected_attempts = sorted(
        number for number, record in attempts.items() if record["outcome"] == "REJECTED"
    )
    approval_receipts = sorted(
        int(issue["number"])
        for issue in issue_list
        if isinstance(issue.get("number"), int)
        and _approval_receipt_valid(issue, pr_number=pr_number, head_sha=head_sha)
    )

    rejection_receipts: list[int] = []
    for issue in issue_list:
        try:
            issue_number = int(issue["number"])
        except (KeyError, TypeError, ValueError):
            continue
        source_attempt = _rejection_receipt_source(issue, pr_number=pr_number, head_sha=head_sha)
        if source_attempt is None:
            continue
        source = attempts.get(source_attempt)
        if source is None or source["outcome"] != "REJECTED":
            continue
        rejection_receipts.append(issue_number)

    rejection_receipts.sort()
    rejected = bool(rejected_attempts or rejection_receipts)
    return {
        "approved": bool(approval_receipts) and not rejected,
        "rejected": rejected,
        "attempt_count": len(attempts),
        "validated_attempts": sorted(attempts),
        "validated_rejected_attempts": rejected_attempts,
        "validated_approval_receipts": approval_receipts,
        "validated_rejection_receipts": rejection_receipts,
        "trusted_control_author": TRUSTED_CONTROL_AUTHOR,
        "admin_mutation_is_trusted_boundary": True,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issues", required=True)
    parser.add_argument("--pr-number", required=True, type=int)
    parser.add_argument("--head-sha", required=True)
    args = parser.parse_args()

    data = json.loads(Path(args.issues).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ControlStateError("issues input must be a JSON array")
    state = exact_head_control_state(data, pr_number=args.pr_number, head_sha=args.head_sha)
    print(json.dumps(state, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
