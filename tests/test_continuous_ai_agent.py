import json

import continuous_ai_agent as agent


def test_validate_assessment_rejects_trade_state():
    parsed = agent.validate_assessment(
        {
            "status": "INVESTIGATE",
            "priority": "HIGH",
            "summary": "validator evidence still pending",
            "next_action": "verify the exact workflow result",
        }
    )
    assert parsed["status"] == "INVESTIGATE"
    assert parsed["priority"] == "HIGH"

    try:
        agent.validate_assessment(
            {
                "status": "TRADE",
                "priority": "HIGH",
                "summary": "buy now",
                "next_action": "bypass validation",
            }
        )
    except ValueError:
        pass
    else:
        raise AssertionError("trade-like AI status must fail closed")


def test_extract_json_accepts_fenced_and_wrapped_object():
    fenced = '```json\n{"status":"HEALTHY","priority":"LOW"}\n```'
    assert agent._extract_json(fenced)["status"] == "HEALTHY"

    wrapped = 'Assessment follows:\n{"status":"INVESTIGATE","priority":"MEDIUM"}\nEnd.'
    assert agent._extract_json(wrapped)["priority"] == "MEDIUM"


def test_extract_json_still_rejects_malformed_output():
    try:
        agent._extract_json("not json and no object")
    except json.JSONDecodeError:
        pass
    else:
        raise AssertionError("malformed output must fail closed")


def test_missing_ai_configuration_does_not_call_network(monkeypatch):
    monkeypatch.setattr(agent, "OPENAI_API_KEY", "")
    result = agent.run_ai_cycle()
    assert result == {"configured": False, "error_type": "MissingAIConfiguration"}


def test_status_has_no_authority_and_bounded_request_timeout():
    status = agent.status_snapshot()
    assert status["trade_authority"] is False
    assert status["write_authority"] is False
    assert status["promotion_authority"] is False
    assert status["interval_seconds"] >= 60
    assert 10 <= status["request_timeout_seconds"] <= 240


def test_openai_cycle_uses_bounded_timeout_and_no_retries(monkeypatch):
    seen = {}

    class FakeStateResponse:
        text = "# state"
        def raise_for_status(self):
            return None

    class FakeResponses:
        def create(self, **kwargs):
            seen["create"] = kwargs
            return type("Response", (), {"output_text": '{"status":"HEALTHY","priority":"LOW","summary":"ok","next_action":"continue"}'})()

    class FakeOpenAI:
        def __init__(self, **kwargs):
            seen["client"] = kwargs
            self.responses = FakeResponses()

    monkeypatch.setattr(agent, "OPENAI_API_KEY", "test-key")
    monkeypatch.setattr(agent, "CONTINUOUS_AI_MODEL", "test-model")
    monkeypatch.setattr(agent.httpx, "get", lambda *args, **kwargs: FakeStateResponse())
    monkeypatch.setattr(agent, "OpenAI", FakeOpenAI)

    result = agent.run_ai_cycle()
    assert result["configured"] is True
    assert seen["client"]["timeout"] == agent.CONTINUOUS_AI_TIMEOUT_SECONDS
    assert seen["client"]["max_retries"] == 0
