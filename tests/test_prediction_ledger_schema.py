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
    assert "research_context" in select
    assert "calibration" not in select


def test_shadow_prediction_query_matches_production_schema(monkeypatch):
    fake = _HTTP()
    monkeypatch.setattr(db, "http", fake)
    monkeypatch.setattr(db, "configured", lambda: True)
    db.fetch_shadow_predictions()
    select = fake.calls[-1]["params"]["select"].split(",")
    assert "created_at" not in select
    assert "scan_id" in select
    assert "resolved_at" in select
    assert "research_context" in select
    assert "calibration" in select


def test_prediction_ledger_chronology_still_orders_by_resolved_at(monkeypatch):
    fake = _HTTP()
    monkeypatch.setattr(db, "http", fake)
    monkeypatch.setattr(db, "configured", lambda: True)
    db.fetch_resolved_predictions()
    assert fake.calls[-1]["params"]["order"] == "resolved_at.desc"
    db.fetch_shadow_predictions()
    assert fake.calls[-1]["params"]["order"] == "resolved_at.desc"
    assert int(fake.calls[-1]["params"]["limit"]) <= 2000


def test_shadow_prediction_fetch_returns_recent_window_in_chronological_order(monkeypatch):
    class _RowsResponse:
        status_code = 200
        text = "[]"

        def json(self):
            return [
                {"id": 3, "resolved_at": "2026-09-03T00:00:00+00:00"},
                {"id": 2, "resolved_at": "2026-09-02T00:00:00+00:00"},
                {"id": 1, "resolved_at": "2026-09-01T00:00:00+00:00"},
            ]

    class _RowsHTTP:
        def __init__(self):
            self.params = None

        def get(self, url, headers=None, params=None):
            self.params = dict(params or {})
            return _RowsResponse()

    fake = _RowsHTTP()
    monkeypatch.setattr(db, "http", fake)
    monkeypatch.setattr(db, "configured", lambda: True)
    rows = db.fetch_shadow_predictions(limit=999999)
    assert fake.params["order"] == "resolved_at.desc"
    assert fake.params["limit"] == "2000"
    assert [row["id"] for row in rows] == [1, 2, 3]


def test_prediction_identity_fetch_is_exact_and_never_fabricates_missing_fields(monkeypatch):
    class _OneResponse:
        status_code = 200
        text = ""

        def json(self):
            return [{"id": 42, "scan_id": "canonical"}]

    class _OneHTTP:
        def __init__(self):
            self.params = None

        def get(self, url, headers=None, params=None):
            self.params = params
            return _OneResponse()

    fake = _OneHTTP()
    monkeypatch.setattr(db, "http", fake)
    monkeypatch.setattr(db, "configured", lambda: True)
    assert db.fetch_prediction_by_id(42) == {"id": 42, "scan_id": "canonical"}
    assert fake.params == {"select": "*", "id": "eq.42", "limit": "1"}
    assert db.fetch_prediction_by_id("42") is None
    assert db.fetch_prediction_by_id(-1) is None


def test_compacted_research_context_exposes_preforecast_market_fields_without_calibration():
    row = {
        "research_context": {
            "preforecast_market_context": {
                "captured_at": "2026-09-19T00:00:10Z",
                "market_consensus": {
                    "recorded": True,
                    "reliable_at_forecast": True,
                    "independent_source_count": 2,
                    "required_source_count": 2,
                    "price_range_bps": 4.5,
                    "max_quote_age_seconds": 8,
                    "accepted_exchange_names": ["kraken", "okx"],
                    "accepted_observations": [
                        {"exchange": "kraken", "observed_ms": 1789776000000},
                        {"exchange": "okx", "observed_ms": 1789776005000},
                    ],
                },
            }
        }
    }
    exposed = db._expose_preforecast_market_fields(row)
    assert exposed["market_consensus_reliable"] is True
    assert exposed["market_consensus_timestamp_safe"] is True
    assert exposed["market_consensus_source_count"] == 2
    assert exposed["market_consensus_accepted_exchange_names"] == ["kraken", "okx"]
