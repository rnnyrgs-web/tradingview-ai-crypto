# Liquidity-shock mean-reversion: rejected before OOS

The bounded `DISC-LIQUIDITY-MEANREV-001-v1` screen fails its original gates.
No profitable candidate or deep-validation promotion is justified. This audit
reuses PR #416's first artifact; no new market outcomes were fetched.

## Freeze and reproduction

Contract commit `dc6ffe7489ec0a5bdaf119872772fbe26fe221aa` preceded implementation,
workflow execution and evidence inspection. The contract is unchanged at
SHA-256 `19252de4464fc997632b0500fded857bc58d5bdad49d6f72e3660eba75a28b57`.
It defines one eligible candidate, three mandatory fixed replication assets,
one timeframe and two non-selectable falsifiers. No post-outcome parameter,
cost, sample-size or acceptance threshold was changed.

The first archive digest, sealed envelope and normalized dataset hash match.
Each fixed series has 11,999 UTC hourly rows with zero missing intervals;
all last bars ended before artifact generation. The original collector filters
unconfirmed candles. Raw exchange responses/confirmation flags were not retained,
so completion is supported by collector code and time bounds, not an independent
raw-response audit. No historical executable quote/fill evidence exists.

Offline replay reproduces the **entire original selection object exactly**.
The cache is durable in `orchestration/evidence/liquidity_meanrev_001_cache/`.
It preserves original OOS data only as opaque provenance. All scoring stops at
the frozen validation end, 2026-06-10T04:00Z exclusive. No OOS outcome was opened.

## Economic result

| Metric | Train | Validation |
|---|---:|---:|
| Completed trade labels | 425 | 123 |
| Calendar days in scored interval | 298.96 | 98.00 |
| Trade labels per 30 days, three assets combined | 42.65 | 37.65 |
| Distinct signal hours | 275 | 77 |
| Mean net bps, base 20 bps costs | -48.87 | -5.48 |
| Mean net bps, 3× / 60 bps costs | -88.87 | -45.48 |
| Median net bps, 3× | -65.34 | -49.21 |
| Profit factor, 3× | 0.331 | 0.456 |
| Win rate, 3× | 31.06% | 31.71% |
| Mean winner / loser bps, 3× | 141.54 / -192.67 | 120.16 / -122.38 |
| 5th / 95th percentile net bps, 3× | -486.92 / 224.11 | -298.78 / 285.23 |
| Additive trade-label drawdown bps, 3× | 38675.86 | 6059.63 |

Drawdown is the original additive closed-label statistic ordered by signal
time. It is **not a portfolio percentage**, capital-normalized equity curve or
intrahold mark-to-market risk estimate. Correlated simultaneous BTC/ETH/SOL
trades are not independent observations. These distinctions prohibit an
unsupported useful-frequency or portfolio-economics claim.

All three assets fail: validation means at 3× costs are BTC -50.83, ETH -46.73,
SOL -41.63 bps. Validation halves return -29.15 / -63.77 bps. BULL/BEAR means
are -52.49 / -40.51 bps. Both sigma falsifiers fail. The liquidity filters add
only 1.60 bps versus the losing validation baseline. Validation gross mean is
14.52 bps, below the base 20 bps cost proxy; even base-cost expectancy fails.

The complete descriptive record includes every cost stress, month, asset,
direction, regime, half, quantile and win/loss distribution in
`orchestration/evidence/disc_liquidity_meanrev_001_audit_20260919.json`.
These added descriptions are explicitly post-selection and cannot change gates.
No inferential significance or multiple-comparison-adjusted discovery is claimed.

## What was learned and fixed

The tested OHLCV shock proxy does not identify an economical six-hour reversal
on these fixed cohorts. This does not establish that actual liquidation or
order-book overshoot can never revert. The frozen rule has **no stop or target**;
its only exit is the six-hour time exit. Changing that now would create a new
trial, not rescue v1. Composite costs are a declared assumption, not observed
fees, spreads, funding or slippage on historical fills.

The audit fixes concrete safety defects without altering the contract/results:

- Supplied contracts now undergo checksum validation and must match the original
  pinned contract, preventing re-signed cost/parameter changes under v1.
- Hourly gaps and off-grid timestamps fail closed instead of compressing missing
  time into a misleading six-bar label. The original dataset has no such gaps.
- Verification uses the original cache with no fresh-data fallback, preventing
  repeated downloads, moving train/OOS boundaries and repeated selection trials.
- Rejection memory, DATA-005/006 completion details, DATA-007 maturation blockers,
  safety invariants and machine-readable handoff headings are preserved.
- Routing tests target the new active assignments and explicitly cover clearing
  a completed liquidity lease without reopening the rejected fingerprint.

The original `signal_ts` is the bar-open label; the decision time is one hour
later. Next-open execution is an idealized causal label with latency covered
only by the cost assumption. A future successful candidate would require actual
execution validation; this rejected candidate receives none.

## Pivot and continuation

The ranked queue and all four discovery assignments advance to materially
distinct `DISC-SQUEEZE-RETENTION-001-v1`: continuation after price retention and
forced-flow normalization, rather than immediate contrarian entry.
The Sep. 19 Money Intelligence example is hypothesis generation only.
The first data preflight is recorded separately; do not replace unavailable
historical liquidation data with volume, current snapshots or post-event labels.

Frizz remains source-fingerprint blocked. Deep-candidate count stays zero;
OOS, forward, promotion and broker authority remain closed.
