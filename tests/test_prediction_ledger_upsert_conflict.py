import db


class _Response:
    status_code = 201
    text = ""


class _HTTP:
    def __init__(self):
        self.calls = []

    def post(self, url, headers=None, params=None, json=None):
        self.calls.append({
            "url": url,
            "headers": dict(headers or {}),
            "params": dict(params or {}),
            "json": json,
        })
        return _Response()


def test_prediction_ledger_insert_uses_composite_unique_conflict_target(monkeypatch):
    fake = _HTTP()
    monkeypatch.setattr(db, "http", fake)
    monkeypatch.setattr(db, "configured", lambda: True)

    row = {
        "scan_id": "6e089eec-d7c7-5b11-af17-4f8ec408dab2",
        "symbol": "ZEC-USDT",
        "horizon": "6h",
        "direction": "LONG",
        "entry_price": 1160.34,
        "score": 3.75,
        "market_regime": "UNCLASSIFIED",
        "strategy_identity": {"system": "FFRIZZ_SECONDARY_V1", "research_only": True},
        "action_at_forecast": "WAIT",
        "due_at": "2026-09-12T19:52:05+00:00",
        "calibration": {"source_system": "FFRIZZ_SECONDARY_V1", "shadow_only": True},
    }

    db.insert_prediction_ledger([row])

    call = fake.calls[-1]
    assert call["params"] == {"on_conflict": "scan_id,symbol,horizon"}
    assert "resolution=ignore-duplicates" in call["headers"]["Prefer"]
    assert call["json"] == [row]
