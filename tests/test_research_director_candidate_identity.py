from research_director import build_mission, claim_mission


def test_mission_and_claim_preserve_frozen_candidate_identity():
    mission = build_mission(
        lane="feature-research",
        horizon="24h",
        direction="BUY_SELL_WAIT",
        theme="candidate-review",
        hypothesis="falsify the frozen candidate",
        expected_information_gain=0.8,
        expected_signal_impact=0.7,
        sample_readiness=0.9,
        novelty=0.4,
        candidate_fingerprint="fp-001",
        hypothesis_id="H-001",
        permission="FALSIFICATION",
        experiment_id="EXP-001",
        git_sha="git-abc",
        dataset_sha256="data-abc",
        strategy_contract_sha256="contract-abc",
    )
    payload = mission.to_dict()
    assert payload["candidate_fingerprint"] == "fp-001"
    assert payload["hypothesis_id"] == "H-001"
    assert payload["permission"] == "FALSIFICATION"
    assert payload["git_sha"] == "git-abc"
    assert payload["dataset_sha256"] == "data-abc"
    assert payload["strategy_contract_sha256"] == "contract-abc"

    claim = claim_mission(mission, worker_id="worker-1")
    claimed = claim.to_dict()
    assert claimed["candidate_fingerprint"] == "fp-001"
    assert claimed["hypothesis_id"] == "H-001"
    assert claimed["permission"] == "FALSIFICATION"
    assert claimed["git_sha"] == "git-abc"
    assert claimed["dataset_sha256"] == "data-abc"
    assert claimed["strategy_contract_sha256"] == "contract-abc"


def test_permission_rejects_unknown_values():
    try:
        build_mission(
            lane="feature-research",
            horizon="24h",
            direction="BUY_SELL_WAIT",
            theme="candidate-review",
            hypothesis="falsify the frozen candidate",
            expected_information_gain=0.8,
            expected_signal_impact=0.7,
            sample_readiness=0.9,
            novelty=0.4,
            permission="MUTATE_WHATEVER",
        )
    except ValueError as exc:
        assert "permission" in str(exc)
    else:
        raise AssertionError("unknown mission permission must fail closed")
