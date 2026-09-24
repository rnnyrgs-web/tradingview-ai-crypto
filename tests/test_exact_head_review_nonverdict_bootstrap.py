from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from orchestration import exact_head_review as review


HEAD_SHA = "a" * 40
RUNTIME_SHA = "c" * 40
WORKFLOW_REPOSITORY = "rnnyrgs-web/tradingview-ai-crypto"
WORKFLOW_REF = (
    "rnnyrgs-web/tradingview-ai-crypto/.github/workflows/"
    "exact_head_independent_review.yml@refs/heads/main"
)


def _trusted_review_context() -> tuple[dict[str, object], dict[str, object]]:
    provenance = {
        "repository": WORKFLOW_REPOSITORY,
        "run_id": 123456789,
        "workflow_ref": WORKFLOW_REF,
        "runtime_git_sha": RUNTIME_SHA,
    }
    context = {
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
    return provenance, context


@pytest.fixture(autouse=True)
def _bypass_live_workflow_trust_only_for_provider_unit_tests(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # These tests exercise provider error classification after trust admission.
    # Trust reconciliation itself is covered adversarially in test_reviewer_trust_root.py.
    monkeypatch.setattr(review, "_trusted_context_for_review", _trusted_review_context)


def _diff() -> str:
    return """diff --git a/orchestration/strategy_predeclaration.py b/orchestration/strategy_predeclaration.py
index 1111111..2222222 100644
--- a/orchestration/strategy_predeclaration.py
+++ b/orchestration/strategy_predeclaration.py
@@ -1 +1 @@
-old
+new
"""


def _request(url: str) -> httpx.Request:
    return httpx.Request("POST", url)


def _status_error(status: int, url: str) -> httpx.HTTPStatusError:
    request = _request(url)
    response = httpx.Response(status, request=request)
    return httpx.HTTPStatusError(f"HTTP {status}", request=request, response=response)


def test_claude_malformed_json_is_bounded_nonverdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    diff_path = tmp_path / "candidate.diff"
    output = tmp_path / "review.json"
    diff_path.write_text(_diff(), encoding="utf-8")
    monkeypatch.setattr(review, "_protected_context", lambda _diff_text: [])

    def malformed(_review_input: str, _raw_output: Path) -> int:
        raise json.JSONDecodeError("truncated", "{", 1)

    monkeypatch.setattr(review, "_review_diff_claude_adversarial", malformed)
    with pytest.raises(RuntimeError, match="temporarily unavailable.*malformed"):
        review.review_exact_head("claude-adversarial", diff_path, output, pr_number=1, head_sha=HEAD_SHA)
    assert not output.exists()


def test_openai_429_is_bounded_nonverdict(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    diff_path = tmp_path / "candidate.diff"
    output = tmp_path / "review.json"
    diff_path.write_text(_diff(), encoding="utf-8")
    monkeypatch.setattr(review, "_protected_context", lambda _diff_text: [])
    monkeypatch.setattr(review, "model_name", lambda: "test-model")
    exc = _status_error(429, "https://api.openai.com/v1/responses")
    monkeypatch.setattr(review, "post_response", lambda _payload: (_ for _ in ()).throw(exc))

    with pytest.raises(RuntimeError, match="temporarily unavailable.*exhausted bounded retries"):
        review.review_exact_head("security", diff_path, output, pr_number=1, head_sha=HEAD_SHA)
    assert not output.exists()


def test_openai_401_remains_hard_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    diff_path = tmp_path / "candidate.diff"
    output = tmp_path / "review.json"
    diff_path.write_text(_diff(), encoding="utf-8")
    monkeypatch.setattr(review, "_protected_context", lambda _diff_text: [])
    monkeypatch.setattr(review, "model_name", lambda: "test-model")
    exc = _status_error(401, "https://api.openai.com/v1/responses")
    monkeypatch.setattr(review, "post_response", lambda _payload: (_ for _ in ()).throw(exc))

    with pytest.raises(httpx.HTTPStatusError):
        review.review_exact_head("lead", diff_path, output, pr_number=1, head_sha=HEAD_SHA)
    assert not output.exists()
