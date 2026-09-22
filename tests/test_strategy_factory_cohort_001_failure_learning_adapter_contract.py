from __future__ import annotations

import hashlib
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONTRACT_PATH = (
    ROOT
    / "orchestration"
    / "cohorts"
    / "strategy_factory_cohort_001_failure_learning_adapter_contract.json"
)


def _load() -> dict:
    return json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))


def test_failure_learning_adapter_contract_identity_is_deterministic() -> None:
    payload = _load()
    detached = dict(payload)
    expected = detached.pop("contract_sha256")
    detached.pop("contract_hash_definition")
    encoded = json.dumps(
        detached,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    assert hashlib.sha256(encoded).hexdigest() == expected


def test_failure_learning_adapter_preserves_frozen_cost_and_independence_semantics() -> None:
    payload = _load()
    mapping = payload["mapping"]
    assert mapping["validation.trades"] == "validation.independent_events"
    assert payload["scientific_rules"]["raw_trade_count_may_substitute_for_independent_validation_events"] is False
    assert payload["scientific_rules"]["cost_stress_must_exactly_cover_frozen_multipliers"] == [1.0, 2.0, 3.0]
    rows = mapping["cost_stress"]
    assert [row["multiplier"] for row in rows] == [1.0, 2.0, 3.0]
    assert rows[0]["net_mean_bps"] == "validation.mean_24bps * 10000"
    assert rows[1]["net_mean_bps"] == "validation.mean_48bps * 10000"
    assert rows[2]["net_mean_bps"] == "validation.mean_72bps * 10000"
    assert payload["scientific_rules"]["no_new_48bps_promotion_gate_is_created"] is True


def test_failure_learning_adapter_fails_closed_on_authority_and_tail_semantics() -> None:
    payload = _load()
    authority = payload["authority"]
    locks = payload["evidence_locks"]
    assert authority["test_only_or_caller_supplied_results_may_mint_canonical_screen"] is False
    assert authority["required_source_evidence_status"] == "CERTIFIED_COHORT_DEVELOPMENT_ONLY"
    assert payload["scientific_rules"]["underpowered_catastrophic_tail_remains_rejection_eligible"] is True
    assert payload["scientific_rules"]["ordinary_underpower_without_sufficient_tail_evidence_is_inconclusive"] is True
    assert mapping_risk_keys(payload) == {
        "risk.worst_event_net_bps",
        "risk.winner_concentration_share",
        "risk.without_best_net_mean_bps",
    }
    assert authority["protected_oos_opened"] is False
    assert authority["genuine_forward_opened"] is False
    assert authority["broker_connected"] is False
    assert authority["trade_authority"] is False
    assert authority["promotion_authority"] is False
    assert locks["strategy_outcomes_read_to_form_contract"] is False
    assert locks["protected_oos_opened"] is False
    assert locks["genuine_forward_opened"] is False
    assert locks["post_outcome_mapping_changes_allowed"] is False


def mapping_risk_keys(payload: dict) -> set[str]:
    return {key for key in payload["mapping"] if key.startswith("risk.")}
