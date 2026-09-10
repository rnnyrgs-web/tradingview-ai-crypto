# FFriZz V2 OI Alignment Challenger

Status: research/shadow only. No production, paper, promotion, broker, or signing authority.

## Predeclared change

`FFRIZZ_SECONDARY_V1` is unchanged. The challenger fingerprint is `FFRIZZ_SECONDARY_V2_OI_CLOSE_END`.

The only intended semantic change is open-interest timestamp alignment for the 1H FFriZz profiles: normalized OHLC timestamps represent candle OPEN, while Binance open-interest-history timestamps represent period END. V2 therefore matches each completed 1H candle CLOSE endpoint (`open_ts + 3600000 ms`) to an OI period-END timestamp by exact equality.

## Prohibited shortcuts

No nearest-neighbour matching, interpolation, tolerance windows, forward fill, historical OI backfill, future data, threshold changes, pooled V1/V2 evidence, or production authority.

## Validation route

V2 must remain separately fingerprinted. First verify feature availability prospectively, then collect immutable non-overlapping forward forecasts. Any later performance claim requires the canonical chronological validation, untouched OOS, robustness/stability, multiple-testing, point-in-time universe, execution-cost, strategy-registry, production-risk, and genuine-forward gates already required by the repository.
