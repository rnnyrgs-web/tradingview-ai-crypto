import paper_db as p


def _row(*, horizon="7d", direction="LONG", action="WAIT", rank=1, evidence=90.0):
    return {
        "scan_id": "scan-1",
        "horizon": horizon,
        "symbol": "TEST-USDT",
        "direction": direction,
        "action": action,
        "rank": rank,
        "evidence_score": evidence,
    }


def test_strong_7d_long_wait_becomes_paper_shadow_trade_without_mutating_source(monkeypatch):
    source = _row(rank=2, evidence=84.0)
    monkeypatch.setattr(p, "fetch_production_ranked_opportunities", lambda **kwargs: [source])

    rows = p.fetch_ranked_opportunities(horizon="7d", limit=20)

    assert source["action"] == "WAIT"
    assert rows[0]["action"] == "TRADE"
    assert rows[0]["paper_shadow"] is True
    assert rows[0]["paper_source_action"] == "WAIT"


def test_7d_shadow_policy_is_restrictive_symmetric_and_horizon_specific(monkeypatch):
    source = [
        _row(rank=1, evidence=79.99),
        _row(rank=6, evidence=99.0),
        _row(direction="SHORT", rank=1, evidence=99.0),
        _row(action="TRADE", rank=1, evidence=99.0),
    ]
    monkeypatch.setattr(p, "fetch_production_ranked_opportunities", lambda **kwargs: source)

    rows = p.fetch_ranked_opportunities(horizon="7d", limit=20)

    assert [row["action"] for row in rows] == ["WAIT", "WAIT", "TRADE", "TRADE"]
    assert rows[2]["paper_shadow"] is True
    assert rows[2]["paper_source_action"] == "WAIT"
    assert source[2]["action"] == "WAIT"
    assert not rows[0].get("paper_shadow")
    assert not rows[1].get("paper_shadow")
    assert not rows[3].get("paper_shadow")


def test_24h_wait_is_never_upgraded_by_paper_shadow_policy(monkeypatch):
    source = [_row(horizon="24h", rank=1, evidence=100.0)]
    monkeypatch.setattr(p, "fetch_production_ranked_opportunities", lambda **kwargs: source)

    rows = p.fetch_ranked_opportunities(horizon="24h", limit=20)

    assert rows is source
    assert rows[0]["action"] == "WAIT"
    assert "paper_shadow" not in rows[0]


def test_shadow_thresholds_remain_selective():
    assert p.PAPER_7D_SHADOW_MIN_EVIDENCE >= 80.0
    assert 1 <= p.PAPER_7D_SHADOW_MAX_RANK <= 5
