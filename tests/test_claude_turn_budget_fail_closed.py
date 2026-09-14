import copy

from agents.autonomous_cloud_runner import Decision, load_config, load_coordination
from agents import claude_specialist_runner as runner


def test_turn_budget_exhaustion_returns_blocked_and_preserves_usage(monkeypatch):
    config = copy.deepcopy(load_config(runner.CONFIG_PATH))
    config["roles"]["signal-accuracy"]["max_turns"] = 2
    coordination = load_coordination()
    decision = Decision(
        run=True,
        reason="READY",
        role="signal-accuracy",
        task_id="COORD-VAL-001",
        branch="auto/signal-accuracy/coord-val-001",
    )

    calls = []

    def fake_post(payload):
        calls.append(payload)
        n = len(calls)
        return {
            "content": [
                {
                    "type": "tool_use",
                    "id": f"tool-{n}",
                    "name": "unknown_tool",
                    "input": {},
                }
            ],
            "usage": {
                "input_tokens": 100 * n,
                "output_tokens": 10 * n,
                "cache_read_input_tokens": 5 * n,
            },
        }

    monkeypatch.setattr(runner, "_post_anthropic", fake_post)

    outcome, usage = runner.run_agent(config, coordination, decision)

    assert len(calls) == 2
    assert outcome["status"] == "BLOCKED"
    assert "bounded turn budget" in outcome["summary"]
    assert outcome["changed_files"] == []
    assert usage == {
        "input_tokens": 300,
        "output_tokens": 30,
        "cached_input_tokens": 15,
    }
