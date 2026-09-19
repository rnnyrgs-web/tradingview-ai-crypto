# DISC-BTC-LEADLAG-001-v1 exploratory screen

## Decision

`DISC-BTC-LEADLAG-001-v1` is **REJECTED_PRE_OOS**. The immutable reused-history screen failed its predeclared economic and replication gates. No parameter, asset, timeframe, or date was changed, and the historical untouched OOS and genuine-forward periods remain unopened.

This is negative research evidence, not a profitability or trading-authority claim.

## Frozen-screen evidence

The runner reverified the exact contract SHA-256 `8d991f723c65a583b1d3188aa7f4f77493d08cfd198ee6aa4be508294d770989`, dataset SHA-256 `047c098bb2957557f8344ca30c32339ecac01b5067ae424b147d21c9e9caaf9f`, fixed BTC/ETH/SOL instruments, common hourly timestamps, row counts, coverage, and OHLC validity before computing outcomes.

At the required 3x cost stress, the 50 bps primary rule produced:

| Segment | Trades | Mean net bps | Profit factor |
|---|---:|---:|---:|
| Training, pooled | 102 | -68.95 | 0.420 |
| Validation, pooled | 24 | -113.69 | 0.097 |
| Training, ETH | 50 | -87.43 | 0.334 |
| Validation, ETH | 10 | -116.86 | 0.106 |
| Training, SOL | 52 | -51.19 | 0.521 |
| Validation, SOL | 14 | -111.42 | 0.090 |

The primary rule was already negative at base cost: -28.95 bps per pooled training trade and -73.69 bps per pooled validation trade. It also underperformed the no-underreaction validation baseline (-75.31 bps at 3x), while both fixed 35 bps and 65 bps falsifier sensitivities were negative in train and validation. Both validation halves and both sufficiently populated BTC regimes failed the frozen stability tests.

## Safety and accounting

- Through-origin beta used only the 168 strictly prior aligned returns.
- Signal-bar close determined eligibility; entry used the next follower open and exit used the open six hours later.
- Decision timestamps, common event IDs, and feature-availability timestamps use the signal close rather than the later entry open. A follower still open at that decision close cannot re-enter at its exit open.
- The simulator used a closed $100,000 portfolio, shared BTC event IDs, 25% decision-NAV sizing per follower, two-position/50% gross caps, and no resizing.
- Fees, spread, slippage, and carry were explicit money debits; trade P&L and hourly NAV reconcile through the existing `profitability_learning` validator.
- The CLI requires an initialized durable Profitability Learning database. It persists the training and validation completions through the shared runtime hook, records the predeclared underreaction-vs-baseline ablation, and makes the rejected exact strategy fingerprint ineligible to future admission. Replay is idempotent.
- The underreaction filter improved training compounded return by 6.03 percentage points versus its predeclared ablation, but the full strategy still lost 16.30% after costs. This is an unproven development association, not a rescue or positive edge.
- Reused train/validation artifacts are explicitly retrospective and exploratory only.
- Candidate outcomes inspected: yes, only in purged train/validation.
- Historical untouched OOS opened: no.
- Genuine forward opened: no.
- Broker, execution, promotion, and automatic-trading authority: off.

## Exact next action

After independent review and integration, persist the selection fingerprint in the canonical rejected registry and release the one-deep slot. Do not tune or reopen v1. The next strategy-discovery milestone must freeze a materially distinct mechanism before inspecting its outcomes. The evidence envelope is `orchestration/evidence/disc_btc_leadlag_001_20260919.json.gz`, payload SHA-256 `9a73a00e6052783525b77ec36527bc5fb12c2891ebd300da00ff744fd3e4951c`.
