# AI DEVELOPMENT STATE
Last updated: 2026-09-09

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file from `main` in full before development. Never infer current project state only from ChatGPT memory. Update this file on `main` after every completed development/integration cycle.

## CURRENT ARCHITECTURE
Production: GitHub -> Render -> Python/FastAPI V3 -> Supabase. Production scans run about every 15 minutes and produce separate 24h/7d Top-20 rankings. Cloud research/backtesting runs continuously through a bounded 17-worker Python army on the existing Render coordinator. PONS is included only when defensible public data supports it. Specialist development uses isolated branches and exact-head Security and Reliability success is required before merge.

Primary production Render service: `srv-dadliegu01pc73bc7t50` (`tradingview-ai-crypto`).
Continuous research coordinator: `srv-dafgtead0e5s73cc7ekg`.
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed.

## SAFETY INVARIANTS
No AI opinion, ranking score, evidence score, current order-book snapshot, paper P&L, ensemble weight, single OOS result, signed historical promotion, observability metric, supervisor status, diagnostic, incident fingerprint, canary result, risk-gate result, selective-precision result, or shadow execution result by itself may authorize live BUY/SELL.

Mandatory chain:
RESEARCH -> BACKTEST -> VALIDATION -> UNTOUCHED OOS -> ROBUSTNESS/STABILITY -> MULTIPLE-TESTING FIREWALL -> POINT-IN-TIME UNIVERSE SAFETY -> STRATEGY-REGISTRY APPROVAL -> PRODUCTION-RISK APPROVAL -> GENUINE FORWARD PROOF -> GLOBAL/EXECUTION RISK CLEAR -> LIVE BUY/SELL.

Every later stage is restrictive-only. Missing, stale, contradictory, deteriorating, malformed, overlapping-only, insufficient, illiquid, execution-unsafe, portfolio-unsafe, statistically search-breadth-weak, survivorship-unsafe, or system-unsafe evidence means `WAIT / NO TRADE / RESEARCH_ONLY`.

`live_promotions.json` remains intentionally empty. Signing keys remain unused. Broker remains disconnected. Do not add credentials or real order capability without explicit user approval plus all canonical evidence gates.

## VALIDATION / CALIBRATION
Chronological validation remains train / validation / untouched holdout. Robustness includes deterministic bootstrap/Monte Carlo resampling, parameter perturbation, regime stability, conservative execution-cost stress and false-discovery/search-breadth penalties. Prediction ledger is append-only with fixed `due_at`; forward proof counts only non-overlapping full-horizon resolved forecasts for the exact immutable strategy fingerprint. Calibration, deterioration, selective-precision analysis, observability, worker supervision, diagnostics and deployment canary signals can only restrict or inform operations; none can authorize trading.

Evidence score is not probability. Never choose a production threshold by looking at untouched/forward outcomes and then treating that same evidence as confirmatory. Any future production selectivity change must be predeclared, restrictive-only, fingerprint-aware, and independently validated.

## ACCURACY PROGRAM STATUS
- ACC-001 MARKET / EXECUTION REALISM — COMPLETE. PRs #38-#44 and follow-ons.
- ACC-002 CROSS-ASSET RANK RESEARCH — IN PROGRESS. PRs #56-#60 and #64-#68: cross-sectional relative strength, multi-lookback vol-normalized momentum, train/validation/untouched OOS, purging, non-overlapping observations, fixed predeclared grids, Top-15/30/45 liquidity stability, 1x/1.5x/2x/3x cost stress, deterministic 500-resample bootstrap, dedicated 24h/7d workers. No profitability claim authorized yet.
- ACC-003 REGIME GATING — COMPLETE. PR #70; merge `606595e50f3057452714c50eb88e8178213ac5c8`.
- ACC-004 CHAMPION / CHALLENGER — COMPLETE. PR #71; merge `223bbd094e0ca8350f2673e94bec3d34a8836f87`.
- ACC-005 MARKET-DATA PROVENANCE — COMPLETE. PR #72; merge `bb4c0e4060bba067e5bee1a86f1247d30901d19e`.
- ACC-006 FORECAST DETERIORATION — COMPLETE. PR #73; merge `ad3973d01fe94d52010cdd6628d9f85a9dc23a3d`.
- ACC-007 ADVERSARIAL ROBUSTNESS — COMPLETE. PR #74; merge `76d83786acf132b6cc848dacf0edf17acba2ed77`.
- ACC-008 GENUINE FORWARD PROOF — COMPLETE. PR #75; merge `cf66104242467c8cf1177c91e20db206c92f62e5`. Exact fingerprint, >=20 independent 24h or >=12 7d, 3x modeled cost, positive after-cost expectancy, Wilson 95% lower >=50%, max forward DD <=12%, no deterioration.
- ACC-009 GLOBAL PORTFOLIO / EXECUTION RISK — COMPLETE. PR #76; merge `4f70e89f81b4f16df39d4fd2fe88b3c0f298d6f5`.
- ACC-010 SIZE-AWARE EXECUTION — COMPLETE. PR #77; merge `edbed73a7b4236234ea2ff958e94ca2510db2df1`.
- ACC-011 POINT-IN-TIME UNIVERSE / SURVIVORSHIP FIREWALL — COMPLETE. PR #79; merge `20c383c1dae1d2413c534b749b10faf95fb83f57`.
- ACC-012 MULTIPLE-TESTING / FALSE-DISCOVERY FIREWALL — COMPLETE. PR #78; merge `8ddac654e63a70a95f811dd14777e649faefd625`.
- ACC-013 GENUINE-FORWARD SHADOW CHAMPION / CHALLENGER — COMPLETE. PR #80; merge `51db55b5339bcbd5183044a50521e6fe36770caa`.
- ACC-014 CHAOS / FAILURE FAIL-CLOSED GATES — COMPLETE. PR #81; merge `c91e337439782ac4b6c60a06a81aee5fb051ee29`.

## SAFE RESEARCH / OPERATIONS INFRASTRUCTURE
- SAFE WORKER THROUGHPUT — COMPLETE. PR #82; bounded heavy concurrency, dedicated ACC-002 accuracy lane, bounded failure backoff.
- SHARED IMMUTABLE DEEP-HISTORY CACHE — COMPLETE. PR #83; exact-request identity, integrity/provenance, bounded TTL, chronology checks.
- RESEARCH OBSERVABILITY — COMPLETE. PR #84.
- EXACT DEEP-HISTORY NETWORK LATENCY — COMPLETE. PR #85.
- PRIVATE RENDER OBSERVABILITY LOGGING — COMPLETE. PRs #86/#87.
- SELF-HEALING 24/7 WORKER SUPERVISOR — COMPLETE. PR #88; merge `f02d91edb458cacb5be02fba4325555f381f7123`.
- PRIVACY-PRESERVING WORKER FAILURE DIAGNOSTICS / BUG LEDGER — COMPLETE. PR #89; merge `edef2386262459935987249cb7a6414bd721dbfe`.
- ACC-002 expected insufficient-liquidity outcome classified as `research_blocked` — COMPLETE. PR #90; merge `220452eca6242999cac7381bb9a37c77354b710a`. No thresholds weakened.
- PONS diagnostic gap — COMPLETE. PR #91; merge `fa5541ff3154da1be11c560008155c582b3de3ef`.
- PONS insufficient public history classified as `research_blocked` — COMPLETE. PR #92; merge `03fcf47c8745538bad76013ebec07ef8b439a917`. History minimums remain unchanged; missing data is never fabricated.
- DEPLOYMENT CANARY / CONTROLLED ROLLBACK DECISION LAYER — COMPLETE. PR #93; merge `62a7811cd004b7ec4441f6d749308fe55308e7a7`. Recommendation only; no automatic repo/deploy/trade authority.
- DEEP-HISTORY TTL-BOUNDARY CACHE REUSE — COMPLETE. PR #94; merge `4e3e9bd2c13d4134fd8990a9a17496376f3bbe97`. Does not stretch TTL or alter chronology/source behavior.

## KRAKEN READINESS
PR #95 `KRAKEN BROKER-DISCONNECTED SHADOW EXECUTION` passed exact-head Security and Reliability run `34292185973` on `5134af4980f02586d72518c69761d63f61baa26d` and was squash-merged as `dd2ecd13ce5860f31a33580b890b56d39ca60f8d`.
Public timestamped Kraken order-book snapshots can be walked for hypothetical visible-depth VWAP/slippage/fee-adjusted fills. Stale/future/malformed/insufficient-depth books fail closed; hidden liquidity is never extrapolated. Adapter remains broker/order/trade authority false and contains no private credentials or order endpoints.

## PRODUCTION SCAN PERSISTENCE INCIDENT — RESOLVED
PR #97 passed exact-head run `34292801678` on `1e07b192ea619286113cf4df4161bdf1e4178165`; squash merge `4a1f30beb42d1b2f64b7956ad8404e5ff400b6ea`. It added privacy-preserving failure classification without masking failures.

Fresh post-PR #97 evidence then identified the exact root cause: `fetch_resolved_predictions()` requested nonexistent `prediction_ledger.created_at`, producing Supabase SQLSTATE `42703` and blocking opportunity persistence. PR #98 removed only that nonexistent field while preserving `due_at`/`resolved_at` chronology and forward/OOS logic. Exact-head Security and Reliability run `34293217999` passed on `19218735fe4a5fed1147a0f12ac808dc7ca238d1`; squash merge `f2c5dcaf2e83d97973e161d7f54e121b9060183b`.

Live verification on 2026-09-09 showed repeated healthy `/scan` 200 responses after the fix, including approximately 00:05, 00:09, 00:35, 00:55 and 01:06 UTC, with no recurrence of the `prediction_ledger.created_at` persistence failure in observed logs. Individual symbol-level collection errors still occur and remain fail-closed rather than being fabricated away.

## SELECTIVE HIGH-CONFIDENCE PRECISION RESEARCH — COMPLETE AS MEASUREMENT LAYER
PR #99 `Measure selective high-confidence signal precision on current main` was recreated directly from current main after PRs #97/#98. Exact tested head `6c819b36b0221f0322bac5a8e6333c2bb7468d3d` passed Security and Reliability run `34297224092` (#731) and was squash-merged as `8c4da6f195ef138e458fae1770663fa8fb489153`.

The module measures resolved 24h/7d precision for fixed, predeclared evidence-score cutoffs 60/70/80/90, minimum samples >=30, Wilson 95% lower bounds, and excludes observations explicitly recorded with unreliable market consensus. Missing historical consensus fields are not fabricated. Output is descriptive research only with `trade_authority=false`, `promotion_authority=false`, and `probability_claim=false`. No production signal gate or strategy fingerprint changed. No accuracy improvement claim is authorized until genuine resolved evidence supports one.

## RESOLVED SELECTIVE-PRECISION OBSERVABILITY — COMPLETE
PR #101 `Expose resolved selective precision observability` exact tested head `cd9a8a07f8244c521e6cab4eeb7a33b16c8cac92` passed Security and Reliability run `34299614199` (#766) and was squash-merged as `e1d1a2309a84c9760c90b93172f4c3b0f7214859`.

A protected read-only `/selective-precision` endpoint now feeds only genuinely resolved prediction-ledger rows into the fixed-threshold PR #99 measurement. It explicitly reports `research_only=true`, `trade_authority=false`, `promotion_authority=false`, and `threshold_selection_authority=false`. No threshold selection, production strategy behavior, broker connectivity, paper-ledger behavior, market-data source, or cost policy changed. No accuracy or profitability improvement claim is authorized from this observability layer alone.

## CONTINUOUS AI OBSERVER RATE-LIMIT BACKOFF — COMPLETE AND LIVE
Fresh production logs on 2026-09-09 showed the read-only continuous AI observer repeatedly failing with `RateLimitError` roughly every configured 300 seconds while `/health`, `/scan`, and paper risk behavior remained healthy. This was a cost/reliability inefficiency, not a trading-strategy failure.

PR #100 `Back off continuous AI observer on rate limits` exact tested head `feb7ab949d0dde80abb1d091514ce9c53eb9c7eb` passed Security and Reliability run `34297760626` (#737) and was squash-merged as `77a5ab6e501f6219916ef090b2fd52b1a19ff4e6`.

Behavior now:
- `RateLimitError` gets bounded exponential retry backoff: first retry >=600s, then grows, default cap 3600s, hard environment cap 7200s;
- unrelated transient errors retain the normal configured observer cadence;
- a successful observer cycle resets the failure streak immediately;
- status exposes only failure streak, next retry timing, and error type; raw exception detail/secrets are not surfaced;
- observer remains read-only with trade/write/promotion authority false;
- no strategy, OOS/forward threshold, market-data source behavior, paper ledger, broker connectivity, or cost ceiling changed.

Render auto-deploy verified commit `77a5ab6e501f6219916ef090b2fd52b1a19ff4e6` live on fresh instance `srv-dadliegu01pc73bc7t50-8xp79`. Application startup completed and the first live rate-limit event logged `retry_in=600s`, confirming the new backoff path is active. `/scan` remained 200 immediately before cutover and service root/health remained reachable after deploy.

## AUTHENTIC PAPER TRADING STATE
The continuous paper account remains forward-only and broker-disconnected. Authentic baseline is exactly `$100,000` from `2026-09-08T01:17:49Z`; never reset or rewrite it. Current account value = immutable starting capital plus realized/open P&L. Safety/execution gates may reject entries but never fabricate or reset history. Paper performance is evidence only.

Observed live logs continue to show legitimate restrictive decisions such as `Global paper WAIT: correlated_directional_concentration`; do not weaken these risk gates merely to increase trade frequency.

## COST / SPEED POLICY
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed. Prefer existing shared Render compute, deterministic Python, public/free defensible data, caching/reuse, early rejection and bounded concurrency. No paid feed/service/compute without approval.

## SPEED WITHOUT CHEATING
Preserve stable exact strategy fingerprints while genuine forward observations accumulate. Challengers may run in shadow. Never count overlapping forecasts as independent, lower forward-proof thresholds, reset paper history, raise heavy concurrency, stretch cache TTLs, change market-data source behavior, or cherry-pick confidence thresholds merely to accelerate results.

## OPEN / STALE PR POLICY
Current old open PRs #34, #33 and #13 predate the current architecture. Do not merge them merely because they are open or historically green. Re-evaluate against current main, current invariants and exact-head CI first; close/supersede when appropriate.

## EXACT NEXT STEP
1. Verify PR #101 auto-deploy and protected `/selective-precision` endpoint health; treat output as descriptive research only.
2. Enrich only future prediction-ledger records with timestamp-safe pre-forecast agreement/provenance fields needed to test genuinely independent signal agreement (for example reliable market-consensus state). Never retroactively fabricate those fields for historical rows.
3. Continue ACC-002 genuine 24h/7d OOS/forward evidence and worker-health monitoring. No profitability or accuracy-improvement claim unless genuine evidence passes.
4. Verify subsequent live cycles honor the new continuous-AI rate-limit backoff (no repeated 5-minute retry loop while quota remains exhausted) and that normal cadence resumes after a successful cycle.
5. Confirm a fresh PONS cycle remains explicit `research_blocked` for insufficient public history without increasing unknown worker failures; do not lower candle/history requirements.
6. Verify supervisor/canary remain healthy in current coordinator logs: no stale/crashed workers, restart loop, timeout spike, or rollback recommendation without proven unhealthy evidence.
7. Compare post-PR #94 non-zero cache/history metrics; optimize only proven cold/deep-history inefficiency without changing chronology, market-data source behavior, evidence requirements, or the $30/month ceiling.
8. Extend Kraken readiness only with broker-disconnected public-data shadow execution/reconciliation until genuine forward proof and all canonical approval gates pass; no credentials or real orders yet.
9. Preserve stable exact champion fingerprints while challengers run in shadow; only evidence-backed strategy behavior changes create a new fingerprint.
10. Preserve empty `live_promotions.json`, unused signing keys, immutable $100k paper ledger and broker-disconnected state.
11. Only add microstructure features when genuine timestamped data supports them; never reconstruct unavailable order books/liquidations from candles.
12. Optimize after-cost risk-adjusted realized performance with tail protection and abstention, not headline accuracy.