from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = ROOT / "orchestration" / "external_replication" / "ext_eth_tuesday_drift_001_v1.json"
EXPECTED_SHA256 = "6ddab16cbfbb846d0690dced9e2128244e2bc9ec6221243a02cb48fea4b5c98b"


def _canonical_json(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _load() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_frozen_contract_digest_and_identity() -> None:
    contract = _load()
    digest = contract.pop("artifact_sha256")
    assert digest == EXPECTED_SHA256
    assert hashlib.sha256(_canonical_json(contract)).hexdigest() == EXPECTED_SHA256
    assert contract["replication_id"] == "EXT-ETH-TUESDAY-DRIFT-001-v1"
    assert contract["status"] == "FROZEN_PRE_OUTCOME_WAIT_ADMISSION_REVIEW"


def test_source_chronology_is_genuinely_post_publication() -> None:
    contract = _load()
    source = contract["source_research"]
    data = contract["data_contract"]
    assert source["source_data_end"] == "2023-05-05"
    assert source["published_at"] == "2024-08-12"
    assert data["screen_start_utc"] == "2025-05-12T00:00:00Z"
    assert source["published_results_are_project_evidence"] is False
    assert contract["evidence_chronology"]["classification"] == "POST_PUBLICATION_PROJECT_UNREAD_REPLICATION"
    assert contract["evidence_chronology"]["profitability_claim_allowed_from_stage1"] is False


def test_one_materially_distinct_rule_no_parameter_search() -> None:
    contract = _load()
    signal = contract["signal_rules"]
    assert signal["parameter_variants"] == 1
    assert signal["selected_weekdays_utc"] == ["TUESDAY"]
    assert signal["direction"] == "LONG"
    assert signal["holding_period_hours"] == 24
    assert signal["day_selection_search_allowed"] is False
    assert signal["boundary_search_allowed"] is False
    assert signal["asset_search_allowed"] is False
    assert signal["direction_search_allowed"] is False
    assert signal["post_outcome_parameter_changes_allowed"] is False
    assert contract["multiple_testing"]["project_primary_hypotheses_frozen_now"] == 1
    assert contract["multiple_testing"]["project_parameter_variants"] == 1


def test_dataset_and_protected_tail_are_exactly_bound() -> None:
    contract = _load()
    data = contract["data_contract"]
    assert data["normalized_dataset_sha256"] == "047c098bb2957557f8344ca30c32339ecac01b5067ae424b147d21c9e9caaf9f"
    assert data["compressed_git_blob_sha1"] == "3a93beb4b1b4ef7f5d32b2936bf3119c692e7c15"
    assert data["instrument"] == "ETH-USDT-SWAP"
    assert data["bar_interval"] == "1H"
    assert data["asset_substitution_allowed"] is False
    assert data["protected_oos_start_utc"] == "2026-09-01T00:00:00Z"
    assert data["screen_may_read_protected_oos"] is False


def test_frozen_halves_are_34_complete_weeks_each() -> None:
    contract = _load()
    data = contract["data_contract"]
    parse = lambda s: datetime.fromisoformat(s.replace("Z", "+00:00"))
    h1_start = parse("2025-05-12T00:00:00Z")
    h1_end_exclusive = parse("2026-01-05T00:00:00Z")
    h2_start = parse("2026-01-05T00:00:00Z")
    h2_end_exclusive = parse("2026-08-31T00:00:00Z")
    assert (h1_end_exclusive - h1_start).days == 34 * 7
    assert (h2_end_exclusive - h2_start).days == 34 * 7
    assert data["expected_complete_weeks_total"] == 68
    assert data["expected_tuesday_sessions_total_before_data_missingness"] == 68
    assert data["expected_tuesday_sessions_per_half_before_data_missingness"] == 34


def test_cost_and_successive_halving_gates_are_frozen() -> None:
    contract = _load()
    assert contract["cost_model"]["round_trip_cost_bps_ladder"] == [24.0, 48.0, 72.0]
    stage1 = contract["stage_1_screen"]
    assert stage1["primary_cost_bps"] == 48.0
    assert stage1["stress_cost_bps"] == 72.0
    assert stage1["minimum_scored_sessions_per_half"] == 25
    assert len(stage1["survival_requires_all"]) == 7
    assert contract["survivor_baseline_gauntlet"]["execute_only_if_stage_1_survives"] is True


def test_baseline_gauntlet_is_predeclared_before_outcomes() -> None:
    contract = _load()
    gauntlet = contract["survivor_baseline_gauntlet"]
    assert set(gauntlet) >= {
        "market_beta",
        "simple_trend",
        "simple_reversal",
        "randomized_timing_placebo",
        "one_period_delay",
        "volatility_matched",
        "ablation",
        "complexity_rule",
    }
    assert "CONTINUOUS_ONE_SEVENTH_ETH_BETA" == gauntlet["market_beta"]["name"]
    assert "Wednesday" in gauntlet["one_period_delay"]["rule"]
    assert "SHA256" in gauntlet["randomized_timing_placebo"]["rule"]
    assert "without replacement" in gauntlet["volatility_matched"]["rule"]


def test_all_authority_locks_remain_closed() -> None:
    contract = _load()
    locks = contract["authority_locks"]
    assert locks == {
        "stage1_started": False,
        "stage1_pnl_opened": False,
        "baseline_pnl_opened": False,
        "protected_oos_opened": False,
        "genuine_forward_opened": False,
        "broker_connected": False,
        "trade_authority": False,
        "promotion_authority": False,
    }
