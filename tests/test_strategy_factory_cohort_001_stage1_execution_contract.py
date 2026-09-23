import hashlib
import json
from pathlib import Path


CONTRACT_PATH = Path("orchestration/cohorts/strategy_factory_cohort_001_stage1_execution_contract.json")
BINDING_PATH = Path("orchestration/cohorts/strategy_factory_cohort_001_stage1_binding.json")


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _self_digest(payload: dict) -> str:
    canonical_payload = dict(payload)
    canonical_payload.pop("execution_contract_sha256", None)
    canonical = json.dumps(
        canonical_payload,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


def test_execution_contract_digest_and_binding_are_frozen() -> None:
    contract = _load(CONTRACT_PATH)
    binding = _load(BINDING_PATH)

    assert contract["execution_contract_sha256"] == _self_digest(contract)
    assert contract["source_stage1_binding"]["binding_id"] == binding["binding_id"]
    assert (
        contract["source_stage1_binding"]["binding_receipt_sha256"]
        == binding["binding_receipt_sha256"]
    )


def test_execution_contract_covers_exactly_bound_stage1_candidates() -> None:
    contract = _load(CONTRACT_PATH)
    binding = _load(BINDING_PATH)

    expected = {
        row["fingerprint_id"] for row in binding["eligible_stage1_candidates"]
    }
    assert set(contract["candidate_specific_semantics"]) == expected
    assert len(expected) == 6


def test_execution_contract_preserves_stage1_gate_and_cost_authority() -> None:
    contract = _load(CONTRACT_PATH)
    binding = _load(BINDING_PATH)
    semantics = contract["global_numerical_semantics"]
    sample_gate = semantics["minimum_sample_gate"]
    cheap_gate = binding["cheap_stage_gate"]
    costs = binding["stage1_cost_contract"]["stress_totals_bps"]

    assert sample_gate["training_independent_events"] == cheap_gate["minimum_independent_trades_train"]
    assert sample_gate["validation_independent_events"] == cheap_gate["minimum_independent_trades_validation"]
    assert costs == {"1x": 24.0, "2x": 48.0, "3x": 72.0}
    assert "72-bps" in semantics["three_x_gate"]
    assert "24-bps" in semantics["base_economic_gate"]
    assert "Raw trade count is diagnostic only" in semantics["independence_accounting"]
    assert "remove the single best independent event" in semantics["single_winner_dependence_veto"]
    assert "50%" in semantics["catastrophic_tail_veto"]


def test_execution_contract_remains_outcome_blind_and_research_only() -> None:
    contract = _load(CONTRACT_PATH)
    locks = contract["evidence_locks"]
    authority = contract["execution_authority"]

    assert locks == {
        "strategy_outcomes_read_to_form_contract": False,
        "protected_oos_opened": False,
        "genuine_forward_opened": False,
        "post_outcome_semantics_changes_allowed": False,
        "broker_connected": False,
        "trade_authority": False,
    }
    assert authority["may_implement_runner_before_parent_integration"] is True
    assert authority["may_execute_real_stage1_before_parent_515_integrates"] is False
    assert (
        authority[
            "may_execute_real_stage1_before_this_contract_is_reconciled_and_independently_reviewed"
        ]
        is False
    )
    assert authority["may_read_protected_oos"] is False
    assert authority["may_promote_strategy"] is False
    assert authority["may_trade"] is False


def test_validation_halves_are_fixed_before_outcomes() -> None:
    contract = _load(CONTRACT_PATH)
    halves = contract["global_numerical_semantics"]["validation_halves"]

    assert halves == [
        {
            "id": "VAL-H1",
            "entry_start_utc": "2026-05-01T00:00:00Z",
            "latest_exit_row_utc": "2026-06-30T23:00:00Z",
        },
        {
            "id": "VAL-H2",
            "entry_start_utc": "2026-07-01T00:00:00Z",
            "latest_exit_row_utc": "2026-08-31T23:00:00Z",
        },
    ]


def test_candidate_semantics_close_known_posthoc_degrees_of_freedom() -> None:
    contract = _load(CONTRACT_PATH)
    candidates = contract["candidate_specific_semantics"]

    residual = candidates["DISC-RESIDUAL-REV-001-v1"]
    assert "Each historical residual must use its own contemporaneous 336h beta" in residual["zscore_reference"]
    assert "Gross committed notional is 1+abs(beta_i)" in residual["execution"]

    signed_volume = candidates["DISC-SIGNED-VOLUME-DRIFT-001-v1"]
    assert "prior 720 completed quote_volume bars" in signed_volume["signed_volume"]
    assert "Zero candle body contributes zero" in signed_volume["signed_volume"]

    weekend = candidates["DISC-WEEKEND-NORMALIZE-001-v1"]
    assert "20 distinct UTC Monday-Friday calendar dates" in weekend["prior_20_weekdays"]
    assert "Never widen the calendar window" in weekend["power"]

    range_reversion = candidates["DISC-RANGE-AUCTION-REV-001-v1"]
    assert "current row i is excluded" in range_reversion["prior_range"]
    assert "Actual next-bar entry open" in range_reversion["stop_anchor"]
    assert "record BOTH reason flags" in range_reversion["exit_precedence"]
