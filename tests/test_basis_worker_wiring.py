import inspect

import basis_falsification_runner
from continuous_worker_army import WORKERS


def test_rejected_funding_compatibility_runtime_is_retired_and_not_scheduled():
    specs = [spec for spec in WORKERS if spec.name == "basis-falsification-btc"]
    assert specs == []
    assert all(spec.script != "basis_falsification_runner.py" for spec in WORKERS)

    # Preserve the historical compatibility runtime for reproducible audit
    # evidence, but never spend an always-on worker slot re-running a frozen
    # candidate that has already failed falsification.
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
