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


def test_calibration_metrics_show_forward_accuracy_floor_and_independent_n():
    metrics=dashboard._calibration_metrics({
        "calibration":{
            "ready":True,
            "empirical_precision":0.683,
            "precision_95pct_lower":0.571,
            "independent_samples":82,
            "minimum_samples":30,
        }
    })
    assert metrics["accuracy"]=="68%"
    assert metrics["floor"]=="57%"
    assert metrics["n"]=="N=82"
    assert metrics["ready"] is True


def test_calibration_metrics_fail_closed_while_learning():
    metrics=dashboard._calibration_metrics({
        "calibration":{
            "ready":False,
            "independent_samples":12,
            "minimum_samples":30,
            "empirical_precision":0.99,
            "precision_95pct_lower":0.98,
        }
    })
    assert metrics["accuracy"]=="LEARNING"
    assert metrics["floor"]=="—"
    assert metrics["n"]=="N=12/30"
    assert metrics["ready"] is False


def test_calibration_metrics_never_invent_missing_accuracy():
    metrics=dashboard._calibration_metrics({})
    assert metrics["accuracy"]=="LEARNING"
    assert metrics["floor"]=="—"
    assert metrics["n"]=="N=0/30"
