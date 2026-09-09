import math

from cross_asset_rank import CrossAssetConfig
from residual_momentum_research import (
    ResidualMomentumConfig,
    build_residual_momentum_panel,
    evaluate_residual_momentum_challenger,
)


def _histories(rows=280, assets=8, *, identical=False):
    output = {}
    betas = [0.55 + 0.15 * index for index in range(assets)]
    for asset in range(assets):
        price = 100.0 + asset
        candles = [{"ts": 1, "close": price}]
        for index in range(1, rows):
            factor = 0.0025 * math.sin(index / 7.0) + 0.0015 * math.cos(index / 13.0)
            if identical:
                ret = factor
            else:
                idiosyncratic = 0.0004 * math.sin((index + 3 * asset) / 5.0)
                ret = betas[asset] * factor + idiosyncratic
            price *= 1.0 + ret
            candles.append({"ts": index + 1, "close": price})
        output[f"ASSET{asset}"] = candles
    return output


def test_residual_scores_do_not_use_future_prices():
    config = CrossAssetConfig(lookbacks=(4, 8), forward_bars=2, min_assets=8)
    residual = ResidualMomentumConfig(beta_window=12)
    histories = _histories()
    original = build_residual_momentum_panel(histories, config, residual)

    mutated = {symbol: [dict(row) for row in rows] for symbol, rows in histories.items()}
    for rows in mutated.values():
        for row in rows[-20:]:
            row["close"] *= 1.25
    changed = build_residual_momentum_panel(mutated, config, residual)

    for left, right in zip(original[:40], changed[:40]):
        assert left["ts"] == right["ts"]
        left_scores = {row["symbol"]: row["score"] for row in left["rows"]}
        right_scores = {row["symbol"]: row["score"] for row in right["rows"]}
        assert left_scores == right_scores


def test_trailing_betas_are_finite_and_bounded():
    config = CrossAssetConfig(lookbacks=(4, 8), forward_bars=2, min_assets=8)
    residual = ResidualMomentumConfig(beta_window=24, beta_clip=2.0)
    panel = build_residual_momentum_panel(_histories(), config, residual)

    assert panel
    for row in panel[-1]["rows"]:
        assert math.isfinite(row["beta"])
        assert -2.0 <= row["beta"] <= 2.0
        assert math.isfinite(row["score"])


def test_identical_assets_fail_closed_before_untouched_oos():
    config = CrossAssetConfig(lookbacks=(4, 8), forward_bars=2, min_assets=8)
    result = evaluate_residual_momentum_challenger(
        _histories(identical=True),
        config,
        ResidualMomentumConfig(beta_window=12),
    )

    assert result["research_only"] is True
    assert result["live_approved"] is False
    assert result["trade_authority"] is False
    assert result["promotion_authority"] is False
    assert result["challenger_pre_oos_positive"] is False
    assert result["untouched_oos_opened"] is False
    assert result["control_untouched_oos"] is None
    assert result["challenger_untouched_oos"] is None
