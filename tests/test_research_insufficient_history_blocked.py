import research_runner


def test_known_insufficient_history_is_research_blocked():
    exc = RuntimeError("Need at least 1000 candles for walk-forward")
    assert research_runner._research_blocked_reason(exc) == "insufficient_historical_candles"

    item = research_runner._blocked_item({"symbol": "PONS-USDT-SWAP", "bar": "15m"}, exc, "insufficient_historical_candles")
    assert item["ok"] is True
    assert item["research_only"] is True
    assert item["research_blocked"] is True
    assert item["eligible_for_promotion_review"] is False
    assert item["live_approved"] is False
    assert item["trade_authority"] is False


def test_short_history_variant_is_research_blocked():
    exc = RuntimeError("Not enough historical candles")
    assert research_runner._research_blocked_reason(exc) == "insufficient_historical_candles"


def test_unknown_runtime_error_remains_software_failure():
    exc = RuntimeError("database corruption")
    assert research_runner._research_blocked_reason(exc) is None


def test_non_runtime_error_is_not_silently_reclassified():
    exc = ValueError("Not enough historical candles")
    assert research_runner._research_blocked_reason(exc) is None
