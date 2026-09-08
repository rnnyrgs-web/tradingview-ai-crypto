from champion_challenger import build_champion_challenger


def _run(ts, expectancy=0.4, pf=1.6, dd=6.0, trades=40):
    metrics = {
        "avg_trade_pct": expectancy,
        "profit_factor": pf,
        "max_drawdown_pct": dd,
        "trades": trades,
    }
    return {
        "generated_at": ts,
        "validation": dict(metrics),
        "holdout_test": dict(metrics),
        "robustness": {"passed": True},
    }


def _candidate(symbol, family):
    return {
        "symbol": symbol,
        "bar": "1H",
        "strategy_family": family,
        "status": "READY_FOR_STRATEGY_REGISTRY_REVIEW",
        "live_approved": False,
    }


def test_ensemble_weights_are_capped_and_research_only():
    candidates = [
        _candidate("BTC-USDT", "trend"),
        _candidate("ETH-USDT", "momentum"),
        _candidate("SOL-USDT", "breakout"),
    ]
    history = {
        (c["symbol"], c["bar"], c["strategy_family"]): [
            _run("2026-01-01T00:00:00Z"),
            _run("2026-02-01T00:00:00Z"),
            _run("2026-03-01T00:00:00Z"),
        ]
        for c in candidates
    }
    result = build_champion_challenger(candidates, history, max_weight=0.45)
    assert result["status"] == "RESEARCH_ENSEMBLE_READY"
    assert result["live_approved"] is False
    assert abs(sum(member["weight"] for member in result["members"]) - 1.0) < 1e-5
    assert result["unallocated_wait_weight"] == 0.0
    assert all(member["weight"] <= 0.450001 for member in result["members"])
    assert result["members"][0]["role"] == "CHAMPION"


def test_recent_deterioration_demotes_strategy_to_zero_weight():
    good = _candidate("BTC-USDT", "trend")
    fading = _candidate("ETH-USDT", "momentum")
    history = {
        ("BTC-USDT", "1H", "trend"): [
            _run("2026-01-01T00:00:00Z", 0.35, 1.5),
            _run("2026-02-01T00:00:00Z", 0.36, 1.55),
            _run("2026-03-01T00:00:00Z", 0.37, 1.6),
            _run("2026-04-01T00:00:00Z", 0.38, 1.65),
        ],
        ("ETH-USDT", "1H", "momentum"): [
            _run("2026-01-01T00:00:00Z", 0.55, 1.9),
            _run("2026-02-01T00:00:00Z", 0.50, 1.8),
            _run("2026-03-01T00:00:00Z", 0.08, 1.08),
            _run("2026-04-01T00:00:00Z", 0.04, 1.04),
        ],
    }
    result = build_champion_challenger([good, fading], history)
    members = {row["symbol"]: row for row in result["members"]}
    demoted = {row["symbol"]: row for row in result["demoted"]}
    assert "BTC-USDT" in members
    assert "ETH-USDT" not in members
    assert demoted["ETH-USDT"]["reason"] == "SEVERE_RECENT_DETERIORATION"
    assert demoted["ETH-USDT"]["weight"] == 0.0
    assert result["unallocated_wait_weight"] > 0.0


def test_high_correlation_penalizes_duplicate_exposure():
    a = _candidate("BTC-USDT", "trend")
    b = _candidate("ETH-USDT", "trend")
    c = _candidate("SOL-USDT", "mean_reversion")
    candidates = [a, b, c]
    history = {
        (row["symbol"], row["bar"], row["strategy_family"]): [
            _run("2026-01-01T00:00:00Z"),
            _run("2026-02-01T00:00:00Z"),
            _run("2026-03-01T00:00:00Z"),
        ]
        for row in candidates
    }
    ka = ("BTC-USDT", "1H", "trend")
    kb = ("ETH-USDT", "1H", "trend")
    result = build_champion_challenger(candidates, history, {(ka, kb): 0.92})
    members = {row["symbol"]: row for row in result["members"]}
    assert members["ETH-USDT"]["correlation_penalty"] <= 0.35
    assert members["SOL-USDT"]["correlation_penalty"] == 1.0


def test_less_than_three_runs_cannot_enter_ensemble():
    candidate = _candidate("BTC-USDT", "trend")
    key = ("BTC-USDT", "1H", "trend")
    result = build_champion_challenger([candidate], {key: [_run("1"), _run("2")]})
    assert result["status"] == "NO_QUALIFIED_ENSEMBLE"
    assert result["members"] == []
    assert result["unallocated_wait_weight"] == 1.0
