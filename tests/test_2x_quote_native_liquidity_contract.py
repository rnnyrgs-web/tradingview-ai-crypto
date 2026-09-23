import json
from pathlib import Path

from big_move_quote_native_liquidity import (
    SCHEMA,
    THRESHOLD_QUOTE_ASSET,
    TRANSFORM_ID,
    TRANSFORM_VERSION,
    frozen_parameters,
)


def _contract():
    path = (
        Path(__file__).resolve().parents[1]
        / "money_intelligence"
        / "2x_cohort_001_quote_native_liquidity_contract.json"
    )
    return json.loads(path.read_text(encoding="utf-8"))


def test_contract_is_source_native_usdt_and_code_constants_match():
    contract = _contract()
    assert contract["schema"] == "two_x_quote_native_liquidity_contract.v1"
    assert contract["outcome_access"] == "SEALED"
    assert contract["universe_scope"]["venue"] == "BINANCE_SPOT"
    assert contract["universe_scope"]["quote_asset"] == "USDT"
    assert contract["source_unit_dependency"]["normalized_rows_schema"] == SCHEMA
    assert contract["source_unit_dependency"]["provider_measure"] == "quote_asset_volume"
    assert contract["source_unit_dependency"]["legacy_usd_labeled_rows"] == "REJECT"

    feature = contract["feature"]
    assert feature["field"] == "liquidity_quote_asset"
    assert feature["source_id"] == TRANSFORM_ID
    assert feature["transform_version"] == TRANSFORM_VERSION
    assert feature["unit"] == "USDT"
    assert feature["unit_semantics"] == "SOURCE_NATIVE_QUOTE_ASSET_NOT_USD"
    assert feature["window_days"] == frozen_parameters()["window_days"]
    assert feature["measure"] == frozen_parameters()["measure"]
    assert feature["completed_daily_bars_only"] is True
    assert feature["required_observation_count"] == 30

    gate = contract["cohort_liquidity_gate"]
    assert gate["threshold"] == THRESHOLD_QUOTE_ASSET
    assert gate["unit"] == "USDT"
    assert gate["usd_equivalence_claim"] is False


def test_contract_keeps_legacy_usd_semantics_blocked_and_grants_no_authority():
    contract = _contract()
    legacy = contract["legacy_v1_containment"]
    assert legacy["feature"] == "liquidity_usd"
    assert legacy["source_id"] == "TRAILING_30D_MEDIAN_QUOTE_VOLUME_USD_V1"
    assert legacy["raw_binance_quote_asset_volume_may_satisfy"] is False
    assert legacy["silent_reinterpretation"] is False

    authority = contract["authority"]
    assert authority
    assert all(value is False for value in authority.values())

    tradability = contract["tradability_boundary"]
    assert tradability["this_feature_establishes_strict_tradability"] is False
    assert set(tradability["strict_tradability_requires"]) == {
        "PIT_EVENT_TIME_DEPTH",
        "PIT_EVENT_TIME_SPREAD",
        "PIT_EVENT_TIME_SLIPPAGE",
    }


def test_contract_requires_corrected_exact_head_ci_before_integration():
    dependency = _contract()["ci_integrity_dependency"]
    assert dependency["issue"] == 717
    assert dependency["repair_pr"] == 718
    assert dependency["pre_repair_pull_request_ci_status"] == (
        "MERGE_REF_ONLY_NOT_EXACT_HEAD_EVIDENCE"
    )
    assert dependency["integration_requires_marker"] == "EXACT_HEAD_PR_CHECKOUT_V1"
    assert dependency["integration_requires_checkout_identity_gate"] is True
