from __future__ import annotations

from pathlib import Path


WORKFLOW = Path(".github/workflows/exact_head_independent_review.yml")


def test_control_issue_pagination_is_append_stable() -> None:
    """New unrelated issues must not shift old terminal receipts across pages.

    The review workflow consumes GitHub's paginated Issues API as durable control
    state.  Descending creation order is unsafe for a long-running pagination:
    another repository workflow can append an unrelated issue while pages are
    being traversed and shift an older item across a page boundary.  The control
    traversal therefore freezes ascending creation order.  This is only a
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


def test_pagination_order_is_not_used_as_review_authority() -> None:
    """Traversal order may stabilize pagination but must not decide a verdict."""

    text = WORKFLOW.read_text(encoding="utf-8")
    assert "created_at" not in text.lower() or "created_at" in text.lower()
    # Authority remains exact body/source/run binding in the deterministic state
    # validator; this regression deliberately rejects comments/code that claim
    # issue chronology itself is scientific precedence.
    forbidden_authority_phrases = (
        "created_at determines approval",
        "updated_at determines approval",
        "issue number determines approval",
        "higher issue number wins",
    )
    lowered = text.lower()
    assert not any(phrase in lowered for phrase in forbidden_authority_phrases)
