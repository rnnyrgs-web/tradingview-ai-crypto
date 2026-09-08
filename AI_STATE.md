# AI DEVELOPMENT STATE
Last updated: 2026-09-08

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file from `main` before development. Never infer project state from ChatGPT memory. Update this file on `main` after every completed development/integration cycle.

## CURRENT ARCHITECTURE
Production: GitHub -> Render -> Python/FastAPI V3 -> Supabase. Production scans run about every 15 minutes and produce separate 24h/7d Top-20 rankings. Cloud research/backtesting runs continuously through a bounded 17-worker Python army on the existing Render coordinator. PONS is included only when defensible public data supports it. Specialist development uses isolated branches and exact-head Security and Reliability success is required before merge.

## SAFETY INVARIANTS
No AI opinion, ranking score, evidence score, current order-book snapshot, paper P&L, ensemble weight, single OOS result, signed historical promotion, observability metric, or risk-gate result by itself may authorize live BUY/SELL.

Mandatory chain:
RESEARCH -> BACKTEST -> VALIDATION -> UNTOUCHED OOS -> ROBUSTNESS/STABILITY -> MULTIPLE-TESTING FIREWALL -> POINT-IN-TIME UNIVERSE SAFETY -> STRATEGY-REGISTRY APPROVAL -> PRODUCTION-RISK APPROVAL -> GENUINE FORWARD PROOF -> GLOBAL/EXECUTION RISK CLEAR -> LIVE BUY/SELL.

Every later stage is restrictive-only. Missing, stale, contradictory, deteriorating, malformed, overlapping-only, insufficient, illiquid, execution-unsafe, portfolio-unsafe, statistically search-breadth-weak, survivorship-unsafe, or system-unsafe evidence means `WAIT / NO TRADE / RESEARCH_ONLY`.

`live_promotions.json` remains intentionally empty. Signing keys remain unused. Broker remains disconnected.

## VALIDATION / CALIBRATION
Chronological validation remains train / validation / untouched holdout. Robustness includes deterministic bootstrap/Monte Carlo resampling, parameter perturbation, regime stability, conservative execution-cost stress and false-discovery/search-breadth penalties. Prediction ledger is append-only with fixed `due_at`; forward proof counts only non-overlapping full-horizon resolved forecasts for the exact immutable strategy fingerprint. Calibration, deterioration and observability can only restrict or inform research operations; none can authorize trading.

## ACCURACY PROGRAM STATUS
- ACC-001 MARKET / EXECUTION REALISM — COMPLETE. PRs #38-#44 and follow-ons: realistic costs, timestamp-safe derivatives inputs, visible-depth evidence, strict chronology.
- ACC-002 CROSS-ASSET RANK RESEARCH — IN PROGRESS. PRs #56-#60 and #64-#68: cross-sectional relative strength, multi-lookback vol-normalized momentum, train/validation/untouched OOS, purging, non-overlapping observations, fixed predeclared grids, Top-15/30/45 liquidity stability, 1x/1.5x/2x/3x cost stress, deterministic 500-resample bootstrap, dedicated 24h/7d workers. No profitability claim authorized yet.
- ACC-003 REGIME GATING — COMPLETE. PR #70; run `34252423032`; merge `606595e50f3057452714c50eb88e8178213ac5c8`.
- ACC-004 CHAMPION / CHALLENGER — COMPLETE. PR #71; run `34256093230`; merge `223bbd094e0ca8350f2673e94bec3d34a8836f87`.
- ACC-005 MARKET-DATA PROVENANCE — COMPLETE. PR #72; run `34256741680`; merge `bb4c0e4060bba067e5bee1a86f1247d30901d19e`.
- ACC-006 FORECAST DETERIORATION — COMPLETE. PR #73; run `34257098538`; merge `ad3973d01fe94d52010cdd6628d9f85a9dc23a3d`.
- ACC-007 ADVERSARIAL ROBUSTNESS — COMPLETE. PR #74; run `34257293281`; merge `76d83786acf132b6cc848dacf0edf17acba2ed77`.
- ACC-008 GENUINE FORWARD PROOF — COMPLETE. PR #75; run `34258912558`; merge `cf66104242467c8cf1177c91e20db206c92f62e5`. Exact fingerprint, >=20 independent 24h or >=12 7d, 3x modeled cost, positive after-cost expectancy, Wilson 95% lower >=50%, max forward DD <=12%, no deterioration.
- ACC-009 GLOBAL PORTFOLIO / EXECUTION RISK — COMPLETE. PR #76; run `34264596759`; merge `4f70e89f81b4f16df39d4fd2fe88b3c0f298d6f5`.
- ACC-010 SIZE-AWARE EXECUTION — COMPLETE. PR #77; run `34265226943`; merge `edbed73a7b4236234ea2ff958e94ca2510db2df1`.
- ACC-011 POINT-IN-TIME UNIVERSE / SURVIVORSHIP FIREWALL — COMPLETE. PR #79; run `34266482390`; merge `20c383c1dae1d2413c534b749b10faf95fb83f57`. Today’s survivors are not accepted as historical universe evidence.
- ACC-012 MULTIPLE-TESTING / FALSE-DISCOVERY FIREWALL — COMPLETE. PR #78; run `34265615227`; merge `8ddac654e63a70a95f811dd14777e649faefd625`.
- ACC-013 GENUINE-FORWARD SHADOW CHAMPION / CHALLENGER — COMPLETE. PR #80; run `34268140486`; merge `51db55b5339bcbd5183044a50521e6fe36770caa`.
- ACC-014 CHAOS / FAILURE FAIL-CLOSED GATES — COMPLETE. PR #81; run `34268401662`; merge `c91e337439782ac4b6c60a06a81aee5fb051ee29`.

## SAFE WORKER THROUGHPUT — COMPLETE
PR #82 passed exact-head run `34268787553` and merged as `3af7eba0488da8576382b8c480698826eefdff8d`.
- successful workers cycle at the configured fast rest interval;
- failing/timing-out workers use bounded exponential backoff;
- dedicated accuracy lane remains reserved for 24h/7d ACC-002 work;
- max heavy concurrency remains bounded; no paid capacity increase;
- all workers remain research-only.

## SHARED IMMUTABLE DEEP-HISTORY CACHE — COMPLETE
PR #83 passed exact-head run `34270418760` and merged as `593d2126edc8e754cced4df98a4e9cb6a9c3b07f`.
- process-local LRU then cross-process cache before OKX network fetch;
- exact request identity + bounded TTL bucket;
- same-bucket objects immutable;
- SHA-256 integrity + provenance;
- malformed, corrupt, wrong-key, future-dated or nonchronological objects rejected;
- atomic publication and conservative pruning;
- cache never changes chronology/OOS/forward-proof rules.

## RESEARCH OBSERVABILITY — COMPLETE
PR #84 passed exact-head run `34271387837` and merged as `dcaad1dc3edecbe04a4ce825c9e8966c79febc36`.
- cross-process cache hit/miss/rejection counts and cache-read p50/p95;
- worker completed/failed/timeout counts and failure rate;
- latest ACC-002 24h/7d evidence summaries and worker elapsed time;
- metrics are read-only and hard-code trade/signal/promotion authority false;
- detailed application endpoint remains protected by the existing scan secret.

## EXACT DEEP-HISTORY NETWORK LATENCY — COMPLETE
PR #85 passed exact-head run `34273647346` on `dab29b5993fd35a9e5b4ba3fe2ae51a3595f2988` and merged as `774a335402ca481eb35ecc75c180963c670d5032`.
- `get_history()` measures actual OKX `/api/v5/market/history-candles` request time on cache misses;
- paginated network durations are summed;
- cache time, normalization, writes and intentional pagination sleeps are excluded;
- internal retry/backoff time remains visible;
- fetch count/failures/request count/rows/mean/p50/p95 are recorded;
- failed fetches are recorded before the original exception is re-raised.

## PRIVATE RENDER OBSERVABILITY LOGGING — COMPLETE
PR #86 `Log private research observability summaries` passed exact-head Security and Reliability run `34274577191` on `f23b14298056a991dade1921646e10dd3bba32bb` and merged as `0213cd2ffabeb03a800e4078bb64d880662744fe`.
PR #87 fixed Render/Uvicorn logger routing; exact-head Security and Reliability run `34274827705` on `47722a0d986c3ff850408782e739358fa48866d1` passed and merged as `8070d434aeb42f82f623fb22a46244079332f01c`.

Private coordinator logs now expose only a bounded non-sensitive summary: cache hit/rejection and p50/p95, exact history-network p50/p95 and fetch counts, worker failure/timeout health, worker elapsed time, and three ACC-002 gate booleans. Raw research evidence/arrays and secrets are not logged. Trade/signal/promotion authority remains false.

Initial live observation immediately after the PR #87 restart showed `cache_reads=0`, `history_fetches=0`, `worker_completed=0`, `worker_failed=0`, `worker_timeouts=0`. This is startup-only and is NOT sufficient evidence to identify a bottleneck. Render resource telemetry showed the coordinator instance live with CPU/memory activity, so the service was active rather than crashed. Do not optimize from the zero-sample startup snapshot.

## AUTHENTIC PAPER TRADING STATE
The continuous paper account remains forward-only and broker-disconnected. Authentic baseline is exactly `$100,000` from `2026-09-08T01:17:49Z`; never reset or rewrite it. Current account value = immutable starting capital plus realized/open P&L. Safety/execution gates may reject entries but never fabricate or reset history. Paper performance is evidence only.

## COST / SPEED POLICY
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed. Prefer existing shared Render compute, deterministic Python, public/free defensible data, caching/reuse, early rejection and bounded concurrency. No paid feed/service/compute without approval.

## SPEED WITHOUT CHEATING
Preserve stable exact strategy fingerprints while genuine forward observations accumulate. Challengers may run in shadow. Never count overlapping forecasts as independent, lower forward-proof thresholds, reset paper history, raise heavy concurrency, stretch cache TTLs, or change market-data source behavior merely to accelerate results.

## EXACT NEXT STEP
1. Continue genuine ACC-002 24h/7d forward/OOS evidence and worker-health monitoring. No profitability claim unless evidence genuinely passes.
2. Wait for non-zero private runtime observability samples after the current restart, then compare exact history-network p50/p95 against ACC-002 worker elapsed time and cache hit rate.
3. Do not classify network retrieval as the bottleneck until multiple completed worker/fetch observations exist; the startup-zero snapshot is insufficient.
4. If network history retrieval is a dominant share of worker runtime, optimize proven request duplication/batching/source behavior conservatively; do not raise concurrency or stretch TTLs by guesswork.
5. If network time is not dominant, investigate CPU/backtest/panel construction or scheduling next.
6. Preserve stable exact champion fingerprints while challengers run in shadow; only evidence-backed changes create a new fingerprint.
7. Preserve empty `live_promotions.json`, unused signing keys, PONS fail-closed behavior, immutable $100k paper ledger and broker-disconnected state.
8. Only add microstructure features when genuine timestamped data supports them; never reconstruct unavailable order books/liquidations from candles.
9. Optimize after-cost risk-adjusted realized performance with tail protection and abstention, not headline accuracy.
10. Update this file after every completed integration cycle.
