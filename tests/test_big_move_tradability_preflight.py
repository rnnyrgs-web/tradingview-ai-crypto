import copy
import json
from pathlib import Path

import pytest

from big_move_tradability_preflight import load_and_validate, validate_tradability_contract


CONTRACT_PATH = Path("money_intelligence/2x_tradability_precommitment_v1.json")


def _contract():
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_frozen_tradability_contract_is_ready_only_for_data_collection():
    result = validate_tradability_contract(_contract())
    assert result == {
        "status": "READY_FOR_DATA",
        "artifact_id": "2X-TRADABILITY-001-v1",
        "execution_bands_usd": [1_000, 10_000, 50_000, 100_000],
        "outcomes_opened": False,
        "strict_tradability_established": False,
    }


def test_loader_validates_committed_contract():
    assert load_and_validate(CONTRACT_PATH)["status"] == "READY_FOR_DATA"


def test_adv_proxy_cannot_be_promoted_to_strict_tradability():
    contract = _contract()
    contract["proxy_liquidity_tag"]["authority"] = "STRICT_TRADABLE"
    with pytest.raises(ValueError, match="ADV proxy cannot receive strict tradability authority"):
        validate_tradability_contract(contract)


def test_missing_microstructure_must_remain_unknown():
    contract = _contract()
    contract["principles"]["missing_microstructure_policy"] = "ASSUME_TRADABLE_FROM_ADV"
    with pytest.raises(ValueError, match="missing_microstructure_policy"):
        validate_tradability_contract(contract)


def test_outcome_fields_cannot_enter_precommitment():
    contract = _contract()
    contract["hypothesis"]["future_return"] = 1.4
    with pytest.raises(ValueError, match="outcome-derived field is forbidden"):
        validate_tradability_contract(contract)


def test_single_snapshot_cannot_establish_strict_tradability():
    contract = _contract()
    contract["strict_microstructure_window"]["minimum_independent_snapshots"] = 1
    with pytest.raises(ValueError, match="multiple independent snapshots"):
        validate_tradability_contract(contract)


def test_coverage_mask_and_rare_event_metrics_are_frozen():
    contract = _contract()
    contract["evaluation_precommitment"]["coverage_mask_must_be_frozen_before_outcomes"] = False
    with pytest.raises(ValueError, match="coverage mask"):
        validate_tradability_contract(contract)

    contract = _contract()
    contract["evaluation_precommitment"]["primary_metrics"] = ["accuracy"]
    with pytest.raises(ValueError, match="primary metrics"):
        validate_tradability_contract(contract)


def test_authority_remains_off():
    for key in ("prediction_authority", "promotion_authority", "broker_connected", "live_trading"):
        contract = copy.deepcopy(_contract())
        contract["authority"][key] = True
        with pytest.raises(ValueError, match="cannot grant"):
            validate_tradability_contract(contract)
