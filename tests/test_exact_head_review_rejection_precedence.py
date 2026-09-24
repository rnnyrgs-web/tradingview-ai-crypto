from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "exact_head_independent_review.yml"


def _text() -> str:
    return WORKFLOW.read_text(encoding="utf-8")


def test_valid_independent_rejection_dominates_transient_wait() -> None:
    """A valid reject may not be hidden merely because another provider is unavailable."""

    text = _text()
    assert 'echo "rejected=true" >> "$GITHUB_OUTPUT"' in text
    assert "valid independent scientific rejection is terminal" in text

    rejection_output = text.index('echo "rejected=true" >> "$GITHUB_OUTPUT"')
    wait_output = text.index('echo "wait=true" >> "$GITHUB_OUTPUT"')
    assert rejection_output < wait_output

    # A rejected exact head must never enter either approval gate.
    assert text.count("steps.review_models.outputs.rejected != 'true'") >= 2


def test_attempt_finalizer_records_partial_valid_rejection_before_wait() -> None:
    """One authenticated valid rejection is terminal even if other reviewers have no verdict."""

    text = _text()
    expected_rejection_scan = 'any(value is not None and not value["approve"] for value in verdicts)'
    assert expected_rejection_scan in text
    assert 'all(value is not None for value in verdicts) and any(not value["approve"] for value in verdicts)' not in text

    finalizer = text.index("approved_outcome = os.environ.get")
    rejection = text.index(expected_rejection_scan, finalizer)
    controlled_wait = text.index("if controlled_wait:", finalizer)
    assert rejection < controlled_wait


def test_rejected_attempt_is_not_advertised_as_retryable() -> None:
    text = _text()
    assert "REJECTED is terminal for the exact SHA" in text
    assert "FAILED/REJECTED does not permanently blacklist the exact SHA" not in text
