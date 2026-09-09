from continuous_specialist_factory import (
    ACTIVE_SPECIALIST_TARGET,
    CORE_SPECIALISTS,
    SPECIALISTS,
    VIRTUAL_HYPOTHESIS_ADDRESS_SPACE,
    build_specialist_snapshot,
    refresh_once,
)
from research_heavy_experiment_scheduler import MAX_HEAVY_EXPERIMENT_SLOTS
from virtual_specialist_lattice import build_virtual_descriptors


def test_factory_materializes_256_token_free_specialists_from_one_shared_read():
    assert len(CORE_SPECIALISTS) == 32
    assert ACTIVE_SPECIALIST_TARGET == 256
    assert len(SPECIALISTS) == 256
    assert len({spec.name for spec in SPECIALISTS}) == 256
    state = refresh_once([])
    assert state["logical_worker_count"] == 256
    assert state["core_worker_count"] == 32
    assert state["virtual_materialized_worker_count"] == 224
    assert state["ledger_reads_per_refresh"] == 1
    assert state["ai_calls_normal_operation"] == 0
    assert state["heavy_concurrency_increase"] is False


def test_virtual_namespace_is_huge_but_materialization_is_bounded_and_predeclared():
    assert VIRTUAL_HYPOTHESIS_ADDRESS_SPACE >= 10**18
    descriptors = build_virtual_descriptors(target_generated=224)
    assert len(descriptors) == 224
    assert len({row["name"] for row in descriptors}) == 224
    assert all(row["predeclared"] is True for row in descriptors)
    assert all(row["automatic_tuning"] is False for row in descriptors)
    assert all(row["research_only"] is True for row in descriptors)


def test_all_materialized_specialists_remain_research_only_and_fail_closed():
    reports = build_specialist_snapshot([])
    assert len(reports) == 256
    assert all(row["status"] == "awaiting_resolved_evidence" for row in reports.values())
    assert all(row["predeclared_grouping"] is True for row in reports.values())
    assert all(row["automatic_tuning"] is False for row in reports.values())
    assert all(row["trade_authority"] is False for row in reports.values())
    assert all(row["promotion_authority"] is False for row in reports.values())


def test_scaling_logical_specialists_does_not_raise_heavy_experiment_concurrency():
    assert MAX_HEAVY_EXPERIMENT_SLOTS == 1
