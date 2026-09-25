from orchestration.trusted_executor_manifest_audit import audit_executor_manifest


def test_executor_manifest_audit_proves_current_bundle_and_change_provenance():
    """A stale digest or unaudited behavior change must fail the audit."""
    audit = audit_executor_manifest("restrictive_group_abstention_v1")

    assert audit == {
        "schema_version": 1,
        "execution_rule": "restrictive_group_abstention_v1",
        "implementation_id": (
            "research_adaptive_accuracy._evaluate_frozen_filter@v3-import-closure"
        ),
        "previous_bundle_sha256": (
            "de7a1c4208372620f2310d025087b45bbe65fd8a565272d19421fd561b6db8b7"
        ),
        "registered_bundle_sha256": (
            "041a4e363604f58c7cf4d92287d0ca33b4d7e8a4d0b8dc01ee5d7acaa33e55d7"
        ),
        "computed_bundle_sha256": (
            "041a4e363604f58c7cf4d92287d0ca33b4d7e8a4d0b8dc01ee5d7acaa33e55d7"
        ),
        "behavior_change_paths": ["signal_development.py"],
        "change_reason": (
            "Reject non-finite compute-cost and signal-quality priority inputs before "
            "they can affect autonomous research ranking."
        ),
        "dependency_paths": [
            "calibration.py",
            "config.py",
            "profitability_learning/__init__.py",
            "profitability_learning/contracts.py",
            "research_adaptive_accuracy.py",
            "research_experiment_factory.py",
            "research_heavy_experiment_scheduler.py",
            "research_learning.py",
            "research_quant_science_factory.py",
            "selective_precision.py",
            "signal_development.py",
            "utils.py",
        ],
        "resource_paths": ["orchestration/signal_development_objective.json"],
    }
