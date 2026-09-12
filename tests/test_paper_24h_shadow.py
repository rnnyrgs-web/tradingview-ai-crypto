import paper_db


def _row(*, horizon="24h", rank=1, evidence=90.0, direction="LONG", action="WAIT"):
    return {
        "scan_id": "scan-shadow-test",
        "horizon": horizon,
        "rank": rank,
        "symbol": "BTC-USDT",
        "direction": direction,
        "action": action,
        "evidence_score": evidence,
        "calibration": {},
    }


def test_24h_shadow_promotes_only_strict_long_wait_cohort(monkeypatch):
    source = [_row(rank=1, evidence=90.0, direction="LONG", action="WAIT")]
    monkeypatch.setattr(paper_db, "fetch_production_ranked_opportunities", lambda **kwargs: source)

    rows = paper_db.fetch_ranked_opportunities(horizon="24h", limit=20)

    assert source[0]["action"] == "WAIT"
    assert rows[0]["action"] == "TRADE"
    assert rows[0]["paper_shadow"] is True
    assert rows[0]["paper_source_action"] == "WAIT"
    assert rows[0]["paper_shadow_fingerprint"] == paper_db.PAPER_24H_SHADOW_FINGERPRINT


def test_24h_shadow_does_not_promote_short_below_floor_or_rank_outside_top3(monkeypatch):
    source = [
        _row(rank=1, evidence=90.0, direction="SHORT"),
        _row(rank=1, evidence=84.99, direction="LONG"),
        _row(rank=4, evidence=99.0, direction="LONG"),
    ]
    monkeypatch.setattr(paper_db, "fetch_production_ranked_opportunities", lambda **kwargs: source)

    rows = paper_db.fetch_ranked_opportunities(horizon="24h", limit=20)

    assert [row["action"] for row in rows] == ["WAIT", "WAIT", "WAIT"]
    assert all("paper_shadow" not in row for row in rows)


def test_24h_shadow_never_overrides_existing_trade_or_other_horizon(monkeypatch):
    trade = _row(rank=1, evidence=99.0, direction="LONG", action="TRADE")
    monkeypatch.setattr(paper_db, "fetch_production_ranked_opportunities", lambda **kwargs: [trade])
    rows = paper_db.fetch_ranked_opportunities(horizon="24h", limit=20)
    assert rows[0]["action"] == "TRADE"
    assert "paper_shadow" not in rows[0]

    wait_12h = _row(horizon="12h", rank=1, evidence=99.0, direction="LONG", action="WAIT")
    monkeypatch.setattr(paper_db, "fetch_production_ranked_opportunities", lambda **kwargs: [wait_12h])
    rows = paper_db.fetch_ranked_opportunities(horizon="12h", limit=20)
    assert rows[0]["action"] == "WAIT"
    assert "paper_shadow" not in rows[0]


def test_existing_7d_shadow_policy_is_preserved(monkeypatch):
    source = [_row(horizon="7d", rank=5, evidence=80.0, direction="SHORT", action="WAIT")]
    monkeypatch.setattr(paper_db, "fetch_production_ranked_opportunities", lambda **kwargs: source)

    rows = paper_db.fetch_ranked_opportunities(horizon="7d", limit=20)

    assert rows[0]["action"] == "TRADE"
    assert rows[0]["paper_shadow_fingerprint"] == paper_db.PAPER_7D_SHADOW_FINGERPRINT
