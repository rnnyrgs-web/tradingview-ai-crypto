from __future__ import annotations

import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = (
    ROOT
    / "orchestration/external_replication/ext_abnormal_day_momentum_001_randomized_timing_placebo.json"
)


def test_randomized_timing_placebo_contract_digest_and_upstream_binding() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    expected = contract.pop("contract_sha256")
    canonical = json.dumps(
        contract,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )
    assert hashlib.sha256(canonical.encode("utf-8")).hexdigest() == expected
    assert contract["source_stage1_head_sha"] == (
        "dab303eaf380da591147535f57bcbb4526085ac0"
    )
    assert contract["regenerate_if_source_stage1_head_changes"] is True
    assert contract["formed_before_replication_outcomes"] is True
    assert contract["formation"]["draw_count"] == 1
    assert contract["formation"]["post_outcome_redraw_allowed"] is False
    assert contract["authority"] == {
        "research_only": True,
        "promotion_authority": False,
        "broker_connected": False,
        "trade_authority": False,
        "protected_oos_opened": False,
        "genuine_forward_opened": False,
    }
