import json
from pathlib import Path


def test_ffrizz_v2_registration_remains_research_only():
    data = json.loads(Path("orchestration/ffrizz_v2_oi_alignment.json").read_text(encoding="utf-8"))
    assert data["id"] == "FFRIZZ_SECONDARY_V2_OI_CLOSE_END"
    assert data["status"] == "research_only"
    assert data["thresholds_changed"] is False
    assert data["interpolation_allowed"] is False
    assert data["historical_backfill_allowed"] is False
    assert data["pool_with_v1_evidence"] is False
    assert data["trade_authority"] is False
    assert data["paper_trade_authority"] is False
    assert data["promotion_authority"] is False
    assert data["broker_authority"] is False
