import json

import pytest

from orchestration import trusted_executor_manifest_audit
from orchestration.trusted_executor_manifest_audit import audit_executor_manifest


def test_executor_manifest_audit_proves_current_bundle_and_change_provenance():
    """A stale digest or unaudited behavior change must fail the audit."""
    audit = audit_executor_manifest("restrictive_group_abstention_v1")

    assert audit == {
        "schema_version": 2,
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
        "base_commit_sha": "1860f917c829ee5db4f4cd36404bf9702b6b680a",
        "base_manifest_sha256": (
            "4de065ae3ee8231d783362f4d0a44cf70d54f7ac4f25236f0a7d3d54ba5457c0"
        ),
        "bundle_change_paths": ["signal_development.py"],
        "behavior_change_files": {
            "continuous_specialist_factory.py": (
                "277fc43859f4fefb87cfb45d3cd1a1fed63b19435cbac8aaa06a4972c4c34612"
            ),
            "orchestration/profitability_priority.py": (
                "508a5cf055b6cccf51141ed4c49a375cd01c721a0a0c2fe4d725580e457461fa"
            ),
            "profitability_learning/runtime.py": (
                "1a821532340302721a805af694a8c8dc11603fd22ef7a21d20e0a25ce364f23a"
            ),
            "research_director.py": (
                "23139eaf8fb001b6d8c6fcb2695b3386975fe37042330d464f86123757c95c5a"
            ),
            "research_paper_loss_attribution.py": (
                "729e9019a4420a2a9b6d49003d6952094328e5d6565cedf9a2ce740fad1eef21"
            ),
            "signal_development.py": (
                "a968c61121c064beff439bb72bc56481025c1c57539a4fb573253dab747c3c30"
            ),
        },
        "change_reason": (
            "Reject non-finite ranking inputs across mission admission, specialist "
            "cohorts, durable queue feedback, paper-loss prioritization, and the "
            "trusted signal-development executor; only signal_development.py changes "
            "that executor bundle."
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


def test_executor_manifest_audit_rejects_unreceipted_behavior_file_drift(
    tmp_path, monkeypatch
):
    """Every behavior-changing file named by the receipt is content-bound."""
    receipt = json.loads(
        trusted_executor_manifest_audit.RECEIPT_PATH.read_text(encoding="utf-8")
    )
    receipt["behavior_change_files"]["research_director.py"] = "0" * 64
    receipt_path = tmp_path / "receipts.jsonl"
    receipt_path.write_text(json.dumps(receipt) + "\n", encoding="utf-8")
    monkeypatch.setattr(
        trusted_executor_manifest_audit, "RECEIPT_PATH", receipt_path
    )

    with pytest.raises(ValueError, match="behavior file digest is stale"):
        audit_executor_manifest("restrictive_group_abstention_v1")
