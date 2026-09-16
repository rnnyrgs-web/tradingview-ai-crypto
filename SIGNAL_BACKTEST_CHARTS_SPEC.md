# Continuous Signal Backtest Charts

## Objective

Make the historical and forward evidence behind every signal/strategy family visually inspectable without overstating backtests as real profit.

## Required chart set

For each strategy/signal family and supported asset, maintain:

1. **Net equity curve vs buy-and-hold benchmark** after configured fees and conservative execution-cost assumptions.
2. **Drawdown curve** using the same chronological trade path.
3. **Validation-boundary chart** that visibly separates training/in-sample, validation, untouched holdout/OOS, and genuine forward evidence. Never blend these into one unlabeled curve.
4. **Rolling evidence chart** for rolling win rate, expectancy/profit factor, and sample count where statistically meaningful.
5. **Regime/year breakdown** so one favorable period cannot masquerade as durable performance.

## History policy

Target 10 years of point-in-time history where the asset, venue and required inputs genuinely exist. When 10 years are unavailable, use the complete defensible history and label the exact start/end dates and limitation. Never synthesize, extrapolate or backfill missing years.

## Metrics

Display at minimum: exact backtest period, trade count, total net return, CAGR when duration permits, max drawdown, Sharpe/Sortino when defensible, win rate, profit factor, average/median trade, assumed fees/slippage/funding or cost-stress scenario, long/short split, and benchmark return. Clearly distinguish additive trade-return summaries from compounded portfolio equity.

## Scientific safeguards

- Decisions must use only information available at the decision timestamp; execution starts no earlier than the next executable observation.
- Preserve point-in-time universe membership and timestamp causality.
- Training may select parameters; validation and holdout may not be optimized after inspection.
- Never rewrite historical OOS/forward results when a model changes. A changed model/parameter set gets a new immutable strategy identity/version and a new evidence series.
- Historical candle data without executable bid/ask history must not fabricate spreads. Use explicit conservative cost stress and label it.
- Insufficient data, invalid timestamps, missing required features, or uncertain provenance must fail closed and render `INSUFFICIENT EVIDENCE`, not a curve.
- A visually attractive backtest is research evidence only and cannot bypass promotion, calibration, risk, or broker gates.

## Continuous refresh

The existing research/backtest cycle should refresh chart artifacts whenever new resolved market data or genuine forward outcomes materially extend a strategy's evidence. Refreshing means appending/recomputing the display artifact from immutable strategy/version inputs; it must never alter previously frozen predictions or hide losses.

Avoid paid data/compute unless separately authorized and remain within the project's combined approximately $30/month variable-resource ceiling.

## Dashboard behavior

The signal dashboard should expose a `BACKTEST / EVIDENCE` view per strategy/signal family. The default view should emphasize the untouched holdout/forward segment and after-cost equity/drawdown rather than the in-sample curve. Show `last refreshed`, data provenance, strategy/version identity, exact history coverage, and any fail-closed reason.

Until a chart artifact meeting this contract exists, the dashboard must say `BACKTEST CHART NOT YET VERIFIED`; it must not manufacture placeholder performance.