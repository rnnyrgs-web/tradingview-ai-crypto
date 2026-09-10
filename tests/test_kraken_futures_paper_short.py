import math

import kraken_futures_execution as kf
import paper_db


def test_perp_short_walks_visible_depth_and_reserves_funding(monkeypatch):
    monkeypatch.setattr(kf, "resolve_perpetual", lambda symbol: ("PF_TESTUSD", 1.0))
    monkeypatch.setattr(
        kf,
        "_fetch_book",
        lambda symbol: ([(100.0, 20.0), (99.0, 20.0)], [(101.0, 20.0)], 1_000),
    )
    monkeypatch.setattr(kf, "_latest_funding_rate", lambda symbol: -0.00001)

    result = kf.simulate_kraken_perp_fill(
        "TEST-USDT", "SHORT", 1500.0, reserve_full_horizon_funding=True
    )

    assert result.executable is True
    assert result.perp_symbol == "PF_TESTUSD"
    assert result.source_count == 2
    assert result.supported_notional >= 1500.0
    assert result.funding_reserve_bps == 0.00001 * 168 * 10000
    expected_raw = 100.0
    expected_fill = expected_raw * (1 - 0.0005 - 0.00001 * 168)
    assert math.isclose(result.raw_vwap, expected_raw, rel_tol=1e-12)
    assert math.isclose(result.fill_price, expected_fill, rel_tol=1e-12)


def test_perp_short_fails_closed_without_contract_size(monkeypatch):
    monkeypatch.setattr(kf, "resolve_perpetual", lambda symbol: (None, None))
    result = kf.simulate_kraken_perp_fill(
        "UNKNOWN-USDT", "SHORT", 1000.0, reserve_full_horizon_funding=True
    )
    assert result.executable is False
    assert "contract-size" in result.reason


def test_perp_short_fails_closed_without_visible_depth(monkeypatch):
    monkeypatch.setattr(kf, "resolve_perpetual", lambda symbol: ("PF_TESTUSD", 1.0))
    monkeypatch.setattr(
        kf,
        "_fetch_book",
        lambda symbol: ([(100.0, 1.0)], [(101.0, 1.0)], 1_000),
    )
    monkeypatch.setattr(kf, "_latest_funding_rate", lambda symbol: 0.0)
    result = kf.simulate_kraken_perp_fill(
        "TEST-USDT", "SHORT", 5000.0, reserve_full_horizon_funding=True
    )
    assert result.executable is False
    assert "Insufficient visible" in result.reason


def test_7d_short_wait_can_become_paper_shadow(monkeypatch):
    source = {
        "scan_id": "s1",
        "symbol": "TEST-USDT",
        "horizon": "7d",
        "direction": "SHORT",
        "action": "WAIT",
        "evidence_score": 84.0,
        "rank": 4,
    }
    monkeypatch.setattr(paper_db, "fetch_production_ranked_opportunities", lambda **kwargs: [source])
    rows = paper_db.fetch_ranked_opportunities(horizon="7d", limit=20)
    assert rows[0]["action"] == "TRADE"
    assert rows[0]["paper_shadow"] is True
    assert source["action"] == "WAIT"


def test_7d_short_shadow_stays_wait_below_policy(monkeypatch):
    source = {
        "scan_id": "s2",
        "symbol": "TEST-USDT",
        "horizon": "7d",
        "direction": "SHORT",
        "action": "WAIT",
        "evidence_score": 79.9,
        "rank": 4,
    }
    monkeypatch.setattr(paper_db, "fetch_production_ranked_opportunities", lambda **kwargs: [source])
    rows = paper_db.fetch_ranked_opportunities(horizon="7d", limit=20)
    assert rows[0]["action"] == "WAIT"
    assert "paper_shadow" not in rows[0]


def test_perp_technical_failure_remains_retryable():
    payload = paper_db._prepare_paper_signal_decision({
        "account_id": "default",
        "signal_key": "scan:7d:TEST-USDT:SHORT",
        "scan_id": "scan",
        "symbol": "TEST-USDT",
        "horizon": "7d",
        "direction": "SHORT",
        "action": "TRADE",
        "evidence_score": 84.0,
        "decision": "REJECTED",
        "reason": "kraken_perp_execution_evidence_unavailable",
        "signal_generated_at": "2026-09-10T01:00:00Z",
    })
    assert payload["decision"] == "TECHNICAL_BLOCKED"
    assert payload["reason"] == "technical:kraken_perp_execution_evidence_unavailable"
    assert payload["signal_key"].startswith("scan:7d:TEST-USDT:SHORT:technical:")
