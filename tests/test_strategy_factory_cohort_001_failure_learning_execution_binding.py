import json
from pathlib import Path

from orchestration.cohorts.strategy_factory_cohort_001_failure_learning_adapter import (
    EXECUTION_CONTRACT_SHA256,
)


EXECUTION_CONTRACT_PATH = Path(
    "orchestration/cohorts/strategy_factory_cohort_001_stage1_execution_contract.json"
)
ADAPTER_CONTRACT_PATH = Path(
    "orchestration/cohorts/strategy_factory_cohort_001_failure_learning_adapter_contract.json"
)


def test_failure_learning_adapter_binds_exact_causal_execution_contract() -> None:
    execution = json.loads(EXECUTION_CONTRACT_PATH.read_text(encoding="utf-8"))
    adapter = json.loads(ADAPTER_CONTRACT_PATH.read_text(encoding="utf-8"))
    execution_sha = execution["execution_contract_sha256"]

    assert execution_sha == EXECUTION_CONTRACT_SHA256
    assert (
        adapter["source_stage1_execution_contract"]["execution_contract_sha256"]
        == execution_sha
    )
    assert (
        adapter["authority"]["required_bindings"]["stage1_execution_contract_sha256"]
        == execution_sha
    )
    assert adapter["source_stage1_execution_contract"]["source_head_sha_observed"] == (
        "46f67731eb128eb97da47ca11e879d9f5257aaa6"
    )
