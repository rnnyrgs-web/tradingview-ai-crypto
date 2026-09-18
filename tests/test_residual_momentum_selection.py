import json
import math
from pathlib import Path

from research_artifact import sha256_hex
from residual_momentum_selection import evaluate_selection_from_histories


CONTRACT_PATH = Path("orchestration/disc_residual_momentum_001.json")
RUNNER_PATH = Path("residual_momentum_selection.py")


def _histories(rows=420, assets=30):
    output = {}
    for asset in range(assets):
        price = 100.0 + asset
        candles = []
        for index in range(rows):
            factor = 0.0015 * math.sin(index / 11.0) + 0.0008 * math.cos(index / 19.0)
            idio = 0.0002 * math.sin((index + asset * 3) / 7.0)
            price *= 1.0 + factor + idio
            candles.append({"ts": (index + 1) * 3_600_000, "close": price})
        output[f"ASSET{asset:02d}-USDT"] = candles
    return output


def test_residual_selection_contract_is_frozen_and_oos_locked():
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    payload = dict(contract)
    expected = payload.pop("contract_sha256")
    payload.pop("contract_fingerprint_definition")

    assert sha256_hex(payload) == expected
    assert contract["fingerprint_id"] == "DISC-RESIDUAL-MOMENTUM-001-v1"
    assert contract["status"] == "PREDECLARED_SELECTION_ONLY"
    assert contract["research_only"] is True
    assert contract["trade_authority"] is False
    assert contract["promotion_authority"] is False
    assert contract["chronology"]["untouched_oos"] == "LOCKED"
    assert contract["search_breadth"]["primary_candidate_count"] == 1
    assert contract["search_breadth"]["parameter_optimization_allowed"] is False
    assert contract["source"]["point_in_time_universe_required_to_advance"] is True
    assert contract["selection_result_policy"]["attractive_curve_can_bypass_gate"] is False


def test_selection_runner_has_no_untouched_oos_execution_path():
    text = RUNNER_PATH.read_text(encoding="utf-8")
    assert "evaluate_untouched_oos" not in text
    assert "LOCKED_UNTOUCHED_OOS" in text


def test_unverified_point_in_time_evidence_cannot_freeze_or_terminally_reject():
    histories = _histories()
    symbols = list(histories)
    result = evaluate_selection_from_histories(symbols, histories)

    assert result["research_only"] is True
    assert result["trade_authority"] is False
    assert result["promotion_authority"] is False
    assert result["point_in_time_verified"] is False
    assert result["eligible_for_deep_freeze"] is False
    assert result["terminal_rejection_authorized"] is False
    assert result["untouched_oos_opened"] is False
    assert result["untouched_oos"]["status"] == "LOCKED_UNTOUCHED_OOS"
    assert result["screen_status"] in {
        "EXPLORATORY_PRE_OOS_FAIL_SURVIVORSHIP_UNVERIFIED",
        "PRE_OOS_PASS_BLOCKED_POINT_IN_TIME_UNIVERSE",
    }
