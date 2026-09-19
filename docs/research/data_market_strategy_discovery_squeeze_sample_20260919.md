# COORD-DISC-DATA-003: bounded archive verification

Owner: GitHub follow-up data-market worker. Branch:
`auto/data-market/coord-disc-data-003`. Base main:
`7a086231a17bce401a103d9cdeedf99a4c842d30` (PR #421).
Before publication, integrated and retested current main
`a09506e4f0e59eab8dea2552f25e596f3c000b9c` (PR #422).

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

Measured 2026-09-19 UTC. All **9/9** requested objects returned HTTP 200;
**336,805 bytes** total. Exact bytes, request-start UTC (`acquired_at`), source
URLs and SHA-256 are in `research_data/squeeze_preflight/20260902_12/`.
`audit.json` is reproducible offline with no network or strategy calculation.
This pass had no missing requested objects, malformed rows, exact duplicate
rows or timestamp-order inversions. That does not establish behavior for
missing hours or collection interruptions outside this hour.

| Symbol | Liquidation rows | OI rows | OI snapshots preceding receipt hour | Mark/funding rows |
|---|---:|---:|---:|---:|
| BTCUSDT | 38 | 511 | 499 | 3,527 |
| ETHUSDT | 33 | 511 | 499 | 3,527 |
| SOLUSDT | 14 | 509 | 498 | 3,527 |

Findings:

- Collector receipt is consistent with nanoseconds; Binance event, trade,
  snapshot and next-funding times are consistent with milliseconds. All sample
  receipts fall inside the named hour. Liquidation receipt latency ranges
  from 120.841380 to 133.858904 ms across these files; these are collector
  latencies, **not archive publication latencies**.
- OI files contain historical snapshots: BTC/ETH event coverage is Aug 31
  18:25 through Sep 2 12:55 UTC; SOL is Aug 31 18:30 through Sep 2 12:50 UTC.
  Unique OI events are five minutes apart. The oldest snapshot is received
  **41.679 hours** after its exchange timestamp. Backdating these snapshots
  to exchange time would introduce look-ahead. No duplicate snapshots occur
  within these individual files; cross-file deduplication is still unproved.
- Mark/funding event coverage is 12:00:00–12:59:59 UTC for each symbol, but
  the largest adjacent event gap is **73.996 seconds**, and maximum receipt
  latency is **69.691 seconds**. This is evidence of gaps/late receipt, not
  a proof of their cause. Funding-rate observations accompany a future
  `next_funding_time`; they must not be relabeled as realized funding payments.
- The source claims linear Binance USDⓈ-M instruments, but contract/base/quote
  units have not been independently reconciled with venue instrument metadata.
  Liquidation fill-state/notional semantics need a frozen definition. No
  notional feature or trade return was calculated here.

**Decision: `INSUFFICIENT_FOR_FROZEN_SCREEN`.** Structural feasibility is
demonstrated for one receipt-hour only. Historical coverage, missing-hour
semantics, archive publication chronology and independently verified units
remain unproved. Public liquidation broadcasts are sampled; even after these
blockers are resolved, they can only support a declared forced-flow proxy.
Do not promote these results to a profitable-strategy claim or start outcomes.

The offline `available_asof` reference guard requires externally verified
publication time and rejects publication earlier than any collector receipt.
Synthetic boundary tests prove the guard, not that the sample has publication
proof. Today's acquisition timestamps cannot establish historical availability.
The actual sample has **no authorized feature rows**.

## Reproduction and validation

Use an isolated research environment; production dependencies are unchanged.
The original replay used Python 3.12, pyarrow 25.0.1 and pytest 9.1.1.

```sh
python -m pip install pyarrow==25.0.1 pytest==9.1.1
python squeeze_retention_data_preflight.py research_data/squeeze_preflight/20260902_12 --output /tmp/squeeze-audit.json
cmp /tmp/squeeze-audit.json research_data/squeeze_preflight/20260902_12/audit.json
pytest -q tests/test_data_market_squeeze_preflight.py
```

CLI exit 0 means only that the nine sample files replay without integrity or
structural errors; the JSON research decision still fails closed. Default CI
checks every raw hash without pyarrow; the optional real Parquet replay test
skips when pyarrow is unavailable. Local replay includes that test.

Validation: 27 focused tests passed, including wrong units, future events,
missing/duplicate objects, tampering, source/path mismatch, old/repeated OI
snapshots and exact as-of boundaries. Full suite on the integrated main:
**967 passed, 1 skipped** (9.95 seconds). Bandit, dependency vulnerability audit
and committed-secret scan passed. The local test environment required optional
`socksio` for its proxy; no repository dependency change was needed. Exact-head
GitHub CI and independent-review status are recorded in the PR handoff.

Next action after independent review: Lead should reconcile this evidence with
`COORD-DISC-DATA-003`, keeping the scientific contract blocked. A further data
milestone must predeclare the historical coverage interval, prove archive
availability and missing-file semantics, reconcile venue units and freeze a
strict receipt/publication-aware contract **before** `COORD-DISC-QUANT-003`
freezes thresholds and before any outcomes. If those requirements cannot be
proved, record the precise source blocker and let the Lead rank a materially
distinct available-data hypothesis; do not rescue this one with imputed zeros,
venue substitution or outcome-guided thresholds. OOS stays locked.

Primary references used in the source preflight (retrieved 2026-09-19):
[REST overview](https://www.cryptohftdata.com/docs/rest-introduction),
[liquidations](https://www.cryptohftdata.com/docs/rest-liquidations),
[open interest](https://www.cryptohftdata.com/docs/rest-open-interest).
