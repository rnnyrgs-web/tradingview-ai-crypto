from __future__ import annotations

import json
from pathlib import Path

from orchestration.strategy_factory_cohort_001_admission import build_canonical_admission_receipt


ROOT = Path(__file__).resolve().parents[1]
RECEIPT_PATH = (
    ROOT
    / "orchestration"
    / "cohorts"
    / "strategy_factory_cohort_001_canonical_admission.json"
)


def test_committed_cohort_001_admission_receipt_matches_canonical_regeneration() -> None:
    committed = json.loads(RECEIPT_PATH.read_text(encoding="utf-8"))
    regenerated = build_canonical_admission_receipt()
    assert committed == regenerated
