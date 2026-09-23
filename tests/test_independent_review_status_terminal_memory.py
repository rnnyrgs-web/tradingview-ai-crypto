from __future__ import annotations

from pathlib import Path


WORKFLOW = Path(".github/workflows/exact_head_independent_review.yml")


def _workflow_text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_merge_critical_status_does_not_use_bounded_title_only_control_memory() -> None:
    """A terminal exact-head rejection must never age out of review memory.

    The independent-review status is intended to become merge-critical.  A fixed-size
    issue listing plus title-prefix matching can forget an older rejection once enough
    unrelated control issues exist, allowing reviewer shopping on the same SHA.
    """

    text = _workflow_text()
    assert 'gh issue list --repo "$GITHUB_REPOSITORY" --state all --limit 100 --json title' not in text
    assert "orchestration.exact_head_control_state" in text


def test_success_status_requires_authenticated_terminal_control_state() -> None:
    """Provider-local approval text alone may not mint a merge-critical success.

    Before writing success, the workflow must re-read authenticated, fully paginated
    exact-{repo,PR,SHA} durable state so any validated rejection dominates approval or
    WAIT forever for that SHA.
    """

    text = _workflow_text()
    assert 'REVIEW_APPROVED_*)\n              STATUS_STATE="success"' not in text
    assert "exact_head_control_state" in text
    assert "rejection" in text.lower()
