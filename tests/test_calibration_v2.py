from datetime import datetime, timedelta, timezone

from calibration_v2 import (
    clustered_calibration_assessment,
    per_symbol_non_overlapping,
)


def row(symbol, origin, horizon="6h", correct=True, score=35.0, regime="RANGE_MIXED"):
    hours = {"6h": 6, "12h": 12, "24h": 24, "48h": 48, "72h": 72, "7d": 168}[horizon]
    due = origin + timedelta(hours=hours)
    return {
        "scan_id": f"{symbol}-{origin.isoformat()}",
        "symbol": symbol,
        "horizon": horizon,
        "direction": "LONG",
        "score": score,
        "market_regime": regime,
        "correct": bool(correct),
        "due_at": due.isoformat(),
        "resolved_at": (due + timedelta(minutes=5)).isoformat(),
        "strategy_identity": {"fingerprint": "TEST_V1"},
    }


def test_per_symbol_overlap_is_never_counted_twice():
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    rows = [
        row("BTC-USDT", start),
        row("BTC-USDT", start + timedelta(hours=1)),
        row("BTC-USDT", start + timedelta(hours=6)),
    ]
    selected = per_symbol_non_overlapping(rows, "6h")
    assert len(selected) == 2
    assert [r["_origin"] for r in selected] == [start, start + timedelta(hours=6)]


def test_malformed_or_unresolved_chronology_fails_closed():
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    good = row("BTC-USDT", start)
    bad_missing_symbol = {**row("ETH-USDT", start), "symbol": ""}
    bad_early_resolution = {**row("SOL-USDT", start), "resolved_at": start.isoformat()}
    bad_correct = {**row("XRP-USDT", start), "correct": None}
    selected = per_symbol_non_overlapping(
        [good, bad_missing_symbol, bad_early_resolution, bad_correct], "6h"
    )
    assert len(selected) == 1
    assert selected[0]["symbol"] == "BTC-USDT"


def test_perfect_cross_asset_correlation_is_heavily_discounted():
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    rows = []
    symbols = [f"COIN{i}-USDT" for i in range(20)]
    # Twelve non-overlapping time blocks; every coin has the same result in each
    # block. Raw rows=240, but there are only twelve genuinely distinct market
    # outcome blocks, so V2 must not treat 240 as independent.
    for block in range(12):
        outcome = block % 2 == 0
        origin = start + timedelta(hours=6 * block)
        rows.extend(row(symbol, origin, correct=outcome) for symbol in symbols)

    result = clustered_calibration_assessment(35, "6h", rows)
    assert result["symbol_nonoverlap_samples"] == 240
    assert result["time_clusters"] >= 11
    assert result["effective_samples"] < 30
    assert result["ready_for_research_comparison"] is False
    assert result["allows_live_action"] is False
    assert result["research_only"] is True


def test_diverse_cross_asset_outcomes_can_add_effective_information():
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    rows = []
    symbols = [f"COIN{i}-USDT" for i in range(20)]
    # Across twelve independent time blocks, correctness varies across symbols
    # rather than moving as one market-wide binary outcome. The challenger may
    # therefore recognize more than twelve effective observations, while still
    # remaining capped by the 240 authentic per-symbol non-overlap rows.
    for block in range(12):
        origin = start + timedelta(hours=6 * block)
        for i, symbol in enumerate(symbols):
            outcome = ((i * 7 + block * 3) % 11) < 6
            rows.append(row(symbol, origin, correct=outcome))

    result = clustered_calibration_assessment(35, "6h", rows)
    assert result["symbol_nonoverlap_samples"] == 240
    assert 12 < result["effective_samples"] <= 240
    assert result["time_clusters"] >= 11
    assert result["trade_authority_added"] is False
    assert result["production_calibration_unchanged"] is True


def test_two_block_alignments_use_the_more_conservative_result():
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    rows = []
    symbols = [f"COIN{i}-USDT" for i in range(10)]
    for block in range(10):
        # Shift origins close to the aligned horizon boundary so the half-block
        # partition differs materially from the zero-offset partition.
        origin = start + timedelta(hours=6 * block + (5 if block % 2 else 0))
        for i, symbol in enumerate(symbols):
            rows.append(row(symbol, origin, correct=((i + block) % 3 != 0)))

    result = clustered_calibration_assessment(35, "6h", rows)
    assert len(result["alignments"]) == 2
    min_neff = min(item["effective_samples"] for item in result["alignments"])
    assert result["effective_samples"] == min_neff
    assert result["conservative_alignment_offset_fraction"] in {0.0, 0.5}


def test_v2_never_authorizes_production_even_when_research_ready():
    start = datetime(2026, 9, 1, tzinfo=timezone.utc)
    rows = []
    symbols = [f"COIN{i}-USDT" for i in range(40)]
    for block in range(20):
        origin = start + timedelta(hours=6 * block)
        # Vary the within-block success rate so the cluster-robust variance is
        # estimable; a perfectly constant block rate correctly fails closed.
        successes = 28 + (block % 5)
        for i, symbol in enumerate(symbols):
            rows.append(row(symbol, origin, correct=(i < successes)))

    result = clustered_calibration_assessment(
        35,
        "6h",
        rows,
        minimum_effective_samples=10,
        minimum_time_clusters=5,
    )
    assert result["ready_for_research_comparison"] is True
    assert result["allows_live_action"] is False
    assert result["trade_authority_added"] is False
    assert result["production_calibration_unchanged"] is True
