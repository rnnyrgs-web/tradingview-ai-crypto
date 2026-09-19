# DISC-BTC-LEADLAG-001-v1 pre-outcome contract

## Decision

`COORD-DISC-QUANT-004` freezes exactly one new `CHEAP_SCREEN_READY` fingerprint: `DISC-BTC-LEADLAG-001-v1`.

This is a selection contract, not a backtest result. Candidate returns, untouched OOS, and genuine-forward outcomes were not inspected. The broker remains disconnected and this work grants no trade or promotion authority.

## Why this mechanism is materially distinct

The rule tests delayed cross-asset price discovery from a fixed BTC leader into fixed ETH/SOL followers. It does not:

- rank a current-survivor universe or revive residual/cross-sectional momentum;
- tune the rejected compression-breakout or shock-reversal rules;
- infer missing liquidation flow or proxy-rescue squeeze retention;
- reuse rejected funding or mark/index basis signals;
- approximate the unavailable Frizz/PlayBit source.

The economic claim is incremental and falsifiable: a strictly trailing beta-defined follower underreaction condition must improve over trading every identical BTC impulse, after conservative costs, in both mandatory followers.

## Timestamp-safe data path

The contract uses the same immutable, already integrity-verified OKX completed-hourly BTC/ETH/SOL dataset preserved at `orchestration/evidence/liquidity_meanrev_001_cache/dataset.json.gz`:

- venue endpoint: OKX `/api/v5/market/history-candles`;
- fixed instruments: BTC-USDT-SWAP, ETH-USDT-SWAP, SOL-USDT-SWAP;
- common bar interval: 1H;
- coverage: 2025-05-07 05:00 UTC through 2026-09-19 03:00 UTC;
- normalized rows: 35,997;
- normalized dataset SHA-256: `047c098bb2957557f8344ca30c32339ecac01b5067ae424b147d21c9e9caaf9f`.

The later selection runner must re-verify that identity and align all three instruments by exact timestamp before calculating features. Missing, duplicate, off-grid, or non-common timestamps fail closed. No instrument or date substitution is allowed.

## Frozen rule and scientific gates

The machine-readable contract in `orchestration/disc_btc_leadlag_001.json` freezes:

- one-hour BTC impulse definition;
- strictly prior 168-hour BTC volatility and follower beta;
- fixed beta bounds and underreaction gap;
- opposite-move no-trade guard;
- next-open follower entry and six-hour hold;
- identical no-underreaction baseline;
- ETH and SOL as mandatory replication cohorts;
- 60/20/20 chronology with purging and untouched OOS locked;
- 20 bps round-trip cost proxy stressed to 3x;
- sample floors, regime/half stability, two non-selectable gap sensitivities, and all pass/fail rules;
- one eligible primary fingerprint with no parameter, asset, timeframe, or date optimization.

The next bounded task is deterministic implementation and pre-OOS train/validation screening of this exact fingerprint. A fail must be preserved without tuning v1. A pass may only request a canonical one-candidate deep-validation transition; it still cannot open untouched OOS automatically.
