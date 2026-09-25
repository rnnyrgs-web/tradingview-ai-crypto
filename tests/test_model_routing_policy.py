import json
from pathlib import Path

POLICY = Path("orchestration/model_routing_policy.json")


def test_model_routing_policy_is_machine_readable_and_safe():
    data = json.loads(POLICY.read_text(encoding="utf-8"))
    assert data["version"] == 2
    assert data["invariants"]["broker_connected"] is False
    assert data["invariants"]["trade_authority"] is False
    assert data["invariants"]["max_active_deep_strategy_candidates"] == 1
    assert data["invariants"]["subscription_first_for_substantive_model_work"] is True
    assert data["invariants"]["never_claim_unavailable_model_or_work"] is True
    routes = data["routes"]
    assert routes["subscription_sol_high"]["model"] == "gpt-5.6-sol"
    assert routes["subscription_sol_high"]["reasoning"] == "high"
    assert routes["subscription_sol_high"]["executor"] == "chatgpt_subscription"
    assert routes["work"]["executor"] == "chatgpt_work"
    assert routes["codex"]["executor"] == "codex"
    assert routes["api_luna_fallback"]["model"] == "gpt-5.6-luna"
    assert routes["api_terra_fallback"]["model"] == "gpt-5.6-terra"
    assert routes["api_sol_fallback"]["model"] == "gpt-5.6-sol"
    assert routes["api_luna"]["compatibility_only"] is True
    assert routes["api_luna"]["model"] == "gpt-5.6-luna"
    assert any(rule["then"] == "work" for rule in data["routing_rules"])
    assert any(rule["then"] == "subscription_sol_high" for rule in data["routing_rules"])


def test_policy_keeps_legacy_luna_adapter_out_of_substantive_routing():
    data = json.loads(POLICY.read_text(encoding="utf-8"))
    route = data["routes"]["api_luna"]
    assert route["compatibility_only"] is True
    assert route["cost_priority"] > data["routes"]["api_luna_fallback"]["cost_priority"]
    assert all(rule.get("then") != "api_luna" for rule in data["routing_rules"])


def test_no_subscription_or_work_route_is_mislabeled_as_openai_api():
    data = json.loads(POLICY.read_text(encoding="utf-8"))
    assert data["routes"]["subscription_sol_high"]["executor"] == "chatgpt_subscription"
    assert data["routes"]["work"]["executor"] == "chatgpt_work"
\n\ndef test_pro_is_escalation_not_default_execution_route():\n    data = json.loads(POLICY.read_text(encoding="utf-8"))\n    pro = data["routes"]["chatgpt_pro_astra"]\n    assert pro["cost_priority"] > data["routes"]["work"]["cost_priority"]\n    assert "highest-stakes" in " ".join(pro["use_for"]).lower()\n    assert all(rule.get("then") != "chatgpt_pro_astra" or "highest-stakes" in rule.get("if", "").lower() for rule in data["routing_rules"])\n