import json
from pathlib import Path

POLICY = Path("orchestration/model_routing_policy.json")


def test_model_routing_policy_is_machine_readable_and_safe():
    data = json.loads(POLICY.read_text(encoding="utf-8"))
    assert data["version"] == 1
    assert data["invariants"]["broker_connected"] is False
    assert data["invariants"]["trade_authority"] is False
    assert data["invariants"]["max_active_deep_strategy_candidates"] == 1
    routes = data["routes"]
    assert routes["api_luna"]["model"] == "gpt-5.6-luna"
    assert routes["api_terra"]["model"] == "gpt-5.6-terra"
    assert routes["api_sol"]["model"] == "gpt-5.6-sol"
    assert routes["work_astra"]["model"] == "GPT-6 Astra"
    assert routes["work_astra"]["executor"] == "chatgpt_work"
    assert routes["codex_astra"]["executor"] == "codex"
    assert any(rule["then"] == "work_astra" for rule in data["routing_rules"])
    assert any(rule["then"] == "api_sol" for rule in data["routing_rules"])


def test_policy_never_routes_astra_through_openai_api():
    data = json.loads(POLICY.read_text(encoding="utf-8"))
    for name, route in data["routes"].items():
        if route.get("model") == "GPT-6 Astra":
            assert route["executor"] in {"chatgpt_work", "codex"}, name
