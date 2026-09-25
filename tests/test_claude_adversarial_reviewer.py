import json

import pytest

from agents.autonomous_orchestrator import (
    REQUIRED_FALSIFICATION_FINDINGS,
    REVIEWERS,
    anthropic_headers,
    anthropic_model,
    review_diff,
)

SAMPLE_DIFF = (
    "diff --git a/cross_asset_rank.py b/cross_asset_rank.py\n"
    "index 111..222 100644\n"
    "--- a/cross_asset_rank.py\n"
    "+++ b/cross_asset_rank.py\n"
    "@@ -1 +1 @@\n-old\n+new\n"
)

PROTECTED_DIFF = (
    "diff --git a/orchestration/specialist_coordination.json b/orchestration/specialist_coordination.json\n"
    "index 111..222 100644\n"
    "--- a/orchestration/specialist_coordination.json\n"
    "+++ b/orchestration/specialist_coordination.json\n"
    "@@ -1 +1 @@\n-old\n+new\n"
)

FULL_FINDINGS = {name: "avoided: no evidence of this problem in the diff" for name in REQUIRED_FALSIFICATION_FINDINGS}


def test_claude_adversarial_is_a_registered_reviewer():
    assert "claude-adversarial" in REVIEWERS
    assert "lead" in REVIEWERS
    assert "security" in REVIEWERS


def test_credential_gate_fails_closed_without_anthropic_api_key(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_API_KEY"):
        anthropic_headers()


def test_model_gate_fails_closed_without_anthropic_review_model(monkeypatch):
    monkeypatch.delenv("ANTHROPIC_REVIEW_MODEL", raising=False)
    with pytest.raises(RuntimeError, match="ANTHROPIC_REVIEW_MODEL"):
        anthropic_model()


def test_claude_adversarial_review_requires_all_eleven_falsification_findings(tmp_path, monkeypatch):
    diff_path = tmp_path / "candidate.diff"
    diff_path.write_text(SAMPLE_DIFF, encoding="utf-8")
    output_path = tmp_path / "verdict.json"

    incomplete = {
        "approve": True,
        "reason": "looks fine",
        "risk": "low",
        "falsification_findings": {"leakage_lookahead": "avoided"},  # missing 10 of 11
    }

    def fake_post(system, user, max_tokens=2000):
        assert "FALSIFY" in system
        for name in REQUIRED_FALSIFICATION_FINDINGS:
            assert name in user
        return {"stop_reason": "end_turn", "content": [{"type": "text", "text": json.dumps(incomplete)}]}

    monkeypatch.setattr("agents.autonomous_orchestrator.post_anthropic_message", fake_post)
    with pytest.raises(RuntimeError, match="omitted required falsification findings"):
        review_diff("claude-adversarial", diff_path, output_path)


def test_claude_adversarial_review_approves_with_complete_findings(tmp_path, monkeypatch):
    diff_path = tmp_path / "candidate.diff"
    diff_path.write_text(SAMPLE_DIFF, encoding="utf-8")
    output_path = tmp_path / "verdict.json"

    complete = {"approve": True, "reason": "all findings avoided", "risk": "low", "falsification_findings": FULL_FINDINGS}

    def fake_post(system, user, max_tokens=2000):
        return {"stop_reason": "end_turn", "content": [{"type": "text", "text": json.dumps(complete)}]}

    monkeypatch.setattr("agents.autonomous_orchestrator.post_anthropic_message", fake_post)
    review_diff("claude-adversarial", diff_path, output_path)
    verdict = json.loads(output_path.read_text(encoding="utf-8"))
    assert verdict["approve"] is True
    assert set(verdict["falsification_findings"]) == set(REQUIRED_FALSIFICATION_FINDINGS)


def test_claude_adversarial_review_rejects_invalid_risk_value(tmp_path, monkeypatch):
    diff_path = tmp_path / "candidate.diff"
    diff_path.write_text(SAMPLE_DIFF, encoding="utf-8")
    output_path = tmp_path / "verdict.json"

    bad_risk = {"approve": True, "reason": "x", "risk": "extreme", "falsification_findings": FULL_FINDINGS}

    def fake_post(system, user, max_tokens=2000):
        return {"stop_reason": "end_turn", "content": [{"type": "text", "text": json.dumps(bad_risk)}]}

    monkeypatch.setattr("agents.autonomous_orchestrator.post_anthropic_message", fake_post)
    with pytest.raises(RuntimeError, match="invalid risk"):
        review_diff("claude-adversarial", diff_path, output_path)


def test_claude_adversarial_review_still_fails_closed_on_protected_path(tmp_path, monkeypatch):
    diff_path = tmp_path / "candidate.diff"
    diff_path.write_text(PROTECTED_DIFF, encoding="utf-8")
    output_path = tmp_path / "verdict.json"

    def fake_post(system, user, max_tokens=2000):
        raise AssertionError("should never call the model for a protected-path diff")

    monkeypatch.setattr("agents.autonomous_orchestrator.post_anthropic_message", fake_post)
    with pytest.raises(RuntimeError, match="protected path"):
        review_diff("claude-adversarial", diff_path, output_path)


def test_reviewer_never_substitutes_for_canonical_quantitative_evidence_language():
    """The system prompt itself must state this, since the requirement is
    about the reviewer's own understanding of its authority, not only about
    what the workflow does with its output."""
    from agents.autonomous_orchestrator import _review_diff_claude_adversarial
    import inspect

    source = inspect.getsource(_review_diff_claude_adversarial)
    assert "never sufficient" in source
    assert "forward_proof.py" in source
    assert "robustness.py" in source
    assert "multiple_testing.py" in source
