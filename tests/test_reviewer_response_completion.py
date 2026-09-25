import json

import httpx
import pytest

from agents import autonomous_orchestrator as agent
from orchestration import exact_head_review as review


def verdict(approve=True):
    return {
        "approve": approve, "reason": "Concrete bounded finding", "risk": "low",
        "falsification_findings": {
            name: "Not applicable to this diff: transport only."
            for name in agent.REQUIRED_FALSIFICATION_FINDINGS
        },
    }


@pytest.mark.parametrize("stop", ["max_tokens", "model_context_window_exceeded", None, "tool_use"])
def test_incomplete_claude_cannot_write_an_approval(tmp_path, monkeypatch, stop):
    monkeypatch.setattr(agent, "post_anthropic_message", lambda *a, **k: {
        "stop_reason": stop, "content": [{"type": "text", "text": json.dumps(verdict())}],
    })
    output = tmp_path / "receipt.json"
    with pytest.raises(RuntimeError, match="temporarily unavailable.*incomplete"):
        agent._review_diff_claude_adversarial("unchanged complete diff", output)
    assert not output.exists()


@pytest.mark.parametrize("approve", [True, False])
def test_complete_claude_verdict_preserves_all_findings(tmp_path, monkeypatch, approve):
    expected = verdict(approve)
    monkeypatch.setattr(agent, "post_anthropic_message", lambda *a, **k: {
        "stop_reason": "end_turn", "content": [{"type": "text", "text": json.dumps(expected)}],
    })
    output = tmp_path / "receipt.json"
    agent._review_diff_claude_adversarial("unchanged complete diff", output)
    assert json.loads(output.read_text()) == expected


def test_incomplete_but_valid_claude_rejection_is_not_erased(tmp_path, monkeypatch):
    expected = verdict(False)
    monkeypatch.setattr(agent, "post_anthropic_message", lambda *a, **k: {
        "stop_reason": "max_tokens", "content": [{"type": "text", "text": json.dumps(expected)}],
    })
    output = tmp_path / "receipt.json"
    agent._review_diff_claude_adversarial("unchanged complete diff", output)
    assert json.loads(output.read_text())["approve"] is False


@pytest.mark.parametrize("status", ["incomplete", "failed", "in_progress", None])
def test_incomplete_openai_cannot_return_approval(monkeypatch, status):
    monkeypatch.setattr(review, "model_name", lambda: "test")
    monkeypatch.setattr(review, "post_response", lambda p: {
        "status": status, "output_text": json.dumps(verdict()),
    })
    with pytest.raises(RuntimeError, match="temporarily unavailable.*incomplete"):
        review._openai_exact_head_verdict("complete diff")


def test_incomplete_but_valid_openai_rejection_is_not_erased(monkeypatch):
    monkeypatch.setattr(review, "model_name", lambda: "test")
    monkeypatch.setattr(review, "post_response", lambda p: {
        "status": "incomplete", "output_text": json.dumps(verdict(False)),
    })
    assert review._openai_exact_head_verdict("complete diff")["approve"] is False


@pytest.mark.parametrize("error", [
    {"code": "insufficient_quota"}, {"type": "insufficient_quota"},
    {"code": "credit_balance_exhausted"}, {"code": "organization_usage_limit_exceeded"},
    {"code": "organization_spend_limit_exceeded"}, {"code": "project_spend_limit_exceeded"},
])
def test_quota_exhaustion_is_not_retried_or_exposed(monkeypatch, error):
    calls, sleeps = [], []
    def respond(request):
        calls.append(request)
        return httpx.Response(429, json={"error": {**error, "message": "PRIVATE_PROVIDER_DETAIL"}})
    client = httpx.Client
    monkeypatch.setattr(agent.httpx, "Client", lambda **kw: client(transport=httpx.MockTransport(respond), **kw))
    monkeypatch.setattr(agent, "api_headers", lambda: {})
    monkeypatch.setattr(agent.time, "sleep", sleeps.append)
    with pytest.raises(RuntimeError, match="OpenAI quota exhausted") as exc:
        agent.post_response({"input": "complete diff"})
    assert len(calls) == 1
    assert sleeps == []
    assert "PRIVATE_PROVIDER_DETAIL" not in str(exc.value)
    assert "429" not in str(exc.value)  # workflow must not misclassify as transient WAIT


@pytest.mark.parametrize("body", [{"error": {"code": "rate_limit_exceeded"}}, {}, {"error": []}])
def test_transient_or_unknown_429_keeps_bounded_retry(monkeypatch, body):
    calls, sleeps = [], []
    def respond(request):
        calls.append(request)
        if len(calls) == 1:
            return httpx.Response(429, json=body, headers={"retry-after": "2"})
        return httpx.Response(200, json={"status": "completed", "output_text": "result"})
    client = httpx.Client
    monkeypatch.setattr(agent.httpx, "Client", lambda **kw: client(transport=httpx.MockTransport(respond), **kw))
    monkeypatch.setattr(agent, "api_headers", lambda: {})
    monkeypatch.setattr(agent.time, "sleep", sleeps.append)
    assert agent.post_response({"input": "complete diff"})["status"] == "completed"
    assert len(calls) == 2
    assert sleeps == [2.0]
