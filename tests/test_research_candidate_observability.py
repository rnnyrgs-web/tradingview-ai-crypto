from __future__ import annotations

from research_observability import record_candidate_evidence, snapshot


def test_candidate_evidence_is_persisted_without_claiming_authority(tmp_path):
    record_candidate_evidence(
        "active-fp:BTC-USDT:1H",
        {
            "strategy_fingerprint": "active-fp",
            "decision": {"state": "OOS_PASS", "real_money_trade_authority": False},
        },
        metrics_dir=tmp_path,
    )
    state = snapshot(metrics_dir=tmp_path)
    row = state["candidate_evidence"]["active-fp:BTC-USDT:1H"]
    assert row["latest_evidence"]["strategy_fingerprint"] == "active-fp"
    assert state["trade_authority"] is False
    assert state["promotion_authority"] is False
    assert state["workers"]["completed"] == 0


def test_candidate_evidence_rejects_unbound_payload(tmp_path):
    record_candidate_evidence("bad", {"decision": {"state": "OOS_PASS"}}, metrics_dir=tmp_path)
    state = snapshot(metrics_dir=tmp_path)
    assert state["candidate_evidence"] == {}
