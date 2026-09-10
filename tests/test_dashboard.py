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


def test_dashboard_supports_all_predeclared_trade_horizons():
    assert dashboard.DASHBOARD_HORIZONS == ("6h","12h","24h","48h","72h","7d")
    assert dashboard.PERSISTED_SIGNAL_HORIZONS == dashboard.DASHBOARD_HORIZONS
    for horizon in dashboard.DASHBOARD_HORIZONS:
        assert dashboard._duration({"horizon":horizon}) == horizon
        assert dashboard._dashboard_view(horizon) == horizon
    assert dashboard._dashboard_view("all") == "all"
    assert dashboard._dashboard_view("nonsense") == "all"


def test_each_horizon_reads_real_persisted_rows(monkeypatch):
    called=[]
    monkeypatch.setattr(dashboard,"fetch_ranked_opportunities",lambda **kwargs: called.append(kwargs) or [{"symbol":"REAL","horizon":kwargs["horizon"]}])
    for horizon in dashboard.DASHBOARD_HORIZONS:
        rows=dashboard._rows_for_dashboard(horizon)
        assert rows[0]["horizon"]==horizon
    assert [item["horizon"] for item in called] == list(dashboard.DASHBOARD_HORIZONS)


def test_all_view_combines_all_persisted_horizons(monkeypatch):
    def fake_fetch(horizon,limit):
        return [{"symbol":horizon,"horizon":horizon,"rank":1,"evidence_score":80+dashboard.DASHBOARD_HORIZONS.index(horizon)}]
    monkeypatch.setattr(dashboard,"fetch_ranked_opportunities",fake_fetch)
    rows=dashboard._rows_for_dashboard("all")
    assert {row["horizon"] for row in rows}==set(dashboard.DASHBOARD_HORIZONS)
    assert len(rows)==len(dashboard.DASHBOARD_HORIZONS)


def test_calibration_metrics_show_forward_accuracy_floor_and_independent_n():
    metrics=dashboard._calibration_metrics({"calibration":{"ready":True,"empirical_precision":0.683,"precision_95pct_lower":0.571,"independent_samples":82,"minimum_samples":30}})
    assert metrics["accuracy"]=="68%"
    assert metrics["floor"]=="57%"
    assert metrics["n"]=="N=82"
    assert metrics["ready"] is True


def test_calibration_metrics_fail_closed_while_learning():
    metrics=dashboard._calibration_metrics({"calibration":{"ready":False,"independent_samples":12,"minimum_samples":30,"empirical_precision":0.99,"precision_95pct_lower":0.98}})
    assert metrics["accuracy"]=="LEARNING"
    assert metrics["floor"]=="—"
    assert metrics["n"]=="N=12/30"
    assert metrics["ready"] is False


def test_calibration_metrics_never_invent_missing_accuracy():
    metrics=dashboard._calibration_metrics({})
    assert metrics["accuracy"]=="LEARNING"
    assert metrics["floor"]=="—"
    assert metrics["n"]=="N=0/30"
