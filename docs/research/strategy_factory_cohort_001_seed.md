# Strategy Factory Cohort 001 — outcome-blind seed

Formation cutoff: **2026-09-21T04:40:37Z**  
Main observed at formation: `09015514f97d0b21107d033748446e606468e06d`

## Why this exists

PR #507 is still open and its exact head is blocked by independent review because rejected-memory admission is exact-label based rather than label-invariant/semantic. Therefore this artifact **does not screen any candidate** and **does not alter the canonical queue**. It prepares a diverse first cohort for issue #513 so execution can start immediately after the repaired #507 admission gate is integrated.

No protected OOS or forward evidence was opened. No candidate was promoted. Broker/live trading remains off.

## Cohort

Eight outcome-blind seed designs were prepared under one multiple-testing family. Seven use the already certified fixed BTC/ETH/SOL 1H OKX development dataset (`047c098bb2957557f8344ca30c32339ecac01b5067ae424b147d21c9e9caaf9f`) with a strict selection cutoff at 2026-08-31T23:00Z; rows from 2026-09-01 onward are explicitly protected from cheap-screen access for these candidates. One carry design remains **data-preflight only** until a synchronized spot/perp/funding dataset is frozen and hashed.

1. `DISC-BREADTH-PERSIST-001-v1` — synchronized low-dispersion market-breadth continuation.
2. `DISC-RESIDUAL-REV-001-v1` — beta-hedged ETH/SOL residual mean reversion versus BTC.
3. `DISC-SIGNED-VOLUME-DRIFT-001-v1` — signed-volume pressure continuation using only explicit OHLCV proxy data.
4. `DISC-LOWVOL-DRIFT-REV-001-v1` — low-participation multi-hour drift reversion; explicitly excludes the rejected high-volume/wide-range shock design.
5. `DISC-WEEKEND-NORMALIZE-001-v1` — weekend liquidity-normalization reversal with one fixed UTC session definition.
6. `DISC-MODERATEVOL-AUTOCORR-001-v1` — moderate-volatility time-series continuation after three same-sign hourly returns.
7. `DISC-RANGE-AUCTION-REV-001-v1` — low-efficiency range-edge auction reversion.
8. `DISC-DELTA-CARRY-001-v1` — long-spot/short-perp positive-funding carry, data-preflight only; directional funding prediction is not reused.

Each seed records exact signal/execution rules, realistic base costs and stress multipliers, fixed chronology and protected-evidence locks, one planned parameter variant only, family-wide search breadth of eight, and explicit data-readiness state.

## Fail-closed identity self-audit

A self-audit caught that the first draft of `strategy_factory_cohort_001_seed.json` contained inline `scientific_design_sha256` and `contract_sha256` strings that had not actually been generated from the declared canonicalization. Those inline values are **invalid and non-authoritative** and must not be used for admission, screening, rejection memory, or promotion.

The independently recomputed identities are recorded in `orchestration/cohorts/strategy_factory_cohort_001_identity_correction.json`. PR #515 must remain blocked/draft until the seed JSON itself is regenerated to contain only those canonical values and the repaired #507 semantic-rejection implementation independently validates the candidates. This fail-closed correction was made before any screen or outcome inspection.

## Rejected-design audit

The seed set was constructed to avoid cosmetic reopening of currently known rejected designs: `DATA-BASIS-001`, `DATA-FUNDING-001`, `ACC-002`, `DISC-VOL-BREAKOUT-001-v1`, `DISC-LIQUIDITY-MEANREV-001-v1`, and `DISC-BTC-LEADLAG-001-v1`.

It also avoids claiming readiness for the blocked/deprioritized `DISC-RESIDUAL-MOMENTUM-001-v1`, `DISC-SQUEEZE-RETENTION-001-v1`, and `DISC-FRIZZ-PLAYBIT-EMA-001-v1`.

The cohort must still be revalidated against the repaired label-invariant rejected-design memory once #507 changes. If any seed collides semantically under the canonical implementation, reject that seed rather than renaming it.

## Exact next action

After a repaired #507 is independently reviewed, merged, and exact-head green:

1. regenerate the seed JSON with the recomputed canonical identities and verify them deterministically;
2. run the canonical semantic admission validator against all eight seeds;
3. reject any semantic collision without rescue;
4. freeze/build the exact selection dataset partition for each admitted design;
5. run the admitted data-ready cheap screens in deterministic parallel;
6. classify every failure/inconclusive result through #510;
7. keep OOS/forward locked and promote **at most one** genuine survivor to expensive validation.

Machine-readable preparation lives under `orchestration/cohorts/strategy_factory_cohort_001_*`.
