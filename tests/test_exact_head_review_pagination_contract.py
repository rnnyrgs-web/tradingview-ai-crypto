from __future__ import annotations

from pathlib import Path


WORKFLOW = Path(".github/workflows/exact_head_independent_review.yml")
CONTROL_STATE = Path("orchestration/exact_head_control_state.py")


def test_control_issue_pagination_is_append_stable() -> None:
    """New unrelated issues must not shift old terminal receipts across pages.

    The review workflow consumes GitHub's paginated Issues API as durable control
    state. Descending creation order is unsafe for a long-running pagination:
    another repository workflow can append an unrelated issue while pages are
    being traversed and shift an older item across a page boundary. The control
    traversal therefore freezes ascending creation order. This is only a
    pagination-stability rule; issue timestamps/numbers have zero scientific or
    approval authority.
    """

    text = WORKFLOW.read_text(encoding="utf-8")
    required_suffix = "&per_page=100&sort=created&direction=asc"

    issue_api_lines = [
        line.strip()
        for line in text.splitlines()
        if "gh api --paginate" in line and "/issues?state=" in line
    ]
    assert issue_api_lines, "exact-head review must enumerate durable issue control state"
    assert all(required_suffix in line for line in issue_api_lines), issue_api_lines


def test_issue_timestamps_are_not_review_authority() -> None:
    """Traversal timestamps must never become scientific precedence."""

    state_code = CONTROL_STATE.read_text(encoding="utf-8").lower()
    assert "created_at" not in state_code
    assert "updated_at" not in state_code

    # Exact source/run/body bindings, not issue chronology, define receipt
    # authority. The existing control-state regression suite separately proves
    # that a valid receipt can precede its source issue number without changing
    # the verdict, so issue-number order is not scientific causality either.
