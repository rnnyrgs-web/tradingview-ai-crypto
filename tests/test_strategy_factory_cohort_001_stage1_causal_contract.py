import json
from pathlib import Path


CONTRACT_PATH = Path(
    "orchestration/cohorts/strategy_factory_cohort_001_stage1_execution_contract.json"
)


def test_execution_contract_locks_causal_one_third_nav_sizing() -> None:
    contract = json.loads(CONTRACT_PATH.read_text(encoding="utf-8"))
    semantics = contract["global_numerical_semantics"]

    assert "fixed 1/3 NAV gross portfolio slot at its own entry" in semantics[
        "independent_event_return"
    ]
    assert "unused slots remain cash" in semantics["independent_event_return"]
    assert "later overlapping signals cannot resize earlier trades" in semantics[
        "independent_event_return"
    ]
    assert "no normalization by final cluster size or gross_notional" in semantics[
        "independent_event_return"
    ]
    assert "Clustering never changes entry-time portfolio sizing" in semantics[
        "independence_accounting"
    ]
    assert "gross_notional never becomes a cross-trade or future-cluster portfolio weight" in semantics[
        "cost_semantics"
    ]
