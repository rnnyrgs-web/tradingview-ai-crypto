from __future__ import annotations

import json
import sys

import pytest

from orchestration.exact_head_control_state import (
    ControlStateError,
    exact_head_control_state,
    main,
)


REPO = "rnnyrgs-web/tradingview-ai-crypto"
PR = 606
SHA = "a" * 40
MAIN = "b" * 40
BOT = "github-actions[bot]"


def _real_api_attempt(*, repository_url: str, include_body_repository: bool) -> dict[str, object]:
    run = 9001
    body_lines = []
    if include_body_repository:
        body_lines.append(f"Repository: `{REPO}`")
    body_lines.extend(
        [
            f"PR: #{PR}",
            "Candidate branch: `agent/test`",
            f"Exact reviewed SHA: `{SHA}`",
            "Exact-head Security and Reliability run: `12345`",
            f"Workflow run: `{run}`",
            f"Workflow main SHA: `{MAIN}`",
            "Outcome: `REJECTED`",
            "Integration authority: `NONE`",
        ]
    )
    return {
        "number": 41,
        "title": f"exact-head-review-attempt: pr={PR} sha={SHA} run={run}",
        "body": "\n".join(body_lines),
        "user": {"login": BOT},
        "repository_url": repository_url,
    }


def test_cli_uses_github_repository_identity_when_flag_is_omitted(
    tmp_path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    issues = tmp_path / "issues.json"
    issues.write_text("[]", encoding="utf-8")
    monkeypatch.setenv("GITHUB_REPOSITORY", REPO)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "exact_head_control_state",
            "--issues",
            str(issues),
            "--pr-number",
            str(PR),
            "--head-sha",
            SHA,
            "--workflow-main-sha",
            MAIN,
        ],
    )

    assert main() == 0
    state = json.loads(capsys.readouterr().out)
    assert state["repository"] == REPO


def test_cli_rejects_explicit_repository_that_disagrees_with_github_runtime(
    tmp_path, monkeypatch: pytest.MonkeyPatch
) -> None:
    issues = tmp_path / "issues.json"
    issues.write_text("[]", encoding="utf-8")
    monkeypatch.setenv("GITHUB_REPOSITORY", REPO)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "exact_head_control_state",
            "--issues",
            str(issues),
            "--pr-number",
            str(PR),
            "--head-sha",
            SHA,
            "--workflow-main-sha",
            MAIN,
            "--repository",
            "other/repo",
        ],
    )

    with pytest.raises(ControlStateError, match="must match GITHUB_REPOSITORY"):
        main()


def test_real_github_issue_transport_binds_legacy_body_without_repository_line() -> None:
    issue = _real_api_attempt(
        repository_url=f"https://api.github.com/repos/{REPO}",
        include_body_repository=False,
    )
    state = exact_head_control_state(
        [issue],
        pr_number=PR,
        head_sha=SHA,
        workflow_main_sha=MAIN,
        repository=REPO,
    )

    assert state["rejected"] is True
    assert state["validated_rejected_attempts"] == [41]


def test_real_github_issue_transport_rejects_cross_repository_transplant() -> None:
    issue = _real_api_attempt(
        repository_url="https://api.github.com/repos/other/repo",
        include_body_repository=False,
    )
    state = exact_head_control_state(
        [issue],
        pr_number=PR,
        head_sha=SHA,
        workflow_main_sha=MAIN,
        repository=REPO,
    )

    assert state["rejected"] is False
    assert state["attempt_count"] == 0


def test_real_github_transport_and_conflicting_body_binding_fail_closed() -> None:
    issue = _real_api_attempt(
        repository_url=f"https://api.github.com/repos/{REPO}",
        include_body_repository=True,
    )
    issue["body"] = str(issue["body"]).replace(
        f"Repository: `{REPO}`",
        "Repository: `other/repo`",
    )
    state = exact_head_control_state(
        [issue],
        pr_number=PR,
        head_sha=SHA,
        workflow_main_sha=MAIN,
        repository=REPO,
    )

    assert state["rejected"] is False
    assert state["attempt_count"] == 0
