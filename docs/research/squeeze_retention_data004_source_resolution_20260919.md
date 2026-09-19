# Squeeze-retention DATA-004 source resolution

## Decision

`COORD-DISC-DATA-004` reaches **TERMINAL_NO_ZERO_COST_TIMESTAMP_SAFE_SOURCE** under the current approved access, fixed venue/cohort and scientific contract.

This is a data-path decision, not a rejection of `DISC-SQUEEZE-RETENTION-001-v1` and not evidence for or against its returns. No strategy outcome was inspected, untouched OOS remains locked, no paid service was added, and no trading authority changed.

The exact pre-outcome interval was frozen as **2025-07-01T00:00:00Z inclusive through 2026-09-01T00:00:00Z exclusive** for Binance USDⓈ-M BTCUSDT, ETHUSDT and SOLUSDT. It ends before the Sep. 2 fixed feasibility sample and before the Sep. 18 generator observation, preventing either from selecting the historical window.

## What was established

CryptoHFTData documents hourly liquidations, open interest and mark-price files from June 28, 2025, with `received_time` on event/snapshot rows. It also documents two restrictions that matter scientifically:

- public liquidation feeds can be throttled or sampled, so their totals are lower bounds;
- a liquidation file exists only when the venue published at least one event for that symbol/hour.

Those semantics make a sparse liquidation inventory usable only if the complete inventory is known and a dense companion stream proves collector health for each missing symbol/hour. A missing liquidation object can then mean “no public broadcast file”; it still cannot mean zero actual liquidations or zero notional.

The provider's flat-file documentation says complete prefix listing requires short-lived S3 credentials generated after dashboard login. Anonymous REST download works when an exact path is already known, but guessing all paths across 10,248 hours is not equivalent to an exhaustive listing and cannot separate source absence from collector outage. The provider's approximate hour-close-plus-15-minute availability statement is not per-object historical publication proof.

The official Binance REST alternative does not repair the contract. Its open-interest statistics endpoint documents only the latest month. Its public market-data catalogue does not expose matching historical forced-liquidation history. Binance Data Collection provides useful dated mark-price and metrics/open-interest style archives, but the reviewed USDⓈ-M daily/monthly catalogues do not provide the required liquidation-event family. Substituting price or OI for forced flow would change the selected hypothesis after the fact.

## Deterministic inventory gate

`squeeze_retention_inventory_contract.py` now enforces the exact manifest contract without reading returns:

- 61,488 dense open-interest/mark-price objects are required;
- 30,744 liquidation symbol-hours must be classified;
- every present object needs a positive size and SHA-256; an S3 ETag is not accepted as SHA-256;
- pre-Aug. 19, 2026 objects must use the provider's documented `.parquet.zst` key and later objects `.parquet`;
- duplicate or malformed identities fail closed;
- a missing liquidation file is classified as provider-declared no-publication only when the listing is exhaustive and both dense companion files are valid for that symbol/hour;
- receipt/public-availability chronology and independent contract/notional units must be verified before QUANT may use the data.

This preserves an executable reopening gate if already-authorized access later supplies a complete inventory. It does not keep the current data task artificially open.

## Durable blockers and handoff

The exact current blockers are:

1. no complete anonymous prefix inventory or full-period immutable manifest;
2. no independent historical per-object publication chronology;
3. without the complete inventory and dense-stream health, missing liquidation files cannot be separated from collector outages;
4. the official zero-cost Binance alternatives lack the same historical forced-flow family;
5. public liquidation broadcasts remain lower-bound observations, never complete market liquidation notional.

The Lead should close DATA-004 and pivot to the highest-value materially distinct hypothesis whose data are already timestamp-defensible. It should not rescue this fingerprint by changing venue, reconstructing missing forced flow, treating current snapshots as history, or interpreting absent files as zero.

## Sources reviewed on 2026-09-19

- [CryptoHFTData overview and availability](https://www.cryptohftdata.com/docs)
- [CryptoHFTData flat-file access](https://www.cryptohftdata.com/docs/flat-file-introduction)
- [CryptoHFTData AWS CLI keys and suffixes](https://www.cryptohftdata.com/docs/flat-file-aws-cli)
- [CryptoHFTData Binance liquidation dataset](https://www.cryptohftdata.com/datasets/binance-liquidation-data)
- [CryptoHFTData Binance open-interest dataset](https://www.cryptohftdata.com/datasets/binance-open-interest-data)
- [Binance USDⓈ-M official market-data API](https://developers.binance.com/en/docs/catalog/core-trading-derivatives-trading-usd-s-m-futures/api/rest-api/market-data)
- [Binance public USDⓈ-M daily archive](https://data.binance.vision/?prefix=data/futures/um/daily/)
- [Binance public USDⓈ-M monthly archive](https://data.binance.vision/?prefix=data/futures/um/monthly/)
