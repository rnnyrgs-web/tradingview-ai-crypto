import json
from pathlib import Path

import pytest

from big_move_tradability_canonical_gate import (
    CANONICAL_TRADABILITY_CONTRACT_GIT_BLOB_SHA,
    evaluate_authoritative_tradability_preflight,
    load_canonical_tradability_contract,
)


def test_authoritative_tradability_gate_uses_exact_frozen_blob():
    contract = load_canonical_tradability_contract()
    assert contract["artifact_id"] == "2X-TRADABILITY-001-v1"
    assert len(CANONICAL_TRADABILITY_CONTRACT_GIT_BLOB_SHA) == 40

    result = evaluate_authoritative_tradability_preflight()
    assert result["status"] == "READY_FOR_DATA"
    assert result["canonical_contract_git_blob_sha"] == CANONICAL_TRADABILITY_CONTRACT_GIT_BLOB_SHA
    assert result["execution_bands_usd"] == [1_000, 10_000, 50_000, 100_000]
    assert result["outcomes_opened"] is False
    assert result["strict_tradability_established"] is False
    assert result["prediction_authority"] is False
    assert result["promotion_authority"] is False
    assert result["broker_connected"] is False
    assert result["live_trading"] is False


def _mutated_root(tmp_path, mutate):
    source = Path(__file__).parents[1] / "money_intelligence/2x_tradability_precommitment_v1.json"
    contract = json.loads(source.read_text(encoding="utf-8"))
    mutate(contract)
    target = tmp_path / "money_intelligence/2x_tradability_precommitment_v1.json"
    target.parent.mkdir(parents=True)
    target.write_text(json.dumps(contract, indent=2) + "\n", encoding="utf-8")
    return tmp_path


def test_outcome_sensitive_spread_threshold_weakening_cannot_be_authoritative(tmp_path):
    root = _mutated_root(
        tmp_path,
        lambda contract: contract["strict_band_rules"].__setitem__(
            "maximum_median_spread_bps", 10_000
        ),
    )
    with pytest.raises(ValueError, match="drifted from frozen Git blob"):
        evaluate_authoritative_tradability_preflight(repo_root=root)


def test_snapshot_and_missingness_threshold_weakening_cannot_be_authoritative(tmp_path):
    root = _mutated_root(
        tmp_path,
        lambda contract: contract["strict_microstructure_window"].update(
            {
                "minimum_independent_snapshots": 2,
                "maximum_missing_fraction": 0.99,
            }
        ),
    )
    with pytest.raises(ValueError, match="drifted from frozen Git blob"):
        evaluate_authoritative_tradability_preflight(repo_root=root)


def test_adv_proxy_threshold_mutation_cannot_be_authoritative(tmp_path):
    root = _mutated_root(
        tmp_path,
        lambda contract: contract["proxy_liquidity_tag"].__setitem__(
            "maximum_band_to_median_daily_quote_volume_fraction", 0.99
        ),
    )
    with pytest.raises(ValueError, match="drifted from frozen Git blob"):
        evaluate_authoritative_tradability_preflight(repo_root=root)


def test_authoritative_entrypoint_accepts_no_caller_contract_override():
    with pytest.raises(TypeError):
        evaluate_authoritative_tradability_preflight(contract={})
