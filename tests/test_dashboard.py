import time
import dashboard


def test_entry_zone_is_ten_percent_of_stop_distance():
    row={"entry_price":100.0,"stop_loss":90.0}
    lo,hi=dashboard._entry_zone(row)
    assert lo==99.0
    assert hi==101.0


def test_trade_labels_do_not_turn_wait_into_trade():
    assert dashboard._trade_label({"action":"WAIT","direction":"LONG"})=="WAIT"
    assert dashboard._trade_label({"action":"TRADE","direction":"LONG"})=="BUY"
    assert dashboard._trade_label({"action":"TRADE","direction":"SHORT"})=="SELL"


def test_dashboard_session_signature(monkeypatch):
    monkeypatch.setattr(dashboard,"DASHBOARD_SECRET","test-only-secret")
    exp=int(time.time())+60
    token=dashboard._session_token(exp)
    assert dashboard._valid_session(token)
    assert not dashboard._valid_session(token+"tampered")


def test_expired_dashboard_session_rejected(monkeypatch):
    monkeypatch.setattr(dashboard,"DASHBOARD_SECRET","test-only-secret")
    exp=int(time.time())-1
    assert not dashboard._valid_session(dashboard._session_token(exp))
