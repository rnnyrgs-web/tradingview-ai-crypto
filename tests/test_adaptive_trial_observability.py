import research_adaptive_accuracy_runner as runner


def test_runner_exposes_durable_trial_count_without_authority(monkeypatch):
    states = [
        {"lessons": [], "conclusive_trial_count": 3, "updated_at": "before"},
    ]
    monkeypatch.setattr(runner, "load_state", lambda: states[-1])
    monkeypatch.setattr(
        runner,
        "build_adaptive_accuracy_report",
        lambda rows, memory: {
            "ok": True,
            "research_only": True,
            "trade_authority": False,
            "promotion_authority": False,
            "oos_opened": False,
            "evidence_conclusion": "no_dispatchable_hypothesis",
            "memory_lesson": None,
        },
    )

    report = runner.build_runner_report([])
    memory = report["research_memory"]

    assert memory["conclusive_trial_count"] == 3
    assert memory["lesson_count"] == 0
    assert memory["research_only"] is True
    assert memory["trade_authority"] is False
    assert memory["promotion_authority"] is False
    assert report["oos_opened"] is False


def test_runner_reloads_counter_after_conclusive_lesson(monkeypatch):
    states = [
        {"lessons": [], "conclusive_trial_count": 4, "updated_at": "before"},
        {
            "lessons": [{"fingerprint": "abc", "outcome": "validation_failed"}],
            "conclusive_trial_count": 5,
            "updated_at": "after",
        },
    ]
    calls = {"load": 0, "append": 0}

    def fake_load_state():
        index = min(calls["load"], len(states) - 1)
        calls["load"] += 1
        return states[index]

    def fake_append_lesson(lesson):
        calls["append"] += 1
        assert lesson["outcome"] == "validation_failed"

    monkeypatch.setattr(runner, "load_state", fake_load_state)
    monkeypatch.setattr(runner, "append_lesson", fake_append_lesson)
    monkeypatch.setattr(
        runner,
        "build_adaptive_accuracy_report",
        lambda rows, memory: {
            "ok": True,
            "research_only": True,
            "trade_authority": False,
            "promotion_authority": False,
            "oos_opened": False,
            "evidence_conclusion": "validation_failed",
            "memory_lesson": {"fingerprint": "abc", "outcome": "validation_failed"},
        },
    )

    report = runner.build_runner_report([])

    assert calls["append"] == 1
    assert report["research_memory"]["conclusive_trial_count"] == 5
    assert report["research_memory"]["lesson_count"] == 1
    assert report["research_memory"]["updated_at"] == "after"
    assert report["oos_opened"] is False
