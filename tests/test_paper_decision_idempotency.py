import paper_db


class _Response:
    status_code = 201
    text = ""

    def json(self):
        return []


def test_paper_signal_decision_uses_signal_key_conflict_target(monkeypatch):
    captured = {}

    def fake_post(url, *, headers, params, json):
        captured.update(url=url, headers=headers, params=params, json=json)
        return _Response()

    monkeypatch.setattr(paper_db, "SUPABASE_URL", "https://example.supabase.co")
    monkeypatch.setattr(paper_db, "SUPABASE_SECRET_KEY", "service-role-test")
    monkeypatch.setattr(paper_db.http, "post", fake_post)

    inserted = paper_db.insert_paper_signal_decision({
        "account_id": "default",
        "signal_key": "scan:24h:BTC-USDT:LONG",
        "scan_id": "scan",
        "symbol": "BTC-USDT",
        "horizon": "24h",
        "direction": "LONG",
        "action": "WAIT",
        "decision": "REJECTED",
        "reason": "not_actionable",
    })

    assert inserted is False
    assert captured["params"] == {"on_conflict": "signal_key"}
    assert "resolution=ignore-duplicates" in captured["headers"]["Prefer"]
    assert captured["json"]["signal_key"] == "scan:24h:BTC-USDT:LONG"
