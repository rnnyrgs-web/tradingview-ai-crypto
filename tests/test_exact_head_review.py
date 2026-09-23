from __future__ import annotations

import json
from pathlib import Path

import pytest

from orchestration import exact_head_review as review


HEAD_SHA = "a" * 40


def _diff() -> str:
    return """diff --git a/orchestration/strategy_predeclaration.py b/orchestration/strategy_predeclaration.py
index 1111111..2222222 100644
--- a/orchestration/strategy_predeclaration.py
+++ b/orchestration/strategy_predeclaration.py
@@ -1 +1 @@
-old
+new
"""


def test_protected_diff_is_reviewed_not_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    diff_path = tmp_path / "candidate.diff"
    output = tmp_path / "review.json"
    diff_path.write_text(_diff(), encoding="utf-8")

    monkeypatch.setattr(review, "_protected_context", lambda _diff_text: ["orchestration/strategy_predeclaration.py"])
    monkeypatch.setattr(review, "model_name", lambda: "test-model")
    captured: dict[str, object] = {}

    def fake_post(payload: dict[str, object]) -> dict[str, object]:
        captured.update(payload)
        return {"output_text": '{"approve": true, "reason": "bounded", "risk": "low"}'}

    monkeypatch.setattr(review, "post_response", fake_post)
    monkeypatch.setattr(review, "response_text", lambda payload: str(payload["output_text"]))

    assert review.review_exact_head("security", diff_path, output, pr_number=507, head_sha=HEAD_SHA) == 0
    verdict = json.loads(output.read_text(encoding="utf-8"))
    assert verdict["approve"] is True
    assert verdict["protected_paths"] == ["orchestration/strategy_predeclaration.py"]
    assert verdict["integration_authority"] == "NONE"
    assert verdict["exact_head_sha"] == HEAD_SHA
    prompt = str(captured["input"])
    assert "PROTECTED_PATH_CONTEXT: orchestration/strategy_predeclaration.py" in prompt
    assert "INTEGRATION_AUTHORITY: NONE" in prompt
    assert "Protected scientific paths are NOT a reason to" in prompt


def test_claude_receives_same_protected_context(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    diff_path = tmp_path / "candidate.diff"
    output = tmp_path / "review.json"
    diff_path.write_text(_diff(), encoding="utf-8")
    captured: dict[str, str] = {}

    def fake_claude(review_input: str, raw_output: Path) -> int:
        captured["input"] = review_input
        raw_output.write_text(
            json.dumps(
                {
                    "approve": True,
                    "reason": "bounded",
                    "risk": "low",
                    "falsification_findings": {},
                }
            ),
            encoding="utf-8",
        )
        return 0

    monkeypatch.setattr(review, "_review_diff_claude_adversarial", fake_claude)
    assert review.review_exact_head(
        "claude-adversarial", diff_path, output, pr_number=507, head_sha=HEAD_SHA
    ) == 0
    assert "PROTECTED_PATH_CONTEXT: orchestration/strategy_predeclaration.py" in captured["input"]
    assert "INTEGRATION_AUTHORITY: NONE" in captured["input"]
    verdict = json.loads(output.read_text(encoding="utf-8"))
    assert verdict["integration_authority"] == "NONE"
    assert verdict["protected_paths"] == ["orchestration/strategy_predeclaration.py"]


def test_invalid_exact_head_fails_before_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    diff_path = tmp_path / "candidate.diff"
    diff_path.write_text(_diff(), encoding="utf-8")
    monkeypatch.setattr(
        review,
        "post_response",
        lambda _payload: pytest.fail("model must not run for invalid exact-head identity"),
    )
    with pytest.raises(RuntimeError, match="exact 40-character"):
        review.review_exact_head(
            "lead", diff_path, tmp_path / "out.json", pr_number=507, head_sha="not-a-sha"
        )


def test_oversized_diff_fails_before_model(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    diff_path = tmp_path / "candidate.diff"
    diff_path.write_text("x" * (review.MAX_DIFF_BYTES + 1), encoding="utf-8")
    monkeypatch.setattr(
        review,
        "post_response",
        lambda _payload: pytest.fail("model must not run for oversized diff"),
    )
    with pytest.raises(RuntimeError, match="diff too large"):
        review.review_exact_head(
            "lead", diff_path, tmp_path / "out.json", pr_number=507, head_sha=HEAD_SHA
        )


def test_invalid_reviewer_verdict_fails_closed(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    diff_path = tmp_path / "candidate.diff"
    diff_path.write_text(_diff(), encoding="utf-8")
    monkeypatch.setattr(review, "_protected_context", lambda _diff_text: [])
    monkeypatch.setattr(review, "model_name", lambda: "test-model")
    monkeypatch.setattr(review, "post_response", lambda _payload: {"output_text": '{"approve": "yes", "risk": "low"}'})
    monkeypatch.setattr(review, "response_text", lambda payload: str(payload["output_text"]))
    with pytest.raises(RuntimeError, match="invalid approval"):
        review.review_exact_head(
            "security", diff_path, tmp_path / "out.json", pr_number=507, head_sha=HEAD_SHA
        )
