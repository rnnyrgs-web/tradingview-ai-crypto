from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
TRADABILITY = ROOT / "money_intelligence" / "2x_trusted_final_resolution_tradability_binding_v1.json"
GATE = ROOT / "money_intelligence" / "2x_trusted_final_resolution_preimplementation_gate_v1.json"


def _load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def test_crossing_and_execution_must_be_cotemporal() -> None:
    contract = _load(TRADABILITY)
    alignment = contract["price_microstructure_time_alignment"]

    assert alignment["policy_id"] == "CROSSING_EXECUTION_INTERVAL_INTERSECTION_V1"
    assert "same provider event instant" in alignment["exact_event_rule"]
    assert "non-empty intersection" in alignment["interval_rule"]
    assert "not a join tolerance" in alignment["staleness_rule"]
    assert "PRICE_HIT_TRADABILITY_UNKNOWN" in alignment["empty_intersection_rule"]

    crossing = contract["crossing_side_execution"]
    assert "intersects the authenticated target-crossing support interval" in crossing["timing"]
    assert "does not overlap in event time" in crossing["unknown_rule"]


def test_time_alignment_identity_is_frozen_and_fingerprint_bound() -> None:
    contract = _load(TRADABILITY)
    policy = contract["ex_ante_execution_policy"]
    fingerprint_members = set(contract["final_resolution_fingerprint_must_bind"])

    assert "crossing_price_microstructure_time_alignment_policy_id" in policy["must_bind"]
    assert "crossing_price_microstructure_time_alignment_policy_id_and_overlap_bounds" in fingerprint_members

    attacks = "\n".join(contract["mandatory_red_green_tests"])
    assert "60-minute staleness ceiling" in attacks
    assert "nearest-neighbor joined" in attacks
    assert "trusted intersection" in attacks


def test_preimplementation_gate_requires_runtime_interval_intersection() -> None:
    gate = _load(GATE)
    formation = set(gate["formation_binding"]["must_bind"])
    guards = "\n".join(gate["mandatory_ci_guards"])
    implementation = "\n".join(gate["implementation_gate"]["required_before_any_authority"])

    assert "crossing_price_microstructure_time_alignment_policy_id" in formation
    assert "support intervals must overlap" in guards
    assert "staleness ceiling is never a join tolerance" in guards
    assert "co-temporal price/microstructure interval intersection" in implementation
