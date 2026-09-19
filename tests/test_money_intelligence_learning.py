from copy import deepcopy
from datetime import datetime, timedelta, timezone
import sqlite3

import pytest

from money_intelligence_learning.contracts import freeze_mechanism, make_evidence
from money_intelligence_learning.evolution import evolve_mechanism
from money_intelligence_learning.features import derive_relative_impacts
from money_intelligence_learning.memory import Memory
from money_intelligence_learning.research_bridge import emit_research_hypotheses, rank_research_missions
from money_intelligence_learning.runtime import process_observation


BASE = datetime(2026, 1, 1, tzinfo=timezone.utc)


def iso(days=0, hours=0):
    return (BASE + timedelta(days=days, hours=hours)).isoformat()


def mechanism():
    return freeze_mechanism(
        {
            "schema_version": 1,
            "mechanism_key": "wrapper-flow-new-outside-capital",
            "claim": "New outside wrapper capital creates marginal spot demand relative to available liquidity.",
            "causal_chain": [
                "outside cash enters wrapper",
                "authorized participant sources underlying asset",
                "demand meets finite liquidity",
                "asset reprices",
            ],
            "expected_direction": "POSITIVE",
            "expected_horizon_days": 90,
            "falsifier": "Holdings growth is explained by legacy inventory or in-kind transfer without marginal sourcing.",
            "transmission_variables": ["external_cash_flow", "spot_sourcing", "available_liquidity"],
            "matched_control_design": {
                "control_group": "wrappers with holdings growth but no verified outside cash",
                "matching_variables": ["asset_size", "liquidity_regime", "market_beta"],
                "failure_condition": "treated assets do not outperform matched controls after the frozen horizon",
            },
            "regime_scope": ["liquid_crypto", "wrapper_creation_available"],
            "frozen_at": iso(),
            "information_cutoff": iso(),
            "prior_confidence": 0.35,
            "decay_half_life_days": 30,
            "minimum_supporting_sources": 2,
            "minimum_matched_controls": 1,
            "search_breadth": 1,
            "target_assets": ["BTC"],
            "downstream_lanes": ["BIG_MOVE", "STRATEGY_COMPONENT"],
        }
    )


def evidence(contract, kind, strength, day, source, independence_key, *, control=None, narrative=None):
    return make_evidence(
        contract,
        {
            "schema_version": 1,
            "evidence_kind": kind,
            "observed_at": iso(day),
            "published_at": iso(day, 1),
            "available_at": iso(day, 2),
            "information_cutoff": iso(day, 2),
            "source": {
                "publisher": source,
                "uri": f"https://example.test/{source}/{day}",
                "source_type": "PRIMARY",
            },
            "independence_key": independence_key,
            "strength": strength,
            "structured_fact": {"metric": "verified_external_cash_flow", "value": 100 + day},
            "matched_control": control,
            "narrative_summary": narrative,
        },
    )


def test_point_in_time_contract_rejects_post_hoc_or_future_evidence():
    contract = mechanism()
    before_freeze = {
        "schema_version": 1,
        "evidence_kind": "SUPPORT",
        "observed_at": iso(-2),
        "published_at": iso(-1, 1),
        "available_at": iso(-1, 2),
        "information_cutoff": iso(-1, 2),
        "source": {"publisher": "sec", "uri": "https://example.test/sec", "source_type": "PRIMARY"},
        "independence_key": "pre-freeze",
        "strength": 0.8,
        "structured_fact": {"value": 1},
    }
    with pytest.raises(ValueError, match="frozen before evidence"):
        make_evidence(contract, before_freeze)

    future = deepcopy(before_freeze)
    future.update(
        observed_at=iso(1),
        published_at=iso(1, 1),
        available_at=iso(2),
        information_cutoff=iso(1, 2),
        independence_key="future",
    )
    with pytest.raises(ValueError, match="information cutoff"):
        make_evidence(contract, future)


def test_support_contradiction_control_and_decay_update_same_mechanism():
    contract = mechanism()
    support = evidence(contract, "SUPPORT", 0.9, 1, "issuer", "issuer-cash-ledger")
    control_support = evidence(
        contract,
        "MATCHED_CONTROL_SUPPORT",
        0.8,
        2,
        "control-study",
        "matched-control-1",
        control={"control_id": "control-1", "outcome": "SUPPORTS", "predeclared": True},
    )
    supported = evolve_mechanism(contract, [support, control_support], as_of=iso(2, 2))
    assert supported["status"] == "SUPPORTED"
    assert supported["confidence"] == pytest.approx(0.735)
    assert supported["support_count"] == 2
    assert supported["matched_control_count"] == 1

    contradiction = evidence(contract, "CONTRADICTION", 0.8, 3, "auditor", "inventory-audit")
    control_failure = evidence(
        contract,
        "MATCHED_CONTROL_FAILURE",
        0.8,
        4,
        "control-study-2",
        "matched-control-2",
        control={"control_id": "control-2", "outcome": "CONTRADICTS", "predeclared": True},
    )
    weakened = evolve_mechanism(
        contract,
        [support, control_support, contradiction, control_failure],
        as_of=iso(4, 2),
    )
    assert weakened["confidence"] == pytest.approx(0.335)
    assert weakened["contradiction_count"] == 2
    assert weakened["status"] == "CONTRADICTED"

    stale = evolve_mechanism(contract, [support, control_support], as_of=iso(62, 2))
    assert stale["confidence"] == pytest.approx(0.44625)
    assert stale["status"] == "STALE"
    assert stale["decay_applied"] is True


def test_narrative_cannot_change_confidence_or_masquerade_as_evidence():
    contract = mechanism()
    terse = evidence(contract, "SUPPORT", 0.8, 1, "issuer", "same-fact", narrative="brief")
    florid = deepcopy(terse)
    florid["narrative_summary"] = "A compelling reflexive supercycle is definitely beginning."
    assert evolve_mechanism(contract, [terse], as_of=iso(1, 2))["confidence"] == evolve_mechanism(
        contract, [florid], as_of=iso(1, 2)
    )["confidence"]

    with pytest.raises(ValueError, match="evidence kind"):
        evidence(contract, "NARRATIVE", 1.0, 2, "commentator", "story-only")
    injected = deepcopy(terse)
    injected["narrative_score"] = 1.0
    with pytest.raises(ValueError, match="unexpected evidence fields"):
        evolve_mechanism(contract, [injected], as_of=iso(1, 2))


def test_independence_keys_cannot_amplify_repeated_source_evidence():
    contract = mechanism()
    first = evidence(contract, "SUPPORT", 0.9, 1, "issuer", "same-underlying-filing")
    relabel = evidence(contract, "SUPPORT", 0.9, 2, "aggregator", "same-underlying-filing")
    with pytest.raises(ValueError, match="duplicate independence key"):
        evolve_mechanism(contract, [first, relabel], as_of=iso(2, 2))


def metric(value, unit, day, source):
    return {
        "value": value,
        "unit": unit,
        "observed_at": iso(day),
        "available_at": iso(day, 1),
        "source_ref": source,
    }


def test_relative_impacts_are_point_in_time_and_missing_denominators_stay_unknown():
    impacts = derive_relative_impacts(
        {
            "flow": metric(10_000_000, "USD", 1, "flow-source"),
            "market_cap": metric(1_000_000_000, "USD", 1, "market-cap-source"),
            "adv": None,
            "liquidity": metric(50_000_000, "USD", 1, "depth-source"),
            "float": metric(100_000_000, "TOKEN", 1, "supply-source"),
            "issuance": metric(5_000_000, "TOKEN", 1, "issuance-source"),
            "demand": metric(12_500_000, "USD", 1, "demand-source"),
        },
        information_cutoff=iso(1, 2),
    )
    assert impacts["flow_to_market_cap"] == {"status": "KNOWN", "value": 0.01}
    assert impacts["demand_to_liquidity"] == {"status": "KNOWN", "value": 0.25}
    assert impacts["issuance_to_float"] == {"status": "KNOWN", "value": 0.05}
    assert impacts["flow_to_adv"]["status"] == "UNKNOWN"
    assert impacts["flow_to_float"]["status"] == "UNKNOWN"

    future = {"flow": metric(1, "USD", 3, "future"), "market_cap": metric(100, "USD", 1, "cap")}
    with pytest.raises(ValueError, match="information cutoff"):
        derive_relative_impacts(future, information_cutoff=iso(2))


def test_local_memory_is_immutable_replay_safe_and_survives_restart(tmp_path):
    path = tmp_path / "money-intelligence.sqlite"
    contract = mechanism()
    item = evidence(contract, "SUPPORT", 0.9, 1, "issuer", "issuer-cash-ledger")
    memory = Memory(path)
    memory.freeze(contract)
    memory.append_evidence(item)
    memory.append_evidence(deepcopy(item))

    snapshot = Memory(path, create=False).snapshot(as_of=iso(1, 2))
    assert list(snapshot["mechanisms"]) == [contract["mechanism_id"]]
    assert len(snapshot["evidence"]) == 1
    assert snapshot["mechanisms"][contract["mechanism_id"]]["state"]["confidence"] == pytest.approx(0.575)

    changed = deepcopy(item)
    changed["strength"] = 0.1
    with pytest.raises(ValueError, match="immutable"):
        memory.append_evidence(changed)

    with sqlite3.connect(path) as connection:
        connection.execute("update events set digest = ? where kind = 'evidence'", ("0" * 64,))
    with pytest.raises(ValueError, match="integrity"):
        Memory(path, create=False).snapshot(as_of=iso(1, 2))


def test_supported_mechanism_emits_fresh_provenance_bound_research_only_hypotheses(tmp_path):
    contract = mechanism()
    memory = Memory(tmp_path / "money-intelligence.sqlite")
    memory.freeze(contract)
    memory.append_evidence(evidence(contract, "SUPPORT", 0.9, 1, "issuer", "issuer-cash-ledger"))
    memory.append_evidence(
        evidence(
            contract,
            "MATCHED_CONTROL_SUPPORT",
            0.8,
            2,
            "control-study",
            "matched-control-1",
            control={"control_id": "control-1", "outcome": "SUPPORTS", "predeclared": True},
        )
    )
    snapshot = memory.snapshot(as_of=iso(2, 2))
    hypotheses = emit_research_hypotheses(snapshot)
    assert {row["lane"] for row in hypotheses} == {"BIG_MOVE", "STRATEGY_COMPONENT"}
    assert len({row["fingerprint"] for row in hypotheses}) == 2
    for row in hypotheses:
        assert row["source_mechanism_id"] == contract["mechanism_id"]
        assert row["source_evidence_ids"] == snapshot["mechanisms"][contract["mechanism_id"]]["state"]["evidence_ids"]
        assert row["status"] == "FROZEN_RESEARCH_HYPOTHESIS_REQUIRES_VALIDATION"
        assert row["research_only"] is True
        assert row["automatic_execution_authority"] is False
        assert row["strategy_mutation_authority"] is False
        assert row["trade_authority"] is False
        assert row["promotion_authority"] is False
        assert row["untouched_oos_authority"] is False

    missions = rank_research_missions(snapshot)
    assert {row["lane"] for row in missions} == {"big-move-intelligence", "strategy-component-research"}
    assert all(row["priority"] > 0 for row in missions)
    assert all(row["source_hypothesis_fingerprint"] in {item["fingerprint"] for item in hypotheses} for row in missions)
    assert all(row["source_evidence_ids"] for row in missions)
    assert all(row["automatic_execution_authority"] is False for row in missions)
    assert all(row["trade_authority"] is False for row in missions)


def test_runtime_loop_persists_updates_and_removes_routing_when_evidence_reverses(tmp_path):
    contract = mechanism()
    memory = Memory(tmp_path / "runtime.sqlite")
    support = evidence(contract, "SUPPORT", 0.9, 1, "issuer", "issuer-cash-ledger")
    first = process_observation(memory, contract, support, as_of=iso(1, 2))
    replay = process_observation(memory, deepcopy(contract), deepcopy(support), as_of=iso(1, 2))
    assert replay == first
    assert first["state"]["confidence"] == pytest.approx(0.575)
    assert len(memory.snapshot(as_of=iso(1, 2))["evidence"]) == 1

    contradiction = evidence(contract, "CONTRADICTION", 1.0, 2, "auditor", "inventory-audit")
    reversed_state = process_observation(memory, contract, contradiction, as_of=iso(2, 2))
    assert reversed_state["state"]["confidence"] == pytest.approx(0.325)
    assert reversed_state["state"]["status"] == "CONTRADICTED"
    assert reversed_state["research_hypotheses"] == []
    assert reversed_state["ranked_missions"] == []
    assert reversed_state["trade_authority"] is False
    assert reversed_state["promotion_authority"] is False
