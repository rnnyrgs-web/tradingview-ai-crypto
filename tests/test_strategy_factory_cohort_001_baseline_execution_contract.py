from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COHORTS = ROOT / "orchestration" / "cohorts"
CONTRACT_PATH = COHORTS / "strategy_factory_cohort_001_baseline_execution_contract.json"
BUNDLE_PATH = COHORTS / "strategy_factory_cohort_001_candidate_bound_baselines.json"
PLAN_PATH = COHORTS / "strategy_factory_cohort_001_baseline_halving_plan.json"
BINDING_PATH = COHORTS / "strategy_factory_cohort_001_stage1_binding.json"
EXECUTION_PATH = COHORTS / "strategy_factory_cohort_001_stage1_execution_contract.json"
RUNNER_PATH = COHORTS / "strategy_factory_cohort_001_stage1_runner.py"

EXPECTED_ACTIVE = (
    "DISC-RESIDUAL-REV-001-v1",
    "DISC-SIGNED-VOLUME-DRIFT-001-v1",
    "DISC-LOWVOL-DRIFT-REV-001-v1",
    "DISC-MODERATEVOL-AUTOCORR-001-v1",
    "DISC-RANGE-AUCTION-REV-001-v1",
)


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _canonical_sha256(payload: dict) -> str:
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _git_blob_sha(path: Path) -> str:
    raw = path.read_bytes()
    return hashlib.sha1(b"blob " + str(len(raw)).encode("ascii") + b"\0" + raw).hexdigest()


def test_baseline_execution_contract_is_outcome_blind_and_self_authenticated() -> None:
    contract = _load(CONTRACT_PATH)
    claimed = contract["baseline_execution_contract_sha256"]
    unsigned = dict(contract)
    unsigned.pop("baseline_execution_contract_sha256")
    assert _canonical_sha256(unsigned) == claimed
    assert contract["status"] == "OUTCOME_BLIND_FROZEN_WAIT_STAGE1_SURVIVORS"
    assert contract["authority_locks"] == {
        "baseline_outcomes_read_to_form_contract": False,
        "broker_connected": False,
        "genuine_forward_opened": False,
        "post_outcome_control_definition_change_allowed": False,
        "post_outcome_seed_redraw_allowed": False,
        "promotion_authority": False,
        "protected_oos_opened": False,
        "stage1_outcomes_read_to_form_contract": False,
        "trade_authority": False,
        "validation_window_extension_allowed": False,
    }


def test_contract_is_bound_to_frozen_bundle_plan_and_exact_stage1_sources() -> None:
    contract = _load(CONTRACT_PATH)
    bundle = _load(BUNDLE_PATH)
    plan = _load(PLAN_PATH)
    binding = _load(BINDING_PATH)
    execution = _load(EXECUTION_PATH)

    bundle_unsigned = dict(bundle)
    bundle_claimed = bundle_unsigned.pop("bundle_sha256")
    assert _canonical_sha256(bundle_unsigned) == bundle_claimed
    assert contract["source_candidate_bound_bundle"] == {
        "bundle_id": bundle["bundle_id"],
        "bundle_sha256": bundle_claimed,
    }

    plan_unsigned = dict(plan)
    plan_claimed = plan_unsigned.pop("planning_contract_sha256")
    assert _canonical_sha256(plan_unsigned) == plan_claimed
    assert contract["source_baseline_halving_plan"] == {
        "cohort_planning_id": plan["cohort_planning_id"],
        "planning_contract_sha256": plan_claimed,
    }

    source = contract["source_stage1"]
    assert source["binding_id"] == binding["binding_id"]
    assert source["binding_receipt_sha256"] == binding["binding_receipt_sha256"]
    assert source["execution_contract_id"] == execution["contract_id"]
    assert source["execution_contract_sha256"] == execution["execution_contract_sha256"]
    assert source["runner_path"] == str(RUNNER_PATH.relative_to(ROOT))
    assert source["runner_git_blob_sha"] == _git_blob_sha(RUNNER_PATH)


def test_all_five_controls_bind_exact_candidate_identities_and_have_distinct_control_hashes() -> None:
    contract = _load(CONTRACT_PATH)
    bundle = _load(BUNDLE_PATH)
    bundle_rows = {row["fingerprint_id"]: row for row in bundle["candidate_bound_baselines"]}
    rows = contract["candidate_controls"]

    assert tuple(row["fingerprint_id"] for row in rows) == EXPECTED_ACTIVE
    assert len({row["control_bundle_sha256"] for row in rows}) == len(EXPECTED_ACTIVE)

    for row in rows:
        candidate_id = row["fingerprint_id"]
        frozen = bundle_rows[candidate_id]
        assert row["scientific_design_sha256"] == frozen["scientific_design_sha256"]
        assert row["strategy_behavior_sha256"] == frozen["strategy_behavior_sha256"]
        assert row["contract_sha256"] == frozen["contract_sha256"]
        unsigned = dict(row)
        claimed = unsigned.pop("control_bundle_sha256")
        assert _canonical_sha256(unsigned) == claimed
        assert row["primary"]["control_id"]
        assert row["primary"]["definition"]
        assert row["common_control_ids"] == ["DELAYED-SIGNAL-1H-v1", "RANDOMIZED-TIMING-MATCHED-v1"]


def test_primary_and_ablation_semantics_are_exact_not_post_result_prose_placeholders() -> None:
    contract = _load(CONTRACT_PATH)
    rows = {row["fingerprint_id"]: row for row in contract["candidate_controls"]}

    residual = rows["DISC-RESIDUAL-REV-001-v1"]
    assert residual["primary"]["definition"]["gate"] == (
        "abs(zscore(signal_value vs reference mean/population_std)) >= 2.0"
    )
    assert residual["primary"]["definition"]["reference"] == (
        "prior 720 fully formed follower 6h returns ending strictly before t"
    )
    assert {x["control_id"] for x in residual["ablations"]} == {
        "RESIDUAL-ABLATION-UNHEDGED-CANDIDATE-EVENT-v1",
        "RESIDUAL-ABLATION-NO-CORRELATION-GATE-v1",
    }

    signed = rows["DISC-SIGNED-VOLUME-DRIFT-001-v1"]
    assert signed["primary"]["definition"]["gate"] == (
        "abs(4h return) >= Type-7 90th percentile of reference"
    )
    assert signed["ablations"][0]["definition"]["removed_condition"] == (
        "long close_location>=0.80 / short close_location<=0.20"
    )

    lowvol = rows["DISC-LOWVOL-DRIFT-REV-001-v1"]
    assert lowvol["primary"]["definition"]["removed_condition"].startswith("mean quote volume last 8h")
    assert {x["control_id"] for x in lowvol["ablations"]} == {
        "LOWVOL-ABLATION-ORDINARY-HIGH-PARTICIPATION-v1",
        "LOWVOL-ABLATION-NO-SHOCK-EXCLUSION-v1",
    }

    moderate = rows["DISC-MODERATEVOL-AUTOCORR-001-v1"]
    assert moderate["primary"]["definition"]["realized_volatility_regime"] == "none"
    assert moderate["primary"]["definition"]["participation_guard"] == "none"
    assert moderate["ablations"][0]["definition"]["retained_condition"] == (
        "current quote volume between trailing-720h 40th and 90th percentiles"
    )

    auction = rows["DISC-RANGE-AUCTION-REV-001-v1"]
    assert auction["primary"]["definition"]["removed_condition"] == "24h efficiency_ratio <=0.25"
    assert auction["ablations"][0]["definition"]["gate"] == (
        "abs(6h return) >= Type-7 90th percentile of reference"
    )


def test_common_controls_are_single_draw_pit_safe_and_not_recomputed_after_delay() -> None:
    contract = _load(CONTRACT_PATH)
    delayed = contract["common_controls"]["one_bar_delayed_signal"]
    randomized = contract["common_controls"]["randomized_timing"]

    assert "Do not recompute" in delayed["signal_formation"]
    assert "exactly one additional completed 1h bar" in delayed["entry"]
    assert randomized["single_draw"] is True
    assert randomized["redraw_after_results"] is False
    assert "without replacement" in randomized["matching"]
    assert "training and validation" in randomized["matching"]
    assert "before any forward return is read" in randomized["eligible_pool"]


def test_signed_volume_proxy_note_is_diagnostic_not_an_economic_falsifier() -> None:
    contract = _load(CONTRACT_PATH)
    rows = {row["fingerprint_id"]: row for row in contract["candidate_controls"]}
    diagnostics = rows["DISC-SIGNED-VOLUME-DRIFT-001-v1"]["non_economic_diagnostics"]
    assert len(diagnostics) == 1
    assert diagnostics[0]["diagnostic_id"] == "SIGNED-VOLUME-PROXY-LABEL-v1"
    assert "no P&L score and no pass/fail authority" in diagnostics[0]["definition"]


def test_global_control_scoring_preserves_stage1_chronology_cost_and_authority_locks() -> None:
    contract = _load(CONTRACT_PATH)
    global_rules = contract["global_execution_semantics"]
    assert global_rules["costs_bps"] == [24.0, 48.0, 72.0]
    assert global_rules["protected_start_utc"] == "2026-09-01T00:00:00Z"
    assert global_rules["score_only_after_stage1_survival"] is True
    assert "never inflate independent-event counts" in global_rules["independent_event_clustering"]
    assert "fixed 1/3-NAV portfolio slot" in global_rules["portfolio_slot"]
