# 2X-COHORT-001 — outcome-blind coverage + prospective preflight

Status: **COVERAGE PREFLIGHT / OUTCOMES SEALED / NO FORWARD CANDIDATE / NO TRADING AUTHORITY**

Parent: #505  
Cohort: #514  
Base `main`: `5e720e8adbd3e0bcf539d97fdaa5a0c71428dbca`

This milestone starts Cohort 001 after the source/provenance preflight merged in PR #512. It does not modify PR #433's event/matched-control builder, does not take over PR #506, and does not touch Phase-3 #462 causal-acceptance or signal/promotion code.

The machine-readable contract is:

`money_intelligence/2x_cohort_001_preflight_contract.json`

The fail-closed validator is:

`big_move_cohort_preflight.py`

## Current truth

Read-only production ledger check at 2026-09-21T04:40Z:

- total `prediction_ledger` rows: **112,462**
- rows containing `calibration.big_move_2x`: **0**

PR #506 is still open on head `5a57047ed8b534b965215809aa013756bfdff2dc` and independent review has blocked that head because caller-supplied `formed_at` can be backdated. Therefore **no current asset is formed or counted as a forward 2x candidate in this milestone**.

The prospective lane remains:

`BLOCKED_UNTIL_TRUSTED_RECEIPT`

until a repaired #506 is integrated with a non-backdateable durable formation receipt bound to the full formation/evidence/reference-price payload.

## Historical Cohort 001 precommitment

To prevent outcome-driven universe construction, labels remain sealed while coverage is established.

The frozen historical rule is:

- venue: Binance spot
- quote: USDT
- decision grid: Monday 00:00 UTC weekly
- grid: 2021-01-04 through 2026-06-29
- universe: historical markets discovered from pinned archive/catalog evidence, **not today's symbol list**
- listing age: at least 180 days
- liquidity: trailing 30-day median quote volume at least $10M/day
- minimum coverage before labels may open: 12 stable assets, 624 eligible snapshots, and at least 52 decisions per eligible asset
- delisted/censored intervals remain explicit and can never be silently converted to non-mover controls
- same-asset 90-day overlap is removed only in the later label stage under the separately-owned #433 contract

These are pilot coverage gates, not statistical proof of precursor lift.

## Required PIT features

Each admitted snapshot must carry a stable asset identity plus all #433 baseline fields with source identity, source version, raw SHA-256, observation time, availability time and value:

`price, liquidity_usd, market_cap_usd, float_supply, listing_age_days, volatility_30d, return_30d, sector, regime, tradable, member`

The validator rejects:

- missing sources or source versions;
- malformed source digests;
- evidence available after the decision timestamp;
- values from sources not pre-approved by the frozen contract;
- recycled/ambiguous identity intervals;
- any pre-label artifact containing keys such as `outcome`, `reached_2x`, `future_return`, `target_hit_at`, or `resolution`.

## Source refinement after PR #512

Coin Metrics documents a no-key Community API root at:

`https://community-api.coinmetrics.io/v4`

and its asset catalog exposes metric/frequency coverage with a `community` flag. Coin Metrics documentation also uses `SplyCur` as a circulating-supply asset metric example.

That does **not** mean supply is solved broadly. Cohort 001 permits `COINMETRICS_COMMUNITY_SPLY_CUR` only when the exact asset/date/frequency is proven community-available and the retained observation/status timing is compatible with the historical cutoff. Missing coverage remains missing. Current supply is never backfilled.

Historical sector remains stricter. Cohort 001 permits only a versioned `PIT_PRIMARY_FUNCTIONAL_CLASSIFIER_V1`: a mechanical functional-role classification derived from primary launch/protocol documentation that was public by the decision time. Ambiguous or changed roles are excluded rather than mapped using today's category.

## Matched-control rules remain outcome-blind

The execution order is fixed:

1. freeze identities and source versions;
2. compute PIT features;
3. apply coverage/liquidity gates;
4. freeze matching calipers/distance and neighbor pools;
5. hash pools;
6. only then open <=90-day 2x labels.

Controls must remain same-time, same-venue, same-sector and same-regime under PR #433's separately-owned builder. No outcome-driven pool refill. Censored observations are never controls.

## Rare-event evaluation

The candidate system will be evaluated with:

- precision@K
- recall@K
- PR-AUC
- lift over matched/base rate
- tradability/capacity where defensible

Raw accuracy is not the primary metric.

No inferential precursor claim or calibrated probability is allowed from this cohort until at least 20 independent 2x events exist under the frozen design. Below that floor the output is descriptive/falsification-oriented only.

## FACT / INFERENCE / HYPOTHESIS / UNKNOWN

**FACT**

- PR #512 is integrated on current `main`.
- PR #506 is still untrusted for forward-evidence formation because its current head lacks a non-backdateable trusted creation receipt.
- Production `prediction_ledger` currently has zero `big_move_2x` manifests.
- Coin Metrics documents a Community API and per-metric community coverage metadata.
- The current cohort has not yet opened historical 2x labels.

**INFERENCE**

The merged source preflight plus this frozen coverage gate now allow the team to collect PIT inputs without later changing universe, source eligibility or minimum coverage after observing 2x outcomes.

Conditional community `SplyCur` coverage may reduce the supply blocker for a narrow subset, but it cannot be assumed across assets or dates.

**HYPOTHESIS**

A coverage-complete, liquidity-filtered weekly cohort with stable identity, PIT supply/market-cap/sector and outcome-blind controls will produce more trustworthy precursor lift estimates than a broader cohort padded with current metadata or post-outcome exclusions.

**UNKNOWN**

- how many historical assets actually satisfy all frozen fields;
- whether at least 20 independent genuine 2x events survive coverage/censoring/non-overlap;
- whether any precursor feature produces repeatable lift after matched controls;
- whether a repaired #506 will integrate before the first current asset clears the evidence threshold.

## Next execution step

Populate a real **pre-outcome coverage manifest** under this contract from pinned public data. Run `evaluate_coverage(...)`.

- If the result is `COVERAGE_BLOCKED`, persist the exact missing fields/assets and continue source recovery without opening labels.
- If the result is `READY_FOR_LABEL_OPEN`, hand the frozen manifest/digest to the separate #433 builder, open outcomes once, construct matched controls, and test the first predeclared precursor hypothesis.
- Do not form a live candidate until repaired #506 is integrated and trusted persistence proves formation existed before the move.

Broker/live trading remains OFF.
