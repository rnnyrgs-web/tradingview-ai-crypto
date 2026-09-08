# ACC-002 two-hour accuracy sprint

Primary objective: improve real out-of-sample crypto signal accuracy and net expectancy as fast as possible without weakening validation or exceeding the USD 30/month infrastructure ceiling.

## Hour 1 — implement cross-sectional alpha
- Timestamp-safe multi-horizon relative-strength features.
- Volatility-normalized cross-sectional ranking so noisy coins do not dominate by raw move size.
- Exact common-timestamp alignment across the liquid universe.
- Chronological 60/20/20 train/validation/untouched-OOS evaluation.
- Spearman rank information coefficient and top-minus-bottom spread.
- Explicit round-trip trading-cost deduction.
- Dedicated nonstop Render worker for ACC-002 while keeping total heavy concurrency bounded to 2.
- Fail closed on missing assets, bad timestamps, insufficient history, or nonpositive prices.

## Hour 2 — evidence and selection pressure
- Run security/reliability CI on exact head.
- Inspect first real ACC-002 research evidence instead of assuming the model works.
- Reject the factor if untouched OOS rank IC/spread is not positive after costs.
- If it survives, add parameter-stability checks around lookbacks/horizon/costs rather than optimizing to one best parameter set.
- Compare 24h and 7d horizons and only keep features whose sign and ranking quality are stable.
- Feed only validated research evidence toward later Strategy Registry work; no live promotion.

## Success criteria
A useful ACC-002 candidate must show positive untouched-OOS mean rank IC, positive after-cost top-minus-bottom spread, at least 50% positive OOS spread periods, enough OOS observations, and stability across nearby settings. Passing this sprint remains research-only and cannot authorize a live trade.
