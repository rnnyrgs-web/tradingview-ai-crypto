from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "exact_head_independent_review.yml"
REVIEWER = ROOT / "orchestration" / "exact_head_review.py"


def test_temporarily_unavailable_is_only_a_nonverdict_and_cannot_mint_approval() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    reviewer = REVIEWER.read_text(encoding="utf-8")

    # The exact bounded non-verdict phrase emitted by the reviewer runtime must be
    # consumed by the canonical workflow's controlled-WAIT classifier.
    assert "temporarily unavailable:" in reviewer
    assert "temporarily unavailable|overloaded" in workflow

    # A WAIT or an available valid rejection must skip both the unanimity gate and
    # approval-receipt creation. Tightening this gate must not weaken WAIT safety.
    approval_gate = (
        "steps.select.outputs.pr_number != '' && "
        "steps.review_models.outputs.wait != 'true' && "
        "steps.review_models.outputs.rejected != 'true'"
    )
    assert (
        "name: Require all three trust-bound independent reviewers to approve\n"
        f"        if: {approval_gate}"
    ) in workflow
    assert (
        "name: Record review-only approval for exact head\n"
        f"        if: {approval_gate}"
    ) in workflow
    assert "Candidate remains **unapproved** and **unmerged**" in workflow

    # Missing one reviewer can never be substituted by the other two. Final
    # consumption now uses the trust-bound approval verifier, not a bare JSON
    # boolean, and still iterates all three concrete receipt paths.
    for path in (
        "/tmp/security-review.json",
        "/tmp/lead-review.json",
        "/tmp/claude-adversarial-review.json",
    ):
        assert path in workflow
    assert "verify-current-approval" in workflow
    assert "verify-current-receipt" in workflow
    assert "jq -e '.approve == true" not in workflow


def test_nonverdict_exception_precedes_any_output_write() -> None:
    reviewer = REVIEWER.read_text(encoding="utf-8")
    write_pos = reviewer.index("output.write_text(")
    assert reviewer.index("verdict = _claude_exact_head_verdict(") < write_pos
    assert reviewer.index("verdict = _openai_exact_head_verdict(") < write_pos
