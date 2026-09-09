from research_learning_state import append_lesson, load_state


def test_memory_is_bounded_and_research_only(tmp_path):
    path = tmp_path / "learning.json"
    for i in range(205):
        append_lesson({"fingerprint": f"f{i}", "hypothesis": f"h{i}", "outcome": "tested"}, path=path)
    state = load_state(path)
    assert len(state["lessons"]) == 200
    assert state["lessons"][-1]["research_only"] is True
    assert state["lessons"][-1]["trade_authority"] is False
    assert state["lessons"][-1]["promotion_authority"] is False


def test_duplicate_fingerprint_is_replaced(tmp_path):
    path = tmp_path / "learning.json"
    append_lesson({"fingerprint": "same", "hypothesis": "old", "outcome": "rejected"}, path=path)
    append_lesson({"fingerprint": "same", "hypothesis": "new", "outcome": "retested"}, path=path)
    state = load_state(path)
    assert len(state["lessons"]) == 1
    assert state["lessons"][0]["hypothesis"] == "new"


def test_invalid_state_fails_closed(tmp_path):
    path = tmp_path / "learning.json"
    path.write_text("not-json", encoding="utf-8")
    assert load_state(path) == {"lessons": [], "updated_at": None}
