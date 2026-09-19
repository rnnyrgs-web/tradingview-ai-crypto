# COORD-DISC-DATA-003: bounded archive verification

Owner: GitHub follow-up data-market worker. Branch:
`auto/data-market/coord-disc-data-003`. Base main:
`7a086231a17bce401a103d9cdeedf99a4c842d30` (PR #421).

## Predeclared probe (before sample inspection)

Audit the documented sample hour **2026-09-02 12:00–13:00 UTC** for
**BTCUSDT, ETHUSDT, SOLUSDT**, Binance USDⓈ-M perpetuals, with families
`liquidations`, `open_interest`, `mark_price`. This is a documentation-selected
feasibility sample, not a randomly sampled or representative history claim.
No replacement hours, symbols, venues, or strategy outcomes are permitted.

Use the anonymous HTTPS endpoint
`https://api.cryptohftdata.com/v1/download?file=binance_futures/2026-09-02/12/{symbol}_{family}.parquet`.
Bound acquisition to nine requests, 8 MiB/object, 32 MiB/run, 20-second network
timeout per request, no retry and no credentials or paid calls. Persist exact
bytes, acquisition UTC, source paths, sizes and SHA-256. Replay locally without
network. Missing or malformed objects are failures, never zero-event evidence.

DONE for this engineering milestone: regression-tested offline timestamp,
schema and identity audit; a real sample manifest and reproducible report;
explicit missingness, ordering, duplicate and late-arrival diagnostics; exact
next scientific action in a reviewable PR. This does not complete the full data
contract or authorize a selection run.

Collector receipt, exchange event time and archive publication are distinct.
The documented approximate publication delay cannot prove the exact historical
availability of a file. Sample structure alone cannot prove full-period
coverage, contract units, collection completeness or publication chronology.
The report must retain `INSUFFICIENT_FOR_FROZEN_SCREEN` until those prerequisites
are independently resolved. Liquidations are sampled public broadcasts and
only a lower-bound proxy for forced flow. OOS and all strategy returns remain
unopened.

## Results and handoff

Pending the bounded probe and verifier. No profitability evidence is claimed.
