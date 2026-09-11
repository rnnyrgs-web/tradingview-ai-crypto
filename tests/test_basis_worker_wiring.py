from continuous_worker_army import (
    NATURAL_HISTORY_RECHECK_SECONDS,
    SUMMARY_ENV_BY_SCRIPT,
    WORKERS,
    _success_recheck_delay_seconds,
)


def test_basis_falsification_is_wired_without_new_concurrency_lane():
    specs = [spec for spec in WORKERS if spec.name == "basis-falsification-btc"]
    assert len(specs) == 1
    spec = specs[0]

    assert spec.script == "basis_falsification_runner.py"
    assert spec.compute_class == "heavy"
    assert spec.env == {
        "BASIS_RESEARCH_BASE": "BTC",
        "BASIS_RESEARCH_TARGET_POINTS": "4000",
        "BASIS_RESEARCH_MAX_PAGES": "40",
    }
    assert SUMMARY_ENV_BY_SCRIPT[spec.script] == "BASIS_FALSIFICATION_SUMMARY_PATH"
    assert _success_recheck_delay_seconds(spec, {"research_only": True}) == NATURAL_HISTORY_RECHECK_SECONDS
