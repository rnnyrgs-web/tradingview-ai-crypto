from basis_observability import compact_basis_falsification
import continuous_coordinator as coordinator


def test_retired_funding_observability_cannot_look_active_without_worker_evidence():
    projection = compact_basis_falsification({})

    assert projection["active"] is False
    assert projection["retired"] is True
    assert projection["candidate_status"] == "rejected_retired"
    assert projection["production_authority"] is False
    assert projection["signal_authority"] is False
    assert projection["paper_authority"] is False
    assert projection["promotion_authority"] is False
    assert projection["broker_authority"] is False


def test_coordinator_preserves_retired_status_for_legacy_projection():
    payload = coordinator.observability_log_payload({})

    assert payload["basis_falsification"]["active"] is False
    assert payload["basis_falsification"]["retired"] is True
    assert payload["basis_falsification"]["candidate_status"] == "rejected_retired"
