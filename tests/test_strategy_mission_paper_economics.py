from strategy_mission_dashboard import build_paper_economics


def test_paper_economics_are_filtered_to_exact_candidate_fingerprint():
    result = build_paper_economics([
        {"strategy_fingerprint": "fp-1", "status": "CLOSED", "pnl_usd": 100, "pnl_pct": 1.0,
         "fee_bps_one_way": 10, "closed_at": "2026-09-16T10:00:00+00:00"},
        {"strategy_fingerprint": "other", "status": "CLOSED", "pnl_usd": 9999, "pnl_pct": 99.0,
         "fee_bps_one_way": 1, "closed_at": "2026-09-16T11:00:00+00:00"},
        {"strategy_fingerprint": "fp-1", "status": "CLOSED", "pnl_usd": -40, "pnl_pct": -0.4,
         "fee_bps_one_way": 10, "closed_at": "2026-09-16T12:00:00+00:00"},
    ], "fp-1")
    assert result["status"] == "VERIFIED"
    assert result["strategy_fingerprint"] == "fp-1"
    assert result["closed_trades"] == 2
    assert result["net_pnl_usd"] == 60.0
    assert result["expectancy_usd"] == 30.0
    assert result["profit_factor"] == 2.5
    assert result["fee_bps_one_way"] == [10.0]


def test_paper_economics_fail_closed_without_fingerprint_or_matching_rows():
    assert build_paper_economics([], None)["status"] == "UNVERIFIED"
    result = build_paper_economics([{"strategy_fingerprint": "other"}], "fp-1")
    assert result["status"] == "INSUFFICIENT_EVIDENCE"
    assert result["closed_trades"] == 0
