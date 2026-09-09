from research_learning_state import append_lesson, load_state


def test_learning_state_is_bounded_and_research_only(tmp_path):
    path = tmp_path / "learning.json"
    for i in range(205):
        append_lesson({
            "fingerprint": f"f-{i}",
            "hypothesis": f"h-{i}",
            "outcome": "rejected" if i % 2 else "supported",
        }, path=path)
    state = load_state(path)
    assert len(state["lessons"]) == 200
    assert state["lessons"][0]["fingerprint"] == "f-5"
    assert all(row["research_only"] is True for row in state["lessons"])
    assert all(row["trade_authority"] is False for row in state["lessons"])


def test_same_fingerprint_replaces_old_lesson(tmp_path):
    path = tmp_path / "learning.json"
    append_lesson({"fingerprint": "same", "outcome": "rejected"}, path=path)
    append_lesson({"fingerprint": "same", "outcome": "supported"}, path=path)
    state = load_state(path)
    assert len(state["lessons"]) == 1
    assert state["lessons"][0]["outcome"] == "supported"
