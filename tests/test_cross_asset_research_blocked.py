import cross_asset_runner as runner


def test_insufficient_liquidity_is_research_blocked_not_crash(monkeypatch):
    monkeypatch.setenv("CROSS_ASSET_HORIZON", "24h")
    monkeypatch.setenv("CROSS_ASSET_UNIVERSE_SIZE", "30")
    monkeypatch.setenv("CROSS_ASSET_BARS", "3000")

    symbols = [f"ASSET{i}-USDT" for i in range(30)]
    monkeypatch.setattr(runner, "build_universe", lambda: [{"symbol": symbol} for symbol in symbols])
    monkeypatch.setattr(runner, "get_history", lambda *args, **kwargs: [])
    monkeypatch.setattr(runner, "load_manifest", lambda *args, **kwargs: None)
    monkeypatch.setattr(
        runner,
        "filter_histories",
        lambda manifest, histories: (histories, {"promotion_allowed": False, "reason": "missing_point_in_time_evidence"}),
    )

    envelope = runner.run()
    payload = envelope["payload"]
    summary = runner.summarize_evidence(envelope)

    assert payload["research_blocked"] is True
    assert payload["research_blocked_reason"] == "insufficient_supported_liquidity_subsets"
    assert payload["trade_authority"] is False
    assert payload["live_approved"] is False
    assert payload["eligible_for_promotion_review"] is False
    assert payload["untouched_oos_opened_for_candidate_count"] == 0
    assert payload["selected_evaluation"] is None
    assert payload["parameter_stability"]["passes"] is False
    assert summary["research_blocked"] is True
    assert summary["research_blocked_reason"] == "insufficient_supported_liquidity_subsets"
    assert summary["failed_symbol_count"] == 30
    assert summary["failure_type_counts"] == {"InsufficientHistory": 30}
    assert "failed_symbols" not in summary
    assert "ASSET0-USDT" not in str(summary)
    assert summary["trade_authority"] is False
