import research_director_runtime
import profitability_learning.runtime as runtime


def test_default_profitability_director_surface_consumes_causal_feedback(monkeypatch):
    monkeypatch.setattr(
        research_director_runtime,
        "refresh_director",
        lambda army: {
            "missions": [],
            "next_missions": [],
            "daily_lead_report": {"highest_priority_next_missions": []},
        },
    )
    monkeypatch.setattr(
        runtime,
        "factory_feedback",
        lambda: {"status": "WAIT_MEMORY_NOT_CONFIGURED", "missions": []},
    )
    calls = []

    def fake_causal(state):
        calls.append(True)
        state = dict(state)
        state["causal_wiring_proved"] = True
        return state

    monkeypatch.setattr(runtime, "apply_causal_feedback", fake_causal)
    result = runtime.refresh_director({"workers": {}})
    assert calls == [True]
    assert result["causal_wiring_proved"] is True
