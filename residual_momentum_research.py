"""Research-only market-neutral residual momentum challenger for ACC-002.

The challenger removes each asset's trailing beta to the contemporaneous equal-weight
crypto market before ranking idiosyncratic momentum. It reuses the canonical ACC-002
chronological split, purging, non-overlapping evaluation, cost stress and bootstrap
logic from ``cross_asset_rank``. No production behavior or promotion authority is
changed here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from statistics import mean
from typing import Iterable

from cross_asset_rank import (
    CrossAssetConfig,
    build_cross_section_panel,
    evaluate_pre_oos,
    evaluate_untouched_oos,
    normalize_histories,
)


@dataclass(frozen=True)
class ResidualMomentumConfig:
    beta_window: int | None = None
    beta_clip: float = 3.0
    minimum_beta_observations: int = 8


def _pct(a: float, b: float) -> float:
    if a <= 0 or b <= 0:
        raise ValueError("prices must be positive")
    return b / a - 1.0


def _stdev(values: list[float]) -> float:
    if len(values) < 2:
        return 0.0
    m = mean(values)
    return math.sqrt(sum((x - m) ** 2 for x in values) / (len(values) - 1))


def _beta(asset_returns: list[float], market_returns: list[float], clip: float) -> float:
    if len(asset_returns) != len(market_returns) or len(asset_returns) < 2:
        return 0.0
    mx = mean(asset_returns)
    my = mean(market_returns)
    market_var = sum((value - my) ** 2 for value in market_returns)
    if market_var <= 1e-18:
        return 0.0
    covariance = sum((a - mx) * (m - my) for a, m in zip(asset_returns, market_returns))
    raw = covariance / market_var
    bound = abs(float(clip))
    if bound <= 0:
        raise ValueError("beta_clip must be positive")
    return max(-bound, min(bound, raw))


def _compound(returns: list[float]) -> float:
    value = 1.0
    for ret in returns:
        value *= 1.0 + ret
    return value - 1.0


def build_residual_momentum_panel(
    histories: dict[str, Iterable[dict]],
    config: CrossAssetConfig = CrossAssetConfig(),
    residual_config: ResidualMomentumConfig = ResidualMomentumConfig(),
) -> list[dict]:
    """Build a timestamp-safe beta-neutral cross-sectional research panel.

    Beta, market returns and idiosyncratic volatility are estimated only from bars at
    or before the scoring timestamp. Forward returns are used only as labels.
    """
    normalized = normalize_histories(histories)
    if len(normalized) < config.min_assets:
        raise ValueError("insufficient assets")

    common_ts = sorted(set.intersection(*(set(values) for values in normalized.values())))
    symbols = sorted(normalized)
    closes = {symbol: [normalized[symbol][ts] for ts in common_ts] for symbol in symbols}
    max_lookback = max(config.lookbacks)
    beta_window = int(residual_config.beta_window or max_lookback)
    if beta_window < residual_config.minimum_beta_observations:
        raise ValueError("beta_window is below minimum_beta_observations")
    warmup = max(max_lookback, beta_window)
    if len(common_ts) <= warmup + config.forward_bars:
        raise ValueError("insufficient aligned history")

    one_bar = {
        symbol: [_pct(series[index - 1], series[index]) for index in range(1, len(series))]
        for symbol, series in closes.items()
    }
    market_one_bar = [
        mean(one_bar[symbol][index] for symbol in symbols)
        for index in range(len(common_ts) - 1)
    ]

    panel = []
    for idx in range(warmup, len(common_ts) - config.forward_bars):
        beta_start = idx - beta_window
        beta_end = idx
        market_beta_window = market_one_bar[beta_start:beta_end]
        rows = []
        for symbol in symbols:
            asset_beta_window = one_bar[symbol][beta_start:beta_end]
            beta = _beta(asset_beta_window, market_beta_window, residual_config.beta_clip)
            residual_momenta = []
            for lookback in config.lookbacks:
                asset_return = _pct(closes[symbol][idx - lookback], closes[symbol][idx])
                market_return = _compound(market_one_bar[idx - lookback:idx])
                residual_momenta.append(asset_return - beta * market_return)
            idiosyncratic_returns = [
                asset - beta * market
                for asset, market in zip(asset_beta_window, market_beta_window)
            ]
            idiosyncratic_vol = _stdev(idiosyncratic_returns) or 1e-9
            rows.append(
                {
                    "symbol": symbol,
                    "score": mean(residual_momenta) / idiosyncratic_vol,
                    "forward_return": _pct(
                        closes[symbol][idx],
                        closes[symbol][idx + config.forward_bars],
                    ),
                    "beta": beta,
                }
            )
        panel.append({"ts": common_ts[idx], "rows": rows})
    return panel


def _worst_stress(segment: dict) -> dict:
    stress = segment["cost_stress"]
    return stress[max(stress, key=lambda key: float(key))]


def _pre_oos_positive(pre: dict) -> bool:
    train = pre["train"]
    validation = pre["validation"]
    train_worst = _worst_stress(train)
    validation_worst = _worst_stress(validation)
    return bool(
        train["timestamps"] >= 20
        and validation["timestamps"] >= 20
        and (train["mean_rank_ic"] or 0.0) > 0.0
        and (validation["mean_rank_ic"] or 0.0) > 0.0
        and (train_worst["mean_net_top_minus_bottom"] or 0.0) > 0.0
        and (validation_worst["mean_net_top_minus_bottom"] or 0.0) > 0.0
        and validation_worst["positive_net_spread_rate"] >= 0.50
    )


def _pre_oos_beats_control(challenger: dict, control: dict) -> bool:
    challenger_train = _worst_stress(challenger["train"])
    challenger_validation = _worst_stress(challenger["validation"])
    control_train = _worst_stress(control["train"])
    control_validation = _worst_stress(control["validation"])
    challenger_worst_net = min(
        float(challenger_train["mean_net_top_minus_bottom"] or -1e9),
        float(challenger_validation["mean_net_top_minus_bottom"] or -1e9),
    )
    control_worst_net = min(
        float(control_train["mean_net_top_minus_bottom"] or -1e9),
        float(control_validation["mean_net_top_minus_bottom"] or -1e9),
    )
    challenger_worst_ic = min(
        float(challenger["train"]["mean_rank_ic"] or -1e9),
        float(challenger["validation"]["mean_rank_ic"] or -1e9),
    )
    control_worst_ic = min(
        float(control["train"]["mean_rank_ic"] or -1e9),
        float(control["validation"]["mean_rank_ic"] or -1e9),
    )
    return challenger_worst_net > control_worst_net and challenger_worst_ic >= control_worst_ic


def evaluate_residual_momentum_challenger(
    histories: dict[str, Iterable[dict]],
    config: CrossAssetConfig = CrossAssetConfig(),
    residual_config: ResidualMomentumConfig = ResidualMomentumConfig(),
) -> dict:
    """Evaluate one predeclared residual-momentum challenger against raw momentum.

    The untouched holdout is opened only if the challenger is positive on both train
    and validation and beats the existing control on worst pre-OOS after-cost spread
    without reducing worst pre-OOS rank IC.
    """
    control_panel = build_cross_section_panel(histories, config)
    challenger_panel = build_residual_momentum_panel(histories, config, residual_config)
    control_pre = evaluate_pre_oos(control_panel, config)
    challenger_pre = evaluate_pre_oos(challenger_panel, config)
    pre_oos_positive = _pre_oos_positive(challenger_pre)
    beats_control = _pre_oos_beats_control(challenger_pre, control_pre)
    selected = pre_oos_positive and beats_control

    result = {
        "research_only": True,
        "live_approved": False,
        "trade_authority": False,
        "promotion_authority": False,
        "hypothesis": "beta-neutral idiosyncratic momentum improves genuine cross-sectional 24h/7d ranking after costs",
        "selection_policy": "predeclared_single_challenger_train_validation_only_then_open_untouched_oos_once",
        "control_feature": "volatility_normalized_multi_lookback_momentum",
        "challenger_feature": "beta_neutral_residual_momentum",
        "beta_window": int(residual_config.beta_window or max(config.lookbacks)),
        "beta_clip": float(residual_config.beta_clip),
        "control_pre_oos": control_pre,
        "challenger_pre_oos": challenger_pre,
        "challenger_pre_oos_positive": pre_oos_positive,
        "challenger_beats_control_pre_oos": beats_control,
        "untouched_oos_opened": selected,
        "control_untouched_oos": None,
        "challenger_untouched_oos": None,
        "incremental_oos": None,
    }
    if not selected:
        return result

    control_oos = evaluate_untouched_oos(control_panel, config)
    challenger_oos = evaluate_untouched_oos(challenger_panel, config)
    control_worst = _worst_stress(control_oos["metrics"])
    challenger_worst = _worst_stress(challenger_oos["metrics"])
    result["control_untouched_oos"] = control_oos
    result["challenger_untouched_oos"] = challenger_oos
    result["incremental_oos"] = {
        "mean_rank_ic_delta": float(challenger_oos["metrics"]["mean_rank_ic"] or 0.0)
        - float(control_oos["metrics"]["mean_rank_ic"] or 0.0),
        "max_cost_mean_net_spread_delta": float(challenger_worst["mean_net_top_minus_bottom"] or 0.0)
        - float(control_worst["mean_net_top_minus_bottom"] or 0.0),
        "challenger_passes_acc002_research_gate": bool(challenger_oos["passes_acc002_research_gate"]),
    }
    return result
