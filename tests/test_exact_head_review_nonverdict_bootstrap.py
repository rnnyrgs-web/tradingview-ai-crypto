from __future__ import annotations

import json
from pathlib import Path

import httpx
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
