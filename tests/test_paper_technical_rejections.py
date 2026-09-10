import paper_db as p


def _base(decision="REJECTED", reason="kraken_execution_evidence_unavailable"):
    return {
        "account_id": "default",
        "signal_key": "scan:7d:IOST-USDT:LONG",
        "scan_id": "scan",
        "symbol": "IOST-USDT",
        "horizon": "7d",
        "direction": "LONG",
        "action": "TRADE",
        "evidence_score": 92.9,
        "decision": decision,
        "reason": reason,
        "signal_generated_at": "2026-09-10T01:06:59Z",
        "decided_at": "2026-09-10T01:10:31Z",
    }


def test_execution_information_failure_is_flagged_as_retryable_technical_incident():
    payload = p._prepare_paper_signal_decision(_base())

    assert payload["decision"] == "TECHNICAL_BLOCKED"
    assert payload["reason"] == "technical:kraken_execution_evidence_unavailable"
    assert payload["signal_key"].startswith("scan:7d:IOST-USDT:LONG:technical:")
    assert payload["signal_key"] != "scan:7d:IOST-USDT:LONG"


def test_technical_incident_does_not_consume_canonical_key_for_later_acceptance():
    blocked = p._prepare_paper_signal_decision(_base())
    accepted = p._prepare_paper_signal_decision(_base(decision="ACCEPTED", reason="fresh_kraken_visible_depth_taker_fill"))

    assert blocked["signal_key"] != accepted["signal_key"]
    assert accepted["signal_key"] == "scan:7d:IOST-USDT:LONG"
    assert accepted["decision"] == "ACCEPTED"


def test_genuine_strategy_or_risk_rejection_keeps_canonical_audit_key():
    payload = p._prepare_paper_signal_decision(_base(reason="max_open_positions"))

    assert payload["decision"] == "REJECTED"
    assert payload["reason"] == "max_open_positions"
    assert payload["signal_key"] == "scan:7d:IOST-USDT:LONG"


def test_explicit_technical_prefix_is_also_retryable():
    payload = p._prepare_paper_signal_decision(_base(reason="technical:market_data_source_timeout"))

    assert payload["decision"] == "TECHNICAL_BLOCKED"
    assert payload["reason"] == "technical:market_data_source_timeout"
    assert payload["signal_key"].startswith("scan:7d:IOST-USDT:LONG:technical:")
