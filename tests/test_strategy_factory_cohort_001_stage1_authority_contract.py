from __future__ import annotations

from dataclasses import fields
import json
from pathlib import Path

from orchestration.cohorts.strategy_factory_cohort_001_stage1_runner import (
    PartitionSummary,
    Stage1Result,
)


BINDING_PATH = Path("orchestration/cohorts/strategy_factory_cohort_001_stage1_binding.json")
CURRENT_COHORT_515_HEAD = "64aef8e5ec904694010c8c541182aa079bb6dd23"


def test_stage1_binding_names_the_current_cohort_parent_exactly() -> None:
    """A reconciled branch may not keep claiming an obsolete Cohort parent."""

    binding = json.loads(BINDING_PATH.read_text(encoding="utf-8"))
    assert binding["source_cohort_pr"] == 515
    assert binding["source_cohort_head_sha"] == CURRENT_COHORT_515_HEAD


def test_partition_summary_preserves_the_full_frozen_cost_ladder() -> None:
    """24/48/72-bps evidence must survive Stage-1 even though 48 bps is not a new gate."""

    names = {field.name for field in fields(PartitionSummary)}
    assert {"mean_24bps", "mean_48bps", "mean_72bps"}.issubset(names)


def test_current_runner_cannot_mint_canonical_stage1_evidence() -> None:
    """Caller/synthetic bars are diagnostic only until a certified adapter is reviewed."""

    by_name = {field.name: field for field in fields(Stage1Result)}
    canonical = by_name["canonical_stage1_evidence"]
    authority = by_name["evidence_authority"]

    assert canonical.default is False
    assert canonical.init is False
    assert authority.default == "TEST_ONLY_UNTRUSTED"
    assert authority.init is False
