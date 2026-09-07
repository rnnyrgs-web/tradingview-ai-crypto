import time
import dashboard


def test_entry_zone_is_ten_percent_of_stop_distance():
    row={"entry_price":100.0,"stop_loss":90.0}
    lo,hi=dashboard._entry_zone(row)
    assert lo==99.0
    assert hi==101.0


def test_trade_labels_fail_closed_without_approved_exact_identity(monkeypatch):
    assert dashboard._trade_label({"action":"WAIT","direction":"LONG"})=="WAIT"
    assert dashboard._trade_label({"action":"TRADE","direction":"LONG"})=="WAIT"

    identity={"strategy_family":"trend","fingerprint":"approved"}
    decision=type("Decision", (), {
        "approved":True,
        "identity":{"fingerprint":"approved"},
    })()
    monkeypatch.setattr(dashboard, "validate_live_strategy", lambda *args: decision)
    row={
        "action":"TRADE", "direction":"LONG", "symbol":"ETH-USDT", "horizon":"24h",
        "strategy_identity":identity,
    }
    assert dashboard._trade_label(row)=="BUY"
    row["direction"]="SHORT"
    assert dashboard._trade_label(row)=="SELL"


def test_trade_label_rejects_unapproved_or_mismatched_persisted_identity(monkeypatch):
    row={
        "action":"TRADE", "direction":"LONG", "symbol":"ETH-USDT", "horizon":"24h",
        "strategy_identity":{"strategy_family":"unknown", "fingerprint":"supplied"},
    }
    rejected=type("Decision", (), {
        "approved":False,
        "identity":{"fingerprint":"supplied"},
    })()
    monkeypatch.setattr(dashboard, "validate_live_strategy", lambda *args: rejected)
    assert dashboard._trade_label(row)=="WAIT"

    mismatched=type("Decision", (), {
        "approved":True,
        "identity":{"fingerprint":"different"},
    })()
    monkeypatch.setattr(dashboard, "validate_live_strategy", lambda *args: mismatched)
    assert dashboard._trade_label(row)=="WAIT"


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
