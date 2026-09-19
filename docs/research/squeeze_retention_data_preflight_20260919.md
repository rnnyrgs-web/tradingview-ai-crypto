# Squeeze-retention: data preflight before outcomes

This continues the ranked pivot to `DISC-SQUEEZE-RETENTION-001-v1` without
inspecting any squeeze-selection outcomes or changing the rejected liquidity
fingerprint. Scope is data capability/provenance research, not strategy
evidence and not a claim that a source is promotion-grade before deterministic
verification.

## Existing repository capability

At the original preflight baseline, `market_data.get_derivatives_history`
provides:

| Input | Existing capability | What remains unproved |
|---|---|---|
| OHLCV | Bounded, cached completed OKX bars | Exact next-candidate venue/cohort/coverage contract |
| Open interest | A bounded recent Binance history request | Adequate historical coverage, units, publication/availability timestamps, exact venue match |
| Funding | OKX/Binance realized history | Timestamp semantics and usefulness as a predeclared feature |
| Liquidations | Explicitly `available: false`, `historical_notional_not_defensible_from_current_public_feed` | Historical directional notional with event AND availability timestamps and known coverage |
| Generator narrative | Money Intelligence Sep. 19 cycle | No event-level historical matched sample or scientific selection evidence |

The existing adapter therefore cannot by itself supply the required forced-flow
history. Do not repeatedly call it or query Supabase for an assumed substitute.
The existing liquidity cache is price/volume data, not liquidation or leverage
data. This is a local data deficiency, not an economic rejection of
squeeze-retention and not by itself a reason to buy a paid service.

## Newly identified zero-cost candidate archive (pre-outcome)

A concrete free candidate now exists for `COORD-DISC-DATA-003`:
**CryptoHFTData** publishes hourly Parquet/Zstd archives for derivatives
liquidations, open interest, funding/mark price, trades and order books.
Documentation currently states that Binance, Bybit, OKX and Kraken history
starts on **2025-06-28**, with a rate-limited free tier usable without an API
key. The documentation also states roughly 15-minute publication delay after an
hour closes.

Primary documentation reviewed before any strategy outcomes:

- `https://www.cryptohftdata.com/docs`
- `https://www.cryptohftdata.com/datasets/binance-liquidation-data`
- `https://www.cryptohftdata.com/datasets/binance-open-interest-data`
- `https://www.cryptohftdata.com/datasets/binance-funding-rate-data`
- `https://www.cryptohftdata.com/dashboard/python-sdk`

For Binance Futures, the documented liquidation schema includes both
`received_time` (collector receive timestamp, nanoseconds) and exchange
`event_time`, plus side, price, quantity, fill state and `trade_time`.
Open-interest rows include collector `received_time`, exchange snapshot
`timestamp`, contracts and quote-notional value when available. Funding/mark
price rows include `received_time`, `event_time`, mark/index price,
`funding_rate`, and `next_funding_time`.

This is promising because one venue can provide the four required feature
families without cross-venue joins. It is **not yet an accepted scientific data
contract**. CryptoHFTData is a third-party archive of exchange broadcasts, and
its liquidation documentation explicitly warns that exchanges may throttle or
sample public liquidation streams. Therefore liquidation totals are a lower
bound on forced flow, not complete market liquidation notional. Missing hourly
files must not be interpreted as zero liquidations without proving that file
semantics support that conclusion.

The source is currently zero-cost, so this preflight does **not** recommend a
paid subscription and does not change the project budget.

## Predeclared feasibility test for `COORD-DISC-DATA-003`

Before reading any squeeze-retention outcome, the data worker should perform one
bounded deterministic source-verification pass on the **Binance USDⓈ-M
futures** venue and fixed replication instruments **BTCUSDT, ETHUSDT,
SOLUSDT**. These are chosen before outcomes because they are highly liquid,
already familiar to the project, and avoid asset substitution after seeing
results.

The pass must verify and persist:

1. exact source URL/object-path template and acquisition timestamp;
2. exact historical coverage per symbol and data family;
3. immutable SHA-256 for every downloaded sample/file or deterministic
   normalized aggregate;
4. liquidation `received_time`, `event_time`, `trade_time` units and ordering;
5. OI snapshot `received_time` and exchange `timestamp` units/cadence;
6. funding/mark-price event and receive timestamps plus funding semantics;
7. duplicate, missing-hour, malformed-row and late-arrival behavior;
8. symbol/contract identity and quote/base units;
9. proof that only information whose receive/availability timestamp is at or
   before the decision timestamp enters a feature;
10. an explicit statement that exchange liquidation broadcasts are sampled and
    therefore all forced-flow features are proxy/intensity features, not claims
    of complete liquidation notional.

The worker must not inspect strategy returns while establishing this contract.
If any required time field is ambiguous, if historical coverage is not stable,
or if missing-file semantics cannot be distinguished from zero events, mark the
source `INSUFFICIENT_FOR_FROZEN_SCREEN` and stop. Do not impute missing
liquidations as zero and do not mix exchanges to rescue feasibility.

If the pass succeeds, freeze a versioned `DISC-SQUEEZE-RETENTION-001-v1` data
contract on these same three instruments and Binance venue before the Quant
worker freezes squeeze/retention thresholds. The later cheap screen may use the
public-stream liquidation proxy only under its documented sampling limitation;
it must compare against a matched equally-large-move baseline and keep untouched
OOS locked.

## Scientific chronology after data feasibility

`COORD-DISC-QUANT-003` must freeze exact squeeze, retention and deleveraging
definitions, sampling/matched controls, entry/stop/exit/hold, fixed cohort,
timeframe, chronological partitions, purging, costs, sample/stability gates
and total search breadth before outcome access. Preserve every protected OOS
interval across related research; a rolling data download must not turn
previously locked observations into new training data.

No squeeze strategy contract is falsely declared complete here. Once the free
source is deterministically verified, freeze the data contract and full
scientific contract as durable commits, then run only authorized
train/validation. If feasibility fails, record that precise blocker and rank a
genuinely distinct available-data hypothesis before any outcomes; never
fabricate forced flow.
