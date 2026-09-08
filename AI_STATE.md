# AI DEVELOPMENT STATE
Last updated: 2026-09-08

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file from `main` before development. Never infer project state from ChatGPT memory. Update this file on `main` after every completed development/integration cycle.

## CURRENT ARCHITECTURE
Production: GitHub -> Render -> Python/FastAPI V3 -> Supabase. Production scans run about every 15 minutes and produce separate 24h/7d Top-20 rankings. Cloud research/backtesting runs continuously through a bounded Python worker army. PONS is included only when defensible public data supports it. There are 15 autonomous development roles; specialists use isolated branches and exact-head Security and Reliability success is required before merge.

## SAFETY INVARIANTS
No AI opinion, ranking score, evidence score, current order-book snapshot, paper P&L, ensemble weight, single OOS result, signed historical promotion, or risk-gate result by itself may authorize live BUY/SELL.

Mandatory chain:
RESEARCH -> BACKTEST -> VALIDATION -> UNTOUCHED OOS -> ROBUSTNESS/STABILITY -> MULTIPLE-TESTING FIREWALL -> POINT-IN-TIME UNIVERSE SAFETY -> STRATEGY-REGISTRY APPROVAL -> PRODUCTION-RISK APPROVAL -> GENUINE FORWARD PROOF -> GLOBAL/EXECUTION RISK CLEAR -> LIVE BUY/SELL.

Every later stage is restrictive-only. Missing, stale, contradictory, deteriorating, malformed, overlapping-only, insufficient, illiquid, execution-unsafe, portfolio-unsafe, statistically search-breadth-weak, survivorship-unsafe, or system-unsafe evidence means `WAIT / NO TRADE / RESEARCH_ONLY`.

`live_promotions.json` remains intentionally empty. Signing keys remain unused until genuine evidence is complete.

## VALIDATION / CALIBRATION
Chronological validation remains train / validation / untouched holdout. Robustness includes deterministic bootstrap/Monte Carlo resampling, parameter perturbation, regime stability, and conservative execution-cost stress. Prediction ledger is append-only with fixed `due_at`; forward proof counts only non-overlapping full-horizon resolved forecasts for the exact immutable strategy fingerprint. Calibration and deterioration can only restrict eligibility.

## ACC-001 MARKET / EXECUTION REALISM — COMPLETE
Integrated across PRs #38-#44 and follow-on work: realistic execution-cost stress, timestamp-safe funding/OI/basis, visible-depth estimates without inventing hidden liquidity, untouched-OOS execution robustness and strict chronology.

## 24/7 RESEARCH / ORCHESTRATION
PR #55 added bounded continuous Python research workers. PRs #65-#68 strengthened dedicated 24h/7d ACC-002 evidence collection, reserved accuracy capacity, independent history, and bounded retry/cache behavior. Existing paid infrastructure only unless approved; USD 30/month recurring ceiling. Workers remain research-only, without trade/write/promotion authority or broker connection.

## ACC-002 CROSS-ASSET RANK RESEARCH — IN PROGRESS
Integrated PRs #56-#60 and #64-#68. Protections include timestamp-safe cross-sectional relative strength; multi-lookback vol-normalized momentum; chronological train/validation/untouched OOS; purging; non-overlapping forward observations; predeclared grids; sufficient independent OOS; parameter and Top-15/30/45 liquidity-subset stability; 1x/1.5x/2x/3x cost stress; deterministic 500-resample bootstrap; dedicated 24h/7d workers. No profitability claim authorized yet.

## ACC-003 REGIME GATING — COMPLETE
PR #70; exact-head run `34252423032` on `c192affed37965f75f0972b608b965ae7c40084e`; merge `606595e50f3057452714c50eb88e8178213ac5c8`.

## ACC-004 CHAMPION / CHALLENGER — COMPLETE
PR #71; run `34256093230` on `e40ba49678e7726462df79fb16df6645b00396a0`; merge `223bbd094e0ca8350f2673e94bec3d34a8836f87`.

## ACC-005 MARKET-DATA PROVENANCE — COMPLETE
PR #72; run `34256741680` on `a4e5efe2fe0a0b6bcf89a735216abb37b9cd4651`; merge `bb4c0e4060bba067e5bee1a86f1247d30901d19e`.

## ACC-006 FORECAST DETERIORATION — COMPLETE
PR #73; run `34257098538` on `86b661a45817970ddaf91e56ffb469372125d20a`; merge `ad3973d01fe94d52010cdd6628d9f85a9dc23a3d`.

## ACC-007 ADVERSARIAL ROBUSTNESS — COMPLETE
PR #74; run `34257293281` on `59d7af5fcdbf8aee830f571a26f50488b81a6d58`; merge `76d83786acf132b6cc848dacf0edf17acba2ed77`.

## ACC-008 GENUINE FORWARD PROOF — COMPLETE
PR #75; run `34258912558` on `d47870757d4fdb846a8afadd3fab5835549a29d2`; merge `cf66104242467c8cf1177c91e20db206c92f62e5`. Exact fingerprint; non-overlapping full-horizon observations; >=20 independent 24h or >=12 7d; 3x modeled cost; positive after-cost expectancy; Wilson 95% lower >=50%; max forward DD <=12%; no deterioration.

## ACC-009 GLOBAL PORTFOLIO / EXECUTION RISK — COMPLETE
PR #76; exact-head run `34264596759` on `285add1ac65903432d8ed4ffaa19aba149f2aa3d`; merge `4f70e89f81b4f16df39d4fd2fe88b3c0f298d6f5`.

## ACC-010 SIZE-AWARE EXECUTION — COMPLETE
PR #77; exact-head run `34265226943` on `324fc08f4723190df50e01d28e608e506d3fec95`; merge `edbed73a7b4236234ea2ff958e94ca2510db2df1`.

## ACC-011 POINT-IN-TIME UNIVERSE / SURVIVORSHIP FIREWALL — COMPLETE
PR #79; exact-head run `34266482390` on `5815277b697b3bda8fac2a33ec9c286ef8f42c68`; squash merge `20c383c1dae1d2413c534b749b10faf95fb83f57`. Today's survivors are not accepted as historical universe evidence; promotion-grade cross-sectional research requires timestamped investable-universe snapshots with provenance; uncovered/malformed historical membership blocks promotion.

## ACC-012 MULTIPLE-TESTING / FALSE-DISCOVERY FIREWALL — COMPLETE
PR #78; exact-head run `34265615227` on `4bd7d3905a89602630e4137b3a3714c2311eee71`; squash merge `8ddac654e63a70a95f811dd14777e649faefd625`. Research predeclares full search breadth before OOS; worker sharding cannot hide breadth; required OOS depth/bootstrap support rise with search breadth; gate can only demote/reject.

## ACC-013 GENUINE-FORWARD SHADOW CHAMPION / CHALLENGER — COMPLETE
PR #80; exact-head run `34268140486` on `0a034a920d22d2e9415a105170edd3ef831b12ed`; squash merge `51db55b5339bcbd5183044a50521e6fe36770caa`. Champion/challenger comparison uses matched independent future buckets, exact distinct fingerprints and 3x own modeled costs. Requires >=20 matched 24h or >=12 matched 7d periods, positive challenger after-cost expectancy/mean advantage, >=55% pairwise wins, and positive deterministic SHA-256 bootstrap 5th-percentile mean advantage. Passing only recommends Strategy Registry review.

## ACC-014 CHAOS / FAILURE FAIL-CLOSED GATES — COMPLETE
PR #81 `ACC-014: Add chaos and failure fail-closed gates` passed exact-head Security and Reliability run `34268401662` on `c99ef9261acdcfb4cf340a4bc98d0f2ab8664a0a` and was squash-merged as `c91e337439782ac4b6c60a06a81aee5fb051ee29`.

Implemented:
- incomplete/corrupt broad market snapshots force global WAIT;
- stale production health state (>45 minutes) forces global WAIT;
- malformed health metrics fail closed;
- deep-scan coverage collapse forces WAIT;
- excessive scan-failure ratio forces WAIT;
- repeated system errors, unhealthy scans, broad volatility/liquidity stress and cross-exchange instability remain blocking;
- adversarial tests cover corrupt market data, stale health, malformed health, scan coverage collapse, excessive scan failures, bad execution, portfolio drawdown/loss streak and directional concentration;
- all behavior is restrictive-only and cannot create trade authority.

## AUTHENTIC PAPER TRADING STATE
The continuous paper account remains forward-only and broker-disconnected. Authentic baseline is exactly `$100,000` from `2026-09-08T01:17:49Z`; never reset or rewrite it. Current account value = immutable starting capital plus realized/open P&L. Safety/execution gates may reject entries but never fabricate or reset history. Paper performance is evidence only.

## ACCURACY PROGRAM STATUS
ACC-001 COMPLETE; ACC-002 IN PROGRESS; ACC-003 COMPLETE; ACC-004 COMPLETE; ACC-005 COMPLETE; ACC-006 COMPLETE; ACC-007 COMPLETE; ACC-008 COMPLETE; ACC-009 COMPLETE; ACC-010 COMPLETE; ACC-011 COMPLETE; ACC-012 COMPLETE; ACC-013 COMPLETE; ACC-014 COMPLETE.

## COST / SPEED POLICY
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed. Prefer existing shared Render compute, deterministic Python, public/free defensible data, caching/reuse, early rejection and bounded concurrency. No paid feed/service/compute without approval.

## SPEED WITHOUT CHEATING
The fastest safe path is to preserve stable exact strategy fingerprints while genuine forward observations accumulate. Challengers may research and run in shadow, but avoid needless champion fingerprint churn that discards comparable forward evidence. Never count overlapping forecasts as independent, lower forward-proof thresholds, or reset paper history to accelerate results.

## EXACT NEXT STEP
1. Continue genuine ACC-002 24h/7d evidence and worker health. No profitability claim unless required horizon evidence genuinely passes.
2. Audit worker scheduling for wasted duplicate work, timeout hotspots and evidence-continuity churn. Improve caching/deduplication/reserved accuracy capacity without increasing heavy concurrency beyond cost/safety bounds.
3. Keep stable champion fingerprints while challengers run shadow comparison. Only evidence-backed changes should create a new fingerprint.
4. Preserve `live_promotions.json` empty, signing keys unused, PONS fail-closed, immutable $100k paper ledger and broker-disconnected state.
5. Only add further microstructure features when genuine timestamped data supports them; never reconstruct unavailable order books or liquidations from candles.
6. Optimize after-cost risk-adjusted realized performance with tail protection and abstention, not headline accuracy.
7. Update this file after every completed integration cycle.
