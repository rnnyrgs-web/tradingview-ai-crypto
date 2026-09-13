import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_acc001_stays_blocked_until_microstructure_is_persisted_preforecast():
    backlog = json.loads((ROOT / "orchestration" / "priority_backlog.json").read_text())
    acc001 = next(item for item in backlog["items"] if item["id"] == "ACC-001")
    opportunity_source = (ROOT / "opportunity_engine.py").read_text()
    db_source = (ROOT / "db.py").read_text()

    has_capture_path = (
        "preforecast_microstructure" in opportunity_source
        and "preforecast_microstructure" in db_source
    )

    if has_capture_path:
        # A future implementation may reopen ACC-001, but only after both the
        # immutable forecast-time write path and resolved-row exposure exist.
        assert acc001["status"] in {"BLOCKED", "READY"}
    else:
        assert acc001["status"] == "BLOCKED"
        assert "prediction-ledger persistence" in acc001["block_reason"]
        assert "historical reconstruction or backfill" in " ".join(acc001["acceptance"])


def test_microstructure_research_cannot_gain_authority_while_capture_is_blocked():
    source = (ROOT / "research_microstructure_veto.py").read_text()
    assert '"trade_authority": False' in source
    assert '"promotion_authority": False' in source
    assert '"historical_orderbook_reconstruction_allowed": False' in source
