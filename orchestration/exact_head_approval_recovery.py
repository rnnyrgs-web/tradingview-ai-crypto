from __future__ import annotations

import argparse
import json
import re
from pathlib import Path
from typing import Any, Iterable

from orchestration.exact_head_control_state import (
    APPROVED_OUTCOMES,
    ControlStateError,
    TRUSTED_CONTROL_AUTHOR,
    exact_head_control_state,
)

_ATTEMPT_TITLE_RE = re.compile(
    r"^exact-head-review-attempt: pr=(?P<pr>[0-9]+) "
    r"sha=(?P<sha>[0-9a-f]{40}) run=(?P<run>[0-9]+)$"
)


def _single_body_value(body: str, pattern: re.Pattern[str], field: str) -> str:
    matches = [
        match.group("value")
        for line in body.splitlines()
        if (match := pattern.fullmatch(line.strip()))
    ]
    if len(matches) != 1:
        raise ControlStateError(f"source attempt must contain exactly one {field}")
    return matches[0]


def _issue_number(issue: dict[str, Any]) -> int | None:
    value = issue.get("number")
    if isinstance(value, bool):
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def _issue_author(issue: dict[str, Any]) -> str:
    user = issue.get("user")
    return str(user.get("login") or "") if isinstance(user, dict) else ""


def build_approval_recovery_receipt(
    issues: Iterable[dict[str, Any]],
    *,
    pr_number: int,
    head_sha: str,
    workflow_main_sha: str,
    repository: str,
    source_issue_number: int,
) -> dict[str, Any]:
    """Build a receipt for one already-finalized approved source attempt.

    This function never runs a reviewer and never turns an unapproved scientific
    judgment into an approval. It only repairs the secondary receipt-persistence
    step after the trusted review workflow has already durably finalized exactly
    one current-context source attempt as approved.
    """

    issue_list = [issue for issue in issues if isinstance(issue, dict)]
    state = exact_head_control_state(
        issue_list,
        pr_number=pr_number,
        head_sha=head_sha,
        workflow_main_sha=workflow_main_sha,
        repository=repository,
    )

    if state["rejected"]:
        raise ControlStateError("rejection dominates; approval receipt recovery forbidden")
    if state["interrupted"]:
        raise ControlStateError("interrupted review attempt makes recovery forbidden")
    if state["invalid_trusted_control_issues"]:
        raise ControlStateError("invalid trusted control evidence blocks recovery")
    if state["approved"]:
        raise ControlStateError("approval receipt already complete")
    if not state["approval_persistence_incomplete"]:
        raise ControlStateError("no incomplete current-context approval persistence to repair")
    if state["unreceipted_approved_attempts"] != [source_issue_number]:
        raise ControlStateError("recovery requires exactly the requested unreceipted approved source")
    if not state["terminal_nonretryable"]:
        raise ControlStateError("source approval must already be nonretryable before recovery")

    source = next(
        (issue for issue in issue_list if _issue_number(issue) == source_issue_number),
        None,
    )
    if source is None:
        raise ControlStateError("source attempt issue not present in authoritative snapshot")
    if _issue_author(source) != TRUSTED_CONTROL_AUTHOR or "pull_request" in source:
        raise ControlStateError("source attempt is not trusted GitHub Actions control evidence")

    title = source.get("title")
    if not isinstance(title, str):
        raise ControlStateError("source attempt title missing")
    title_match = _ATTEMPT_TITLE_RE.fullmatch(title)
    if title_match is None:
        raise ControlStateError("source attempt title malformed")
    if int(title_match.group("pr")) != pr_number or title_match.group("sha") != head_sha:
        raise ControlStateError("source attempt candidate identity mismatch")

    body = source.get("body")
    if not isinstance(body, str):
        raise ControlStateError("source attempt body missing")
    source_run = _single_body_value(
        body,
        re.compile(r"Workflow run: `(?P<value>[0-9]+)`"),
        "Workflow run",
    )
    source_main = _single_body_value(
        body,
        re.compile(r"Workflow main SHA: `(?P<value>[0-9a-f]{40})`"),
        "Workflow main SHA",
    )
    outcome = _single_body_value(
        body,
        re.compile(r"Outcome: `(?P<value>[^`]+)`"),
        "Outcome",
    )
    authority = _single_body_value(
        body,
        re.compile(r"Integration authority: `(?P<value>[^`]+)`"),
        "Integration authority",
    )

    if source_run != title_match.group("run"):
        raise ControlStateError("source attempt workflow-run mismatch")
    if source_main != workflow_main_sha:
        raise ControlStateError(
            "historical approval cannot be recovered as current integration authority"
        )
    if outcome not in APPROVED_OUTCOMES:
        raise ControlStateError("source attempt is not a finalized approved outcome")
    if authority != "NONE":
        raise ControlStateError("source attempt carries forbidden integration authority")

    receipt_title = f"exact-head-review-approved: pr={pr_number} sha={head_sha}"
    receipt_body = "\n".join(
        [
            f"Repository: `{repository}`",
            f"PR: #{pr_number}",
            f"Exact reviewed SHA: `{head_sha}`",
            f"Source attempt issue: #{source_issue_number}",
            f"Source workflow run: `{source_run}`",
            f"Workflow main SHA: `{source_main}`",
            f"Outcome: `{outcome}`",
            "Integration authority: `NONE`",
            "",
            "Deterministic receipt-persistence recovery only. No reviewer was rerun,",
            "no scientific judgment changed, and this receipt grants no merge authority.",
        ]
    ) + "\n"

    return {
        "receipt_title": receipt_title,
        "receipt_body": receipt_body,
        "source_issue": source_issue_number,
        "source_run": int(source_run),
        "outcome": outcome,
        "workflow_main_sha": source_main,
        "integration_authority": "NONE",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--issues", required=True)
    parser.add_argument("--pr-number", required=True, type=int)
    parser.add_argument("--head-sha", required=True)
    parser.add_argument("--workflow-main-sha", required=True)
    parser.add_argument("--repository", required=True)
    parser.add_argument("--source-issue", required=True, type=int)
    parser.add_argument("--output", required=True)
    args = parser.parse_args()

    data = json.loads(Path(args.issues).read_text(encoding="utf-8"))
    if not isinstance(data, list):
        raise ControlStateError("issues input must be a JSON array")
    receipt = build_approval_recovery_receipt(
        data,
        pr_number=args.pr_number,
        head_sha=args.head_sha,
        workflow_main_sha=args.workflow_main_sha,
        repository=args.repository,
        source_issue_number=args.source_issue,
    )
    Path(args.output).write_text(
        json.dumps(receipt, sort_keys=True, indent=2) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
