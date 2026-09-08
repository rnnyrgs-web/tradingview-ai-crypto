import math

import pytest

from cross_asset_rank import CrossAssetConfig, build_cross_section_panel, evaluate_panel, spearman_rank_ic


def _histories(asset_count=10, bars=180):
    out = {}
    for a in range(asset_count):
        rows = []
        price = 100.0 + a
        for i in range(bars):
            # Deterministic persistent relative-strength ordering without future leakage.
            price *= 1.0 + (0.0004 + a * 0.00008) + 0.00015 * math.sin(i / 9.0 + a)
            rows.append({"ts": 1_700_000_000_000 + i * 3_600_000, "close": price})
        out[f"A{a}-USDT"] = rows
    return out


def test_spearman_rank_ic_basic():
    assert spearman_rank_ic([1, 2, 3, 4], [10, 20, 30, 40]) == pytest.approx(1.0)
    assert spearman_rank_ic([1, 2, 3, 4], [40, 30, 20, 10]) == pytest.approx(-1.0)


def test_panel_and_oos_are_chronological_and_research_only():
    cfg = CrossAssetConfig(lookbacks=(4, 8, 16), forward_bars=4, min_assets=8)
    panel = build_cross_section_panel(_histories(), cfg)
    assert panel
    assert all(panel[i]["ts"] < panel[i + 1]["ts"] for i in range(len(panel) - 1))
    result = evaluate_panel(panel, cfg)
    assert result["research_only"] is True
    assert result["live_approved"] is False
    assert result["trade_authority"] is False
    assert result["splits"]["untouched_oos"]["timestamps"] > 0
    assert result["splits"]["untouched_oos"]["mean_rank_ic"] > 0


def test_non_increasing_timestamps_fail_closed():
    data = _histories()
    data["A0-USDT"][20]["ts"] = data["A0-USDT"][19]["ts"]
    with pytest.raises(ValueError, match="non-increasing timestamp"):
        build_cross_section_panel(data)


def test_insufficient_assets_fail_closed():
    with pytest.raises(ValueError, match="insufficient assets"):
        build_cross_section_panel(_histories(asset_count=4))
