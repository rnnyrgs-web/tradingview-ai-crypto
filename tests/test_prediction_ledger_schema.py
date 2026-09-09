import db


class _Response:
    status_code = 200
    text = "[]"

    def json(self):
        return []


class _HTTP:
    def __init__(self):
        self.calls = []

    def get(self, url, headers=None, params=None):
        self.calls.append({"url": url, "params": dict(params or {})})
        return _Response()


def test_resolved_prediction_query_matches_production_schema(monkeypatch):
    fake = _HTTP()
    monkeypatch.setattr(db, "http", fake)
    monkeypatch.setattr(db, "configured", lambda: True)
    db.fetch_resolved_predictions()
    select = fake.calls[-1]["params"]["select"].split(",")
    assert "created_at" not in select
    assert "due_at" in select
    assert "resolved_at" in select


def test_shadow_prediction_query_matches_production_schema(monkeypatch):
    fake = _HTTP()
    monkeypatch.setattr(db, "http", fake)
    monkeypatch.setattr(db, "configured", lambda: True)
    db.fetch_shadow_predictions()
    select = fake.calls[-1]["params"]["select"].split(",")
    assert "created_at" not in select
    assert "scan_id" in select
    assert "resolved_at" in select


def test_prediction_ledger_chronology_still_orders_by_resolved_at(monkeypatch):
    fake = _HTTP()
    monkeypatch.setattr(db, "http", fake)
    monkeypatch.setattr(db, "configured", lambda: True)
    db.fetch_resolved_predictions()
    assert fake.calls[-1]["params"]["order"] == "resolved_at.desc"
    db.fetch_shadow_predictions()
    assert fake.calls[-1]["params"]["order"] == "resolved_at.asc"
