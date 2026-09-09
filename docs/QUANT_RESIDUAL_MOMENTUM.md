# Quant Research: residual-momentum challenger

## Predeclared hypothesis

For liquid crypto cross-sections, ranking assets by trailing beta-neutral idiosyncratic momentum may improve genuine 24h/7d directional ranking quality and after-cost top-minus-bottom spread versus the current volatility-normalized raw momentum control.

This is one challenger feature family, not an unrestricted parameter search.

## Information available at forecast time

At each scoring timestamp, the challenger may use only:
- asset closes at or before the scoring timestamp;
- the contemporaneous equal-weight market return computed from the same timestamp-safe cross-section;
- trailing asset beta estimated only from returns ending at the scoring timestamp;
- trailing idiosyncratic volatility estimated only from those historical residual returns.

Future asset returns are labels only. They must not enter beta, volatility, feature construction, candidate selection, or parameter choice.

## Fixed comparison

Control: canonical ACC-002 volatility-normalized multi-lookback momentum.

Challenger: mean multi-lookback residual momentum, where residual momentum is asset return minus trailing beta times equal-weight market return, normalized by trailing idiosyncratic volatility.

Default beta window equals the maximum lookback and beta is clipped to +/-3 only for numerical robustness. Any later beta-window or clipping search is a new experiment and must be counted in the multiple-testing budget.

## Selection and untouched OOS rule

The challenger may open untouched OOS exactly once only if, on train and validation:
1. rank IC is positive in both splits;
2. worst-stress after-cost top-minus-bottom spread is positive in both splits;
3. validation positive-net-spread rate is at least 50%;
4. the challenger's worst pre-OOS after-cost spread is strictly greater than the control's; and
5. the challenger's worst pre-OOS rank IC is not lower than the control's.

If any condition fails, untouched OOS remains closed and the challenger is rejected for this experiment.

## Canonical gates retained

Untouched OOS uses the existing ACC-002 purged chronological split, non-overlapping horizon observations, 1x/1.5x/2x/3x modeled round-trip cost stress, deterministic 500-resample bootstrap, minimum independent sample requirements, liquidity stability, point-in-time universe safety, multiple-testing firewall, and genuine forward shadow proof before any later promotion review.

No result from this module can authorize a trade or promotion. `live_approved`, `trade_authority`, and `promotion_authority` remain false.

## Evidence claim policy

Passing unit tests or Security and Reliability CI proves implementation integrity only. It does not prove predictive improvement. A quantitative accuracy/profitability claim requires real chronological market evidence that passes the full canonical chain and later genuine forward validation.
