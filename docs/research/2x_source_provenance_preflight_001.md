# 2X-SOURCE-PREFLIGHT-001 — source/provenance + matched-control preflight

Status: **RESEARCH CONTRACT / NO CURRENT CANDIDATE / NO TRADING AUTHORITY**

Base `main`: `09015514f97d0b21107d033748446e606468e06d`

Issue: #505

This milestone performs the independent source/provenance preflight requested by the Lead around the existing Big-Move event/control builder in PR #433. It does **not** reimplement or modify #433, does not take over PR #506's forward-ledger contract, and does not touch Phase-3 #462 causal-acceptance or signal/promotion code.

The canonical machine-readable result is:

`money_intelligence/2x_source_provenance_preflight_v1.json`

## Current truth

At this cutoff the production `prediction_ledger` contains 112,462 rows and **zero** rows carrying a `big_move_2x` manifest. Therefore the 2x factory still has zero frozen / zero resolved immutable 2x forecasts. No current asset is promoted merely to populate a dashboard.

`DO_NOT_FREEZE_CANDIDATE` is the correct current state because the complete historical comparison/base-rate contract is not yet defensible over a broad survivorship-safe universe.

## Existing event-lab contract retained

PR #433 already defines the deterministic DEVELOPMENT-only 2x event/control builder. Its required snapshot fields are:

- `price`
- `liquidity_usd`
- `market_cap_usd`
- `float_supply`
- `listing_age_days`
- `volatility_30d`
- `return_30d`
- `sector`
- `regime`
- `tradable`
- `member`

Each field must retain value, observation time, availability time and source identity. Fixed neighbor pools are built **before** outcome labels, using the same decision time / venue / PIT sector / PIT regime plus frozen covariate distance/calipers. A censored or delisted asset can never be relabeled as a non-mover control. Outcome knowledge cannot refill or change the neighbor pool.

## Source audit

### Binance Public Data — usable raw venue backbone

Official project: https://github.com/binance/binance-public-data

Use case under this preflight:

- raw spot/futures trades and klines for venue-level prices and volumes;
- pre-cutoff trailing quote-volume liquidity proxy;
- pre-cutoff 30-day return and volatility;
- venue listing/trading age only when complete historical coverage and stable identity are proven;
- post-decision outcome OHLC labeling;
- checksums/versioning for archived files.

Important chronology rule: daily downloadable archives are published later than the market events they contain. The archive's later publication proves provenance of the retained historical copy; it does **not** by itself prove that a derived value was available at the old decision time. Pre-move features must be reconstructed only from raw event/bar timestamps that would already have completed by the cutoff. If Binance later corrects an archive, the changed checksum is a new source version and cannot silently overwrite an old research artifact.

### Coin Metrics Community API — conditional coverage/cross-check

Documentation: https://docs.coinmetrics.io/api/v4/

Community endpoint root: `https://community-api.coinmetrics.io/v4`

Use case under this preflight:

- historical market-existence and coverage-gap audit using market catalogs;
- selected community-enabled market/asset metrics;
- selected funding / open-interest / liquidation history only where community coverage and chronology are explicitly verified.

Catalog `min_time` / `max_time` is useful for survivorship and source-coverage checks, but it is not automatically the exact publication timestamp for every derived metric. Missing community coverage remains `MISSING`; it is never imputed or converted to zero.

### CoinGecko historical market data — conditional existing-access source

Documentation: https://docs.coingecko.com/reference/coins-id-market-chart-range

The historical market-chart endpoint documents price, market-cap and volume histories and explicit granularity/availability rules. It may help fill `market_cap_usd` for covered IDs/date ranges only if an already-authorized access tier exists. This milestone authorizes **no new purchase** and does not use CoinGecko as the historical universe definition.

Historical circulating-supply documentation: https://docs.coingecko.com/reference/coins-id-circulating-supply-chart

The current historical circulating-supply endpoint is documented as a premium endpoint, so it is **not** an authorized baseline dependency for this no-new-paid-spend factory lane.

## Feature readiness

| Feature | Status | Preflight rule |
|---|---|---|
| price | READY | Frozen venue + stable asset identity + exact completed pre-cutoff price. |
| liquidity_usd | READY AS PROXY | Predeclare trailing venue quote-volume window; never call it cross-venue depth. |
| market_cap_usd | PARTIAL BLOCKER | Needs audited PIT history. Existing authorized CoinGecko access or verified community coverage only. |
| float_supply | **HARD BLOCKER FOR BROAD UNIVERSE** | No proven zero-cost broad historical PIT source. Never backfill from today's supply or substitute total/max supply. |
| listing_age_days | CONDITIONAL READY | First verified venue trade/listing only when archive and identity coverage are complete. |
| volatility_30d | READY DERIVED | Frozen estimator from completed pre-cutoff bars only. |
| return_30d | READY DERIVED | Frozen definition from completed pre-cutoff bars only. |
| sector | **HARD BLOCKER FOR BROAD AUTOMATED MATCHING** | Current categories are look-ahead-prone; require timestamped historical taxonomy or predeclared mechanical PIT classifier. |
| regime | READY DERIVED | Freeze BTC/market regime rule before opening labels. |
| tradable | READY CONSERVATIVE | Must show actual venue trading at decision time and pass freshness/gap rules. |
| member | CONDITIONAL READY | Historical membership from archives including later delistings; never today's symbol list. |

## Stable asset identity is mandatory

A ticker is not an asset identity. Renames, redenominations, contract migrations and recycled symbols can otherwise splice unrelated histories.

Before a real cohort is admitted, freeze a mapping with at least:

- stable asset ID;
- venue symbol;
- base asset / network / contract identity when applicable;
- identity-valid-from and identity-valid-to;
- evidence source;
- mapping frozen timestamp;
- mapping SHA-256.

Ambiguous intervals are excluded rather than guessed.

## Outcome-blind matched-control contract

Execution order is fixed:

1. freeze the historical universe snapshot;
2. freeze stable identities and exact source versions;
3. compute every eligible pre-move covariate using only evidence available by the decision timestamp;
4. freeze exact matching calipers and distance;
5. build and hash neighbor pools with **no outcome access**;
6. attach future 2x labels only after the pools are frozen;
7. select complete non-movers only from those pre-frozen pools.

A control must use the same decision timestamp, venue, defensible PIT sector and PIT regime; pass the same liquidity/member/tradable/missing-data gates; have a complete uncensored 90-day forward outcome; fail to reach 2x; and satisfy same-asset overlap exclusion.

Forbidden shortcuts include replacing censored delistings with survivors, post-outcome pool refill, matching on post-move metadata, outcome-dependent dropping of missing derivative/on-chain rows, and treating reused controls as independent observations.

The full-cohort base rate is reported only if coverage/censoring permits a defensible population denominator. A matched-pair success rate is a conditional comparison, **not** the population base rate.

## Optional precursor fields

Spot-versus-leverage, OI, funding, basis, liquidations, exchange/on-chain flows, issuance/unlocks, catalyst state and relative strength remain useful research fields, but each becomes a separate frozen hypothesis with explicit coverage masks.

They may not retroactively decide baseline cohort membership or controls after outcomes are known. If a new field is added to matching later, create a fresh predeclared dataset version before its labels are opened.

## FACT / INFERENCE / HYPOTHESIS

**FACT**

- Live `prediction_ledger` has zero `big_move_2x` manifests at this cutoff.
- PR #433 already owns the historical event/control builder and remains open.
- PR #506 owns the separate immutable forward formation/resolution contract and remains open.
- Free public raw venue price/volume history is available with explicit archival/versioning semantics.
- Historical supply and taxonomy coverage are materially weaker than price/volume coverage under the no-new-paid-provider constraint.

**INFERENCE**

A zero-new-spend price/liquidity backbone is feasible, but broad PIT `float_supply` and PIT `sector` are currently the strongest blockers to running the existing #433 contract over a large survivorship-safe universe without hidden look-ahead.

The scientifically faster route is therefore **not** to weaken the contract. It is to start with a narrower coverage-complete cohort whose identity, market cap, supply and historical sector semantics can all be defended.

**HYPOTHESIS**

A narrower coverage-complete cohort should produce more trustworthy initial precursor/base-rate estimates than a nominally broad universe padded with current metadata, inferred supply or post-outcome exclusions.

Derivatives/leverage fields may add useful conditional lift, but should enter only after the baseline cohort is frozen and their missingness/availability policy is predeclared.

## Next bounded action

Build an outcome-blind **stable-asset identity + coverage manifest** for a narrow liquid crypto cohort. Admit only assets for which PIT market cap, supply, historical sector semantics, venue membership and stable identity can all be independently proven.

Before looking at 2x labels, freeze:

- candidate asset set and inclusion timestamp;
- source/version IDs;
- missing-data rules;
- minimum cohort size;
- liquidity threshold;
- stable identity mappings;
- market-cap/supply/sector source eligibility;
- regime function;
- matching calipers/distance.

If fewer than the predeclared minimum qualify, persist `COVERAGE_BLOCKED`. Do **not** weaken the fields, substitute today's metadata, buy a new provider, or create a forward candidate merely to make the dashboard non-empty.

Broker/live trading remains OFF.
