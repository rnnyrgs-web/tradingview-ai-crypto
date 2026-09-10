from types import SimpleNamespace

import paper_db
from opportunity_engine import _action_diagnostics


def _risk(*reasons):
    return SimpleNamespace(reasons=tuple(reasons))


def _validation(approved=True, status="APPROVED", reason="ok"):
    return SimpleNamespace(approved=approved, status=status, reason=reason)


def test_action_diagnostics_preserve_primary_strategy_blocker():
    diagnostics = _action_diagnostics(
        reviewed_direction="LONG",
        direction="LONG",
        reviewed_action="WAIT",
        validation=_validation(),
        consensus={"reliable": True},
        global_risk=_risk(),
        execution_risk=_risk(),
        calibration={"allows_live_action": True},
        pre_calibration_action="WAIT",
    )

    assert diagnostics["blocked"] is True
    assert diagnostics["primary_category"] == "strategy_evidence"
    assert diagnostics["primary_reason"] == "upstream_review_wait"
    assert diagnostics["thresholds_unchanged"] is True
    assert diagnostics["trade_authority_added"] is False


def test_action_diagnostics_distinguish_market_liquidity_from_data_failure():
    market = _action_diagnostics(
        reviewed_direction="LONG",
        direction="LONG",
        reviewed_action="TRADE",
        validation=_validation(),
        consensus={"reliable": True},
        global_risk=_risk(),
        execution_risk=_risk("spread_too_wide"),
        calibration={"allows_live_action": True},
        pre_calibration_action="WAIT",
    )
    assert market["primary_category"] == "market_liquidity"
    assert market["primary_reason"] == "execution_risk_spread_too_wide"

    data = _action_diagnostics(
        reviewed_direction="LONG",
        direction="LONG",
        reviewed_action="TRADE",
        validation=_validation(),
        consensus={"reliable": False, "reason": "missing_sources"},
        global_risk=_risk(),
        execution_risk=_risk(),
        calibration={"allows_live_action": True},
        pre_calibration_action="WAIT",
    )
    assert data["primary_category"] == "technical_data_infrastructure"
    assert data["primary_reason"] == "market_consensus_unreliable"


def test_generic_not_actionable_is_enriched_from_same_signal_without_changing_decision():
    paper_db._ACTIONABILITY_REASON_CACHE.clear()
    opportunity = {
        "scan_id": "scan-1",
        "horizon": "24h",
        "symbol": "BTC-USDT",
        "direction": "LONG",
        "calibration": {
            "action_diagnostics": {
                "blocked": True,
                "primary_category": "strategy_evidence",
                "primary_reason": "calibration_pending_or_weak",
            }
        },
    }
    paper_db._cache_actionability_reason(opportunity)

    payload = paper_db._prepare_paper_signal_decision({
        "account_id": "default",
        "signal_key": "scan-1:24h:BTC-USDT:LONG",
        "scan_id": "scan-1",
        "symbol": "BTC-USDT",
        "horizon": "24h",
        "direction": "LONG",
        "action": "WAIT",
        "decision": "REJECTED",
        "reason": "not_actionable",
    })

    assert payload["decision"] == "REJECTED"
    assert payload["reason"] == "not_actionable:strategy_evidence:calibration_pending_or_weak"
    assert payload["signal_key"] == "scan-1:24h:BTC-USDT:LONG"


def test_unstructured_legacy_wait_stays_generic_instead_of_guessing():
    paper_db._ACTIONABILITY_REASON_CACHE.clear()
    payload = paper_db._prepare_paper_signal_decision({
        "signal_key": "legacy:24h:BTC-USDT:LONG",
        "decision": "REJECTED",
        "reason": "not_actionable",
    })
    assert payload["decision"] == "REJECTED"
    assert payload["reason"] == "not_actionable"
