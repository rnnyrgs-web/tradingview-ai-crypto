from research_adaptive_accuracy_runner import _bounded_limit


def test_adaptive_accuracy_fetch_limit_is_bounded(monkeypatch):
    monkeypatch.setenv("RESEARCH_ADAPTIVE_LEDGER_LIMIT", "999999")
    assert _bounded_limit("RESEARCH_ADAPTIVE_LEDGER_LIMIT", 500, 100, 2000) == 2000
    monkeypatch.setenv("RESEARCH_ADAPTIVE_LEDGER_LIMIT", "20")
    assert _bounded_limit("RESEARCH_ADAPTIVE_LEDGER_LIMIT", 500, 100, 2000) == 100
    monkeypatch.setenv("RESEARCH_ADAPTIVE_LEDGER_LIMIT", "bad")
    assert _bounded_limit("RESEARCH_ADAPTIVE_LEDGER_LIMIT", 500, 100, 2000) == 500
