# AI DEVELOPMENT STATE
Last updated: 2026-09-08

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file from `main` before development. Never infer project state from ChatGPT memory. Update this file on `main` after every completed development/integration cycle.

## CURRENT ARCHITECTURE
Production: GitHub -> Render -> Python/FastAPI V3 -> Supabase. Production scans run about every 15 minutes and produce separate 24h/7d Top-20 rankings. Cloud research/backtesting runs continuously through a bounded 17-worker Python army on the existing Render coordinator. PONS is included only when defensible public data supports it. Specialist development uses isolated branches and exact-head Security and Reliability success is required before merge.

## SAFETY INVARIANTS
No AI opinion, ranking score, evidence score, current order-book snapshot, paper P&L, ensemble weight, single OOS result, signed historical promotion, observability metric, supervisor status, diagnostic, incident fingerprint, or risk-gate result by itself may authorize live BUY/SELL.

Mandatory chain:
RESEARCH -> BACKTEST -> VALIDATION -> UNTOUCHED OOS -> ROBUSTNESS/STABILITY -> MULTIPLE-TESTING FIREWALL -> POINT-IN-TIME UNIVERSE SAFETY -> STRATEGY-REGISTRY APPROVAL -> PRODUCTION-RISK APPROVAL -> GENUINE FORWARD PROOF -> GLOBAL/EXECUTION RISK CLEAR -> LIVE BUY/SELL.

Every later stage is restrictive-only. Missing, stale, contradictory, deteriorating, malformed, overlapping-only, insufficient, illiquid, execution-unsafe, portfolio-unsafe, statistically search-breadth-weak, survivorship-unsafe, or system-unsafe evidence means `WAIT / NO TRADE / RESEARCH_ONLY`.

`live_promotions.json` remains intentionally empty. Signing keys remain unused. Broker remains disconnected.

## VALIDATION / CALIBRATION
Chronological validation remains train / validation / untouched holdout. Robustness includes deterministic bootstrap/Monte Carlo resampling, parameter perturbation, regime stability, conservative execution-cost stress and false-discovery/search-breadth penalties. Prediction ledger is append-only with fixed `due_at`; forward proof counts only non-overlapping full-horizon resolved forecasts for the exact immutable strategy fingerprint. Calibration, deterioration, observability, worker supervision and diagnostics can only restrict or inform research operations; none can authorize trading.

## ACCURACY PROGRAM STATUS
- ACC-001 MARKET / EXECUTION REALISM — COMPLETE. PRs #38-#44 and follow-ons.
- ACC-002 CROSS-ASSET RANK RESEARCH — IN PROGRESS. PRs #56-#60 and #64-#68: cross-sectional relative strength, multi-lookback vol-normalized momentum, train/validation/untouched OOS, purging, non-overlapping observations, fixed predeclared grids, Top-15/30/45 liquidity stability, 1x/1.5x/2x/3x cost stress, deterministic 500-resample bootstrap, dedicated 24h/7d workers. No profitability claim authorized yet.
- ACC-003 REGIME GATING — COMPLETE. PR #70; run `34252423032`; merge `606595e50f3057452714c50eb88e8178213ac5c8`.
- ACC-004 CHAMPION / CHALLENGER — COMPLETE. PR #71; run `34256093230`; merge `223bbd094e0ca8350f2673e94bec3d34a8836f87`.
- ACC-005 MARKET-DATA PROVENANCE — COMPLETE. PR #72; run `34256741680`; merge `bb4c0e4060bba067e5bee1a86f1247d30901d19e`.
- ACC-006 FORECAST DETERIORATION — COMPLETE. PR #73; run `34257098538`; merge `ad3973d01fe94d52010cdd6628d9f85a9dc23a3d`.
- ACC-007 ADVERSARIAL ROBUSTNESS — COMPLETE. PR #74; run `34257293281`; merge `76d83786acf132b6cc848dacf0edf17acba2ed77`.
- ACC-008 GENUINE FORWARD PROOF — COMPLETE. PR #75; run `34258912558`; merge `cf66104242467c8cf1177c91e20db206c92f62e5`. Exact fingerprint, >=20 independent 24h or >=12 7d, 3x modeled cost, positive after-cost expectancy, Wilson 95% lower >=50%, max forward DD <=12%, no deterioration.
- ACC-009 GLOBAL PORTFOLIO / EXECUTION RISK — COMPLETE. PR #76; run `34264596759`; merge `4f70e89f81b4f16df39d4fd2fe88b3c0f298d6f5`.
- ACC-010 SIZE-AWARE EXECUTION — COMPLETE. PR #77; run `34265226943`; merge `edbed73a7b4236234ea2ff958e94ca2510db2df1`.
- ACC-011 POINT-IN-TIME UNIVERSE / SURVIVORSHIP FIREWALL — COMPLETE. PR #79; run `34266482390`; merge `20c383c1dae1d2413c534b749b10faf95fb83f57`.
- ACC-012 MULTIPLE-TESTING / FALSE-DISCOVERY FIREWALL — COMPLETE. PR #78; run `34265615227`; merge `8ddac654e63a70a95f811dd14777e649faefd625`.
- ACC-013 GENUINE-FORWARD SHADOW CHAMPION / CHALLENGER — COMPLETE. PR #80; run `34268140486`; merge `51db55b5339bcbd5183044a50521e6fe36770caa`.
- ACC-014 CHAOS / FAILURE FAIL-CLOSED GATES — COMPLETE. PR #81; run `34268401662`; merge `c91e337439782ac4b6c60a06a81aee5fb051ee29`.

## SAFE WORKER THROUGHPUT — COMPLETE
PR #82; exact-head run `34268787553`; merge `3af7eba0488da8576382b8c480698826eefdff8d`.
- successful workers cycle at configured fast rest interval;
- failing/timing-out workers use bounded exponential backoff;
- dedicated accuracy lane remains reserved for ACC-002 24h/7d;
- heavy concurrency remains bounded under the $30/month ceiling;
- all workers remain research-only.

## SHARED IMMUTABLE DEEP-HISTORY CACHE — COMPLETE
PR #83; exact-head run `34270418760`; merge `593d2126edc8e754cced4df98a4e9cb6a9c3b07f`.
Process-local LRU then cross-process immutable cache before OKX network fetch; exact request identity, bounded TTL bucket, SHA-256 integrity/provenance, invalid/future/nonchronological cache rejection, atomic publication and conservative pruning. Cache never changes chronology/OOS/forward-proof rules.

## RESEARCH OBSERVABILITY — COMPLETE
PR #84; exact-head run `34271387837`; merge `dcaad1dc3edecbe04a4ce825c9e8966c79febc36`.
Cross-process cache hit/miss/rejection and p50/p95, worker completed/failed/timeout/failure rate, ACC-002 24h/7d summaries and elapsed time. Metrics are read-only with trade/signal/promotion authority false.

## EXACT DEEP-HISTORY NETWORK LATENCY — COMPLETE
PR #85; exact-head run `34273647346` on `dab29b5993fd35a9e5b4ba3fe2ae51a3595f2988`; merge `774a335402ca481eb35ecc75c180963c670d5032`.
Measures actual OKX `/api/v5/market/history-candles` request time on cache misses, excluding cache time, normalization, writes and intentional pagination sleeps; retry/backoff remains visible. Fetch count/failure/request count/rows/mean/p50/p95 are recorded.

## PRIVATE RENDER OBSERVABILITY LOGGING — COMPLETE
PR #86 exact-head run `34274577191`; merge `0213cd2ffabeb03a800e4078bb64d880662744fe`. PR #87 exact-head run `34274827705`; merge `8070d434aeb42f82f623fb22a46244079332f01c`.
Private Render logs expose bounded non-sensitive cache/network/worker/ACC-002/supervisor summaries. Raw research arrays and secrets are not logged. Authority remains false.

## SELF-HEALING 24/7 WORKER SUPERVISOR — COMPLETE
PR #88 `Add self-healing supervision for 24/7 research workers`; exact-head Security and Reliability run `34275821381` on `f11389cdd47175019e2dd6d8e397115ae66c73c9`; squash merge `f02d91edb458cacb5be02fba4325555f381f7123`.
- bounded heartbeats during computing and rest/backoff;
- stale/crashed logical worker detection;
- unexpected logical-worker exits are fingerprinted and recreated after bounded delay;
- restart cannot increase heavy concurrency;
- runtime failure categories: timeout, network/exchange, malformed/invalid evidence, resource/runtime, generic process failure;
- coordinator health fails closed on supervisor health;
- supervisor/incident data have trade/promotion/write authority false.

## PRIVACY-PRESERVING WORKER FAILURE DIAGNOSTICS / DURABLE BUG LEDGER — COMPLETE
PR #89 `Capture private worker failure diagnostics` passed exact-head Security and Reliability run `34277010057` on `3f0aed2f1d056dfe34d27a1afa90f0af0d1ac6b6` and was squash-merged as `edef2386262459935987249cb7a6414bd721dbfe`.
- failed subprocess stderr is captured only into that job's temporary directory instead of being discarded;
- only a bounded tail is read after non-zero exit;
- common bearer-token/API-key/token/secret/password/JWT/OpenAI-key forms are redacted before storage/logging;
- final traceback exception type is inferred where possible;
- incident fingerprints include a deterministic diagnostic fingerprint;
- sanitized traceback detail is private; public worker/coordinator snapshots never expose diagnostic text;
- `BUG_REGRESSION_LEDGER.md` is durable defect history separate from ephemeral runtime incidents.

## ACC-002 EXPECTED RESEARCH-BLOCKED OUTCOME — COMPLETE
PR #90 `Classify insufficient ACC-002 evidence as research blocked` passed exact-head Security and Reliability run `34286298608` on `073683edea01168012ab2ece5f31131355dcbc9e` and was squash-merged as `220452eca6242999cac7381bb9a37c77354b710a`.
Fresh post-PR-89 diagnostics proved the recurring 24h/7d exit-code-1 was not a strategy or runtime crash: public cross-exchange / historical availability sometimes resolved fewer than the required predeclared liquidity subsets, correctly triggering the ACC-002 fail-closed liquidity-stability gate. The runner now emits a sealed `research_blocked` artifact with reason `insufficient_supported_liquidity_subsets`, no OOS opening, no promotion eligibility, `live_approved=false`, and `trade_authority=false`, instead of raising a worker-crash `ValueError`. No evidence threshold or safety gate was weakened. `BUG_REGRESSION_LEDGER.md` records `ACC002-BLOCK-001`; `tests/test_cross_asset_research_blocked.py` permanently reproduces the case.

## AUTHENTIC PAPER TRADING STATE
The continuous paper account remains forward-only and broker-disconnected. Authentic baseline is exactly `$100,000` from `2026-09-08T01:17:49Z`; never reset or rewrite it. Current account value = immutable starting capital plus realized/open P&L. Safety/execution gates may reject entries but never fabricate or reset history. Paper performance is evidence only.

## COST / SPEED POLICY
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed. Prefer existing shared Render compute, deterministic Python, public/free defensible data, caching/reuse, early rejection and bounded concurrency. No paid feed/service/compute without approval.

## SPEED WITHOUT CHEATING
Preserve stable exact strategy fingerprints while genuine forward observations accumulate. Challengers may run in shadow. Never count overlapping forecasts as independent, lower forward-proof thresholds, reset paper history, raise heavy concurrency, stretch cache TTLs, or change market-data source behavior merely to accelerate results.

## EXACT NEXT STEP
1. Verify the PR #90 auto-deploy reaches live and confirm fresh ACC-002 24h/7d cycles report `research_blocked` as a normal completed research outcome rather than incrementing worker failure counts.
2. Continue genuine ACC-002 24h/7d forward/OOS evidence and worker-health monitoring. No profitability claim unless evidence genuinely passes.
3. Investigate any remaining recurring non-ACC-002 worker failures from fresh sanitized diagnostics. PONS had isolated opaque exit-code-1 events with no stderr; if it recurs, capture enough bounded non-sensitive evidence to distinguish expected unavailable-data/research-blocked behavior from a true code defect, then fix only the proven defect with a permanent regression test.
4. Verify supervisor remains healthy in live Render logs: no stale workers, no restart loop, heartbeats continue through long jobs.
5. Use non-zero cache/network/worker samples to identify the proven throughput bottleneck; do not optimize from startup-zero samples.
6. Next larger reliability upgrade after current failure cleanup: deployment-canary/controlled rollback decision layer. Do not give research workers repository-write/merge authority.
7. Preserve stable exact champion fingerprints while challengers run in shadow; only evidence-backed changes create a new fingerprint.
8. Preserve empty `live_promotions.json`, unused signing keys, PONS fail-closed behavior, immutable $100k paper ledger and broker-disconnected state.
9. Only add microstructure features when genuine timestamped data supports them; never reconstruct unavailable order books/liquidations from candles.
10. Optimize after-cost risk-adjusted realized performance with tail protection and abstention, not headline accuracy.
