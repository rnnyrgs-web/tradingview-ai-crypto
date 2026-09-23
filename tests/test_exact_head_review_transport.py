from __future__ import annotations

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


@pytest.mark.parametrize(
    "exc",
    [
        httpx.ReadTimeout("timed out", request=_request("https://api.openai.com/v1/responses")),
        httpx.ConnectError("connect failed", request=_request("https://api.openai.com/v1/responses")),
        _status_error(503, "https://api.openai.com/v1/responses"),
        _status_error(429, "https://api.openai.com/v1/responses"),
    ],
)
def test_openai_exhausted_retryable_transport_becomes_bounded_nonverdict(
    exc: Exception, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    diff_path = tmp_path / "candidate.diff"
    output = tmp_path / "review.json"
    diff_path.write_text(_diff(), encoding="utf-8")
    monkeypatch.setattr(review, "_protected_context", lambda _diff_text: [])
    monkeypatch.setattr(review, "model_name", lambda: "test-model")

    def exhausted(_payload: dict[str, object]) -> dict[str, object]:
        raise exc

    monkeypatch.setattr(review, "post_response", exhausted)
    with pytest.raises(RuntimeError, match="temporarily unavailable.*exhausted bounded retries"):
        review.review_exact_head("security", diff_path, output, pr_number=606, head_sha=HEAD_SHA)
    assert not output.exists()


def test_openai_nonretryable_http_error_remains_hard_failure(
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
        review.review_exact_head("lead", diff_path, output, pr_number=606, head_sha=HEAD_SHA)
    assert not output.exists()


@pytest.mark.parametrize(
    "exc",
    [
        httpx.ReadTimeout("timed out", request=_request("https://api.anthropic.com/v1/messages")),
        httpx.ConnectError("connect failed", request=_request("https://api.anthropic.com/v1/messages")),
        _status_error(502, "https://api.anthropic.com/v1/messages"),
        _status_error(504, "https://api.anthropic.com/v1/messages"),
    ],
)
def test_claude_exhausted_retryable_transport_becomes_bounded_nonverdict(
    exc: Exception, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    diff_path = tmp_path / "candidate.diff"
    output = tmp_path / "review.json"
    diff_path.write_text(_diff(), encoding="utf-8")
    monkeypatch.setattr(review, "_protected_context", lambda _diff_text: [])

    def exhausted(_review_input: str, _raw_output: Path) -> int:
        raise exc

    monkeypatch.setattr(review, "_review_diff_claude_adversarial", exhausted)
    with pytest.raises(RuntimeError, match="temporarily unavailable.*exhausted bounded retries"):
        review.review_exact_head("claude-adversarial", diff_path, output, pr_number=606, head_sha=HEAD_SHA)
    assert not output.exists()
    assert not output.with_suffix(output.suffix + ".raw").exists()


def test_claude_nonretryable_http_error_remains_hard_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    diff_path = tmp_path / "candidate.diff"
    output = tmp_path / "review.json"
    diff_path.write_text(_diff(), encoding="utf-8")
    monkeypatch.setattr(review, "_protected_context", lambda _diff_text: [])
    exc = _status_error(403, "https://api.anthropic.com/v1/messages")

    def hard_failure(_review_input: str, _raw_output: Path) -> int:
        raise exc

    monkeypatch.setattr(review, "_review_diff_claude_adversarial", hard_failure)
    with pytest.raises(httpx.HTTPStatusError):
        review.review_exact_head("claude-adversarial", diff_path, output, pr_number=606, head_sha=HEAD_SHA)
    assert not output.exists()
    assert not output.with_suffix(output.suffix + ".raw").exists()


def test_retryable_status_contract_matches_provider_clients() -> None:
    assert review._RETRYABLE_PROVIDER_STATUSES == frozenset({408, 409, 429, 500, 502, 503, 504})
