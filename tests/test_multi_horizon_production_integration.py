from datetime import datetime, timezone

import calibration
import config
import dashboard
import forward_proof
import opportunity_engine as oe


EXPECTED=("6h","12h","24h","48h","72h","7d")


def _risk_plan(features,direction,horizon):
    if direction=="LONG":
        return {"entry":100.0,"stop":90.0,"t1":119.0,"t2":130.0,"rr":1.9}
    return {"entry":100.0,"stop":110.0,"t1":81.0,"t2":70.0,"rr":1.9}


def test_horizon_contracts_align_without_lowering_existing_forward_thresholds():
    assert config.OPPORTUNITY_HORIZONS==EXPECTED
    assert dashboard.DASHBOARD_HORIZONS==EXPECTED
    assert dashboard.PERSISTED_SIGNAL_HORIZONS==EXPECTED
    expected_hours={"6h":6,"12h":12,"24h":24,"48h":48,"72h":72,"7d":168}
    for horizon,hours in expected_hours.items():
        assert config.HORIZONS[horizon]["hold_hours"]==hours
        assert calibration.HORIZON_SPAN[horizon].total_seconds()==hours*3600
        assert forward_proof.HORIZON_SPAN[horizon].total_seconds()==hours*3600
    assert forward_proof.MIN_FORWARD_SAMPLES["24h"]>=20
    assert forward_proof.MIN_FORWARD_SAMPLES["7d"]>=12


def test_new_6h_opportunity_is_immutable_wait_until_governance_passes(monkeypatch):
    persisted=[]; ledger=[]
    monkeypatch.setattr(oe,"replace_opportunities",lambda scan_id,horizon,rows: persisted.extend(dict(row) for row in rows))
    monkeypatch.setattr(oe,"insert_prediction_ledger",lambda rows: ledger.extend(dict(row) for row in rows))
    monkeypatch.setattr(oe,"fetch_resolved_predictions",lambda: [])
    monkeypatch.setattr(oe,"assess_global_market_risk",lambda *_args: type("R",(),{"blocked":False,"reasons":()})())
    monkeypatch.setattr(oe,"assess_execution_risk",lambda *_args: type("R",(),{"blocked":False,"reasons":()})())
    monkeypatch.setattr(oe,"health_snapshot",lambda: {})
    monkeypatch.setattr(oe,"now_utc",lambda: datetime(2026,9,10,0,0,tzinfo=timezone.utc))
    candidate={
        "symbol":"BTC-USDT","activity_score":10.0,"spread_bps":2.0,
        "market_consensus":{"reliable":True,"reason":"ok","confidence_multiplier":1.0},
        "horizons":{"6h":{"score":2.0,"features":{"1H":{"last":100.0}}}},
    }
    ai=[{"symbol":"BTC-USDT","horizon":"6h","direction":"LONG","strategy_family":"trend","action":"TRADE","evidence_score":90,"reasoning":"candidate"}]
    result=oe.build_opportunities("scan-6h",[candidate],ai,"BULL_TREND",_risk_plan)
    assert result["6h"][0]["action"]=="WAIT"
    assert persisted[0]["horizon"]=="6h"
    assert ledger[0]["horizon"]=="6h"
    due=datetime.fromisoformat(ledger[0]["due_at"].replace("Z","+00:00"))
    assert due==datetime(2026,9,10,6,0,tzinfo=timezone.utc)
    assert ledger[0]["action_at_forecast"]=="WAIT"
    assert ledger[0]["calibration"]["ready"] is False
    assert ledger[0]["calibration"]["independent_samples"]==0
