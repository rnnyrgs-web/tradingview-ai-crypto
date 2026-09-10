# FFriZz V3 OI causal-as-of challenger

## Evidence that retired the V2 hypothesis

The first post-#242 live coordinator evidence showed `price_oi_correlation_v2` unavailable for all 12 sampled symbols at each predeclared V2 horizon: 6h, 12h and 24h. V2 itself behaved as specified: it required exact equality between a completed hourly price endpoint and a Binance open-interest period-end timestamp.

Binance's public Open Interest Statistics specification defines `timestamp` as the end time of the requested period, but its documented example is not a canonical hourly wall-clock boundary. Therefore exact endpoint equality is not a defensible general assumption. The V2 result is recorded as a disproven timestamp-alignment hypothesis, not as evidence to loosen its matching rule or tune signal thresholds.

## Predeclared V3 hypothesis

`FFRIZZ_SECONDARY_V3_OI_CAUSAL_ASOF` changes only the OI/price timestamp relationship:

- for each OI observation at time `t`, use the latest completed 1H candle endpoint `<= t`;
- require price staleness to be strictly less than one 1H bar;
- never use a future price endpoint;
- never use nearest-neighbour matching or interpolation;
- reject duplicate OI timestamps and ambiguous reuse of one price endpoint;
- require at least six aligned observations;
- retain V1's existing fixed signal thresholds and three non-OI concept families;
- remain research/shadow only, with no forward-ledger persistence or production, paper, promotion, or broker authority.

The causal as-of rule is a data-semantics challenger, not a validated alpha improvement. It must first prove prospective feature availability and timestamp integrity. Any later precision/expectancy comparison requires separately fingerprinted, non-overlapping prospective evidence and all canonical validation gates.
