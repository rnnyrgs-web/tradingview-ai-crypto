import inspect

import basis_falsification_runner
from continuous_worker_army import (
    NATURAL_HISTORY_RECHECK_SECONDS,
    SUMMARY_ENV_BY_SCRIPT,
    WORKERS,
    _success_recheck_delay_seconds,
)


def test_rejected_funding_compatibility_worker_is_zero_fetch_retired():
    specs = [spec for spec in WORKERS if spec.name == "basis-falsification-btc"]
    assert len(specs) == 1
    spec = specs[0]

    # Preserve the bounded compatibility lane for now, but make the actual job
    # a zero-fetch sentinel instead of repeatedly re-running rejected alpha.
    assert spec.script == "basis_falsification_runner.py"
    assert spec.compute_class == "heavy"
    assert SUMMARY_ENV_BY_SCRIPT[spec.script] == "BASIS_FALSIFICATION_SUMMARY_PATH"
    assert _success_recheck_delay_seconds(spec, {"research_only": True}) == NATURAL_HISTORY_RECHECK_SECONDS

    evidence = basis_falsification_runner.run()
    assert evidence["candidate_id"] == "DATA-FUNDING-001"
    assert evidence["evidence_conclusion"] == "retired_rejected_fingerprint"
    assert evidence["retired"] is True
    assert evidence["market_data_requests"] == 0
    assert evidence["evaluation_performed"] is False
    assert evidence["production_authority"] is False
    assert evidence["paper_authority"] is False
    assert evidence["promotion_authority"] is False
    assert evidence["broker_authority"] is False

    source = inspect.getsource(basis_falsification_runner)
    assert "collect_okx_funding_history" not in source
    assert "evaluate_primary_horizons" not in source
