import ffrizz_secondary_runner as runner


def _signal(action="WAIT", score=1.0, agreement=1, available=3, families=None):
    return {
        "action": action,
        "score": score,
        "independent_family_agreement": agreement,
        "available_family_count": available,
        "families": families or [],
    }


def test_abstention_diagnostics_distinguish_fixed_wait_gates_without_changing_thresholds():
    results = [{
        "horizon": "24h",
        "current_shadow_signals": [
            _signal(
                score=1.4,
                agreement=1,
                available=3,
                families=[{"family": "price_oi_correlation", "available": False, "reason": "oi_unavailable"}],
            ),
            _signal(score=2.5, agreement=2, available=4),
            _signal(action="SHADOW_BUY", score=3.4, agreement=2, available=4),
        ],
    }]

    diagnostic = runner._forward_abstention_diagnostics(results)

    assert diagnostic["diagnostic_only"] is True
    assert diagnostic["thresholds_unchanged"] is True
    assert diagnostic["backfill_used"] is False
    assert diagnostic["trade_authority"] is False
    assert diagnostic["promotion_authority"] is False
    assert diagnostic["signals_scored"] == 3
    assert diagnostic["action_counts"] == {"WAIT": 2, "SHADOW_BUY": 1, "SHADOW_SELL": 0}
    assert diagnostic["wait_gate_counts"]["insufficient_directional_agreement"] == 1
    assert diagnostic["wait_gate_counts"]["score_below_predeclared_threshold"] == 1
    assert diagnostic["wait_gate_counts"]["unexpected_wait_state"] == 0
    assert diagnostic["family_unavailable_counts"] == {"price_oi_correlation:oi_unavailable": 1}
    assert diagnostic["horizon_counts"]["24h"] == {"scored": 3, "WAIT": 2, "SHADOW_BUY": 1, "SHADOW_SELL": 0}


def test_abstention_diagnostics_exposes_future_rule_drift_as_unexpected_wait():
    diagnostic = runner._forward_abstention_diagnostics([{
        "horizon": "7d",
        "current_shadow_signals": [_signal(score=4.0, agreement=3, available=4)],
    }])

    assert diagnostic["wait_gate_counts"]["unexpected_wait_state"] == 1


def test_abstention_diagnostics_do_not_create_forward_rows():
    report = {
        "horizon_results": [{
            "horizon": "24h",
            "current_shadow_signals": [_signal(score=1.0, agreement=1, available=3)],
        }]
    }
    diagnostic = runner._forward_abstention_diagnostics(report["horizon_results"])
    rows = runner.build_forward_ledger_rows(report)

    assert diagnostic["action_counts"]["WAIT"] == 1
    assert rows == []
