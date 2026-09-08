import paper_db as db


class _Response:
    status_code = 200
    text = ""

    def __init__(self, rows=None):
        self._rows = [] if rows is None else rows

    def json(self):
        return self._rows


def test_initial_cash_can_only_be_written_when_account_is_created(monkeypatch):
    calls = []
    monkeypatch.setattr(db, "_configured", lambda: True)
    monkeypatch.setattr(db.http, "patch", lambda *args, **kwargs: calls.append(kwargs["json"]) or _Response())
    db.update_paper_account("default", {"initial_cash": 1.0, "cash": 90000.0})
    assert "initial_cash" not in calls[0]
    assert calls[0]["cash"] == 90000.0


def test_close_reports_whether_open_trade_was_claimed(monkeypatch):
    monkeypatch.setattr(db, "_configured", lambda: True)
    monkeypatch.setattr(db.http, "patch", lambda *args, **kwargs: _Response([]))
    assert db.close_paper_trade(7, 101.0, "TARGET", 10.0, 1.0) is False
    monkeypatch.setattr(db.http, "patch", lambda *args, **kwargs: _Response([{"id": 7}]))
    assert db.close_paper_trade(7, 101.0, "TARGET", 10.0, 1.0) is True
