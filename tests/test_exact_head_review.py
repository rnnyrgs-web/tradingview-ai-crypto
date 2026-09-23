from __future__ import annotations

import json
from pathlib import Path

import pytest

from orchestration import exact_head_review as review
from orchestration import review_scope_policy as policy


HEAD_SHA = "a" * 40
RUNTIME_SHA = "c" * 40
WORKFLOW_REPOSITORY = "rnnyrgs-web/tradingview-ai-crypto"
WORKFLOW_REF = (
    "rnnyrgs-web/tradingview-ai-crypto/.github/workflows/"
    "exact_head_independent_review.yml@refs/heads/main"
)


def _legacy_provenance() -> dict[str, object]:
    return {
        "repository": WORKFLOW_REPOSITORY,
        "run_id": 123456789,
        "workflow_ref": WORKFLOW_REF,
        "runtime_git_sha": RUNTIME_SHA,
    }


def _trust_context() -> dict[str, object]:
    return {
        "repository": WORKFLOW_REPOSITORY,
        "run_id": 123456789,
        "run_attempt": 1,
        "event_name": "issues",
        "workflow_ref": WORKFLOW_REF,
        "workflow_sha": RUNTIME_SHA,
        "runtime_git_sha": RUNTIME_SHA,
        "github_sha": RUNTIME_SHA,
        "server_run_head_sha": RUNTIME_SHA,
        "server_run_event": "issues",
        "server_run_attempt": 1,
        "server_run_path": ".github/workflows/exact_head_independent_review.yml",
        "server_main_sha": RUNTIME_SHA,
    }


@pytest.fixture(autouse=True)
def _trusted_workflow_provenance(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        review,
        "_trusted_context_for_review",
        lambda: (_legacy_provenance(), _trust_context()),
    )


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
    assert verdict["workflow_provenance"]["runtime_git_sha"] == RUNTIME_SHA
    assert verdict["workflow_trust_context"]["server_main_sha"] == RUNTIME_SHA
    assert verdict["review_trust_binding_version"] == 1
    assert verdict["approval_consumption"]["approve_true_required"] is True
    prompt = str(captured["input"])
    assert "PROTECTED_PATH_CONTEXT: orchestration/strategy_predeclaration.py" in prompt
    assert f"WORKFLOW_RUNTIME_GIT_SHA: {RUNTIME_SHA}" in prompt
    assert "REVIEWER_TRUST_ROOT_SHA256:" in prompt
    assert "WORKFLOW_RUN_ATTEMPT: 1" in prompt
    assert "SERVER_MAIN_SHA:" in prompt
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
    assert f"WORKFLOW_RUNTIME_GIT_SHA: {RUNTIME_SHA}" in captured["input"]
    assert "WORKFLOW_RUN_ATTEMPT: 1" in captured["input"]
    assert "INTEGRATION_AUTHORITY: NONE" in captured["input"]
    verdict = json.loads(output.read_text(encoding="utf-8"))
    assert verdict["integration_authority"] == "NONE"
    assert verdict["protected_paths"] == ["orchestration/strategy_predeclaration.py"]
    assert verdict["workflow_provenance"]["runtime_git_sha"] == RUNTIME_SHA
    assert verdict["workflow_trust_context"]["server_run_attempt"] == 1


def test_runtime_git_sha_is_bound_from_checked_out_reviewer_runtime(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.undo()
    monkeypatch.setenv("GITHUB_REPOSITORY", WORKFLOW_REPOSITORY)
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setenv("GITHUB_WORKFLOW_REF", WORKFLOW_REF)

    class _Result:
        stdout = RUNTIME_SHA + "\n"

    monkeypatch.setattr(review.subprocess, "run", lambda *args, **kwargs: _Result())
    provenance = review._workflow_provenance_from_env()
    assert provenance["runtime_git_sha"] == RUNTIME_SHA


def test_invalid_runtime_git_sha_fails_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.undo()
    monkeypatch.setenv("GITHUB_REPOSITORY", WORKFLOW_REPOSITORY)
    monkeypatch.setenv("GITHUB_RUN_ID", "123")
    monkeypatch.setenv("GITHUB_WORKFLOW_REF", WORKFLOW_REF)

    class _Result:
        stdout = "not-a-sha\n"

    monkeypatch.setattr(review.subprocess, "run", lambda *args, **kwargs: _Result())
    with pytest.raises(RuntimeError, match="invalid reviewer-runtime git SHA"):
        review._workflow_provenance_from_env()


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


def test_active_registry_drift_fails_before_any_reviewer_provider(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    diff_path = tmp_path / "candidate.diff"
    diff_path.write_text(_diff(), encoding="utf-8")
    monkeypatch.setattr(
        policy,
        "protected_path_registry_identity",
        lambda: {"version": 1, "sha256": "0" * 64},
    )
    monkeypatch.setattr(
        review,
        "post_response",
        lambda _payload: pytest.fail("provider must not run after registry drift"),
    )
    with pytest.raises(RuntimeError, match="registry identity drifted"):
        review.review_exact_head(
            "security", diff_path, tmp_path / "out.json", pr_number=579, head_sha=HEAD_SHA
        )
