# AI DEVELOPMENT STATE
Last updated: 2026-09-08

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file from `main` before development. Never infer project state from ChatGPT memory. Update this file on `main` after every completed development/integration cycle.

## CURRENT ARCHITECTURE
Production: GitHub -> Render -> Python/FastAPI V3 -> Supabase. Production scans run about every 15 minutes and produce separate 24h/7d Top-20 rankings. Cloud research/backtesting runs continuously through a bounded 17-worker Python army on the existing Render coordinator. PONS is included only when defensible public data supports it. Specialist development uses isolated branches and exact-head Security and Reliability success is required before merge.

## SAFETY INVARIANTS
No AI opinion, ranking score, evidence score, current order-book snapshot, paper P&L, ensemble weight, single OOS result, signed historical promotion, observability metric, supervisor status, diagnostic, incident fingerprint, canary result, or risk-gate result by itself may authorize live BUY/SELL.

Mandatory chain:
RESEARCH -> BACKTEST -> VALIDATION -> UNTOUCHED OOS -> ROBUSTNESS/STABILITY -> MULTIPLE-TESTING FIREWALL -> POINT-IN-TIME UNIVERSE SAFETY -> STRATEGY-REGISTRY APPROVAL -> PRODUCTION-RISK APPROVAL -> GENUINE FORWARD PROOF -> GLOBAL/EXECUTION RISK CLEAR -> LIVE BUY/SELL.

Every later stage is restrictive-only. Missing, stale, contradictory, deteriorating, malformed, overlapping-only, insufficient, illiquid, execution-unsafe, portfolio-unsafe, statistically search-breadth-weak, survivorship-unsafe, or system-unsafe evidence means `WAIT / NO TRADE / RESEARCH_ONLY`.

`live_promotions.json` remains intentionally empty. Signing keys remain unused. Broker remains disconnected.

## VALIDATION / CALIBRATION
Chronological validation remains train / validation / untouched holdout. Robustness includes deterministic bootstrap/Monte Carlo resampling, parameter perturbation, regime stability, conservative execution-cost stress and false-discovery/search-breadth penalties. Prediction ledger is append-only with fixed `due_at`; forward proof counts only non-overlapping full-horizon resolved forecasts for the exact immutable strategy fingerprint. Calibration, deterioration, observability, worker supervision, diagnostics and deployment canary signals can only restrict or inform operations; none can authorize trading.

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

## PR #90 LIVE VERIFICATION — COMPLETE
Fresh Render instance `srv-dafgtead0e5s73cc7ekg-6svgk` confirmed the post-PR-90 deploy is live. ACC-002 24h completed with exit 0, then ACC-002 7d completed with exit 0; subsequent cycles continued exiting 0. Worker failure count remained 0 until an independent PONS failure occurred. Supervisor stayed healthy with no stale workers, no crashed workers and no task restarts. Cache hit rate rose above 90% after warmup, confirming non-zero runtime samples are now available for bottleneck analysis.

## PONS FAILURE DIAGNOSTIC GAP — COMPLETE
PR #91 `Capture PONS research failure diagnostics` passed exact-head Security and Reliability run `34288072983` on `6e901c1c5201ceec64e39c6378f330f09eb582b4` and was squash-merged as `fa5541ff3154da1be11c560008155c582b3de3ef`.
Fresh post-PR-90 production evidence showed `worker_failure worker=pons exit=1 ... diagnostic=<none>`. Root cause could not yet be identified because `research_runner.py` catches per-job exceptions and historically printed them only to stdout, while the worker army intentionally discards stdout and captures stderr on failure. PR #91 preserves fail-closed behavior and adds sanitized private stderr emission for caught research-job exceptions so the next PONS failure can expose a bounded root-cause diagnostic without leaking secrets. `BUG_REGRESSION_LEDGER.md` records `PONS-DIAG-001`; `tests/test_research_failure_diagnostic.py` permanently verifies stderr-only sanitized diagnostics. No strategy/evidence threshold, market-data policy, concurrency, paper ledger, broker connectivity, promotion authority or trade authority was changed.

## PONS EXPECTED INSUFFICIENT-HISTORY OUTCOME — COMPLETE
PR #92 `Classify PONS insufficient history as research blocked` passed exact-head Security and Reliability run `34289018995` on `c43eff90711d27a829163f83f1eeb244a14db174` and was squash-merged as `03fcf47c8745538bad76013ebec07ef8b439a917`.
Fresh post-PR-91 production diagnostics proved the PONS worker's recurring exit-code-1 was caused by insufficient public history: 15m returned `Need at least 1000 candles for walk-forward`; 1H and 4H returned `Not enough historical candles`. Only those two proven `RuntimeError` messages are now classified as `research_blocked` with reason `insufficient_historical_candles`. No candle minimum is lowered, no missing history is fabricated, and blocked items remain research-only with promotion/live/trade authority false. Unknown exceptions still fail and keep diagnostics. `BUG_REGRESSION_LEDGER.md` records `PONS-BLOCK-001`; `tests/test_research_insufficient_history_blocked.py` permanently verifies the fail-closed classification.

## DEPLOYMENT CANARY / CONTROLLED ROLLBACK DECISION LAYER — COMPLETE
PR #93 `Add deployment canary and rollback decision layer` passed exact-head Security and Reliability run `34289540726` on `1c088a372beef4fe2f9785a542ad320ac6aa3881` and was squash-merged as `62a7811cd004b7ec4441f6d749308fe55308e7a7`.
The coordinator now has a bounded warm-up canary that evaluates production/state checks, supervisor health, stale/crashed workers, task restarts, worker timeouts and sufficiently sampled worker failure rate. After the grace period, unhealthy evidence yields `rollback_recommended=true` and coordinator health fails closed. The canary exposes a read-only `/deployment-canary` view and private bounded logs. It has `automatic_rollback_authority=false`, `deployment_authority=false`, `repository_write_authority=false`, `trade_authority=false` and `promotion_authority=false`; therefore it recommends rollback but cannot mutate Render/GitHub or authorize trades. Regression coverage lives in `tests/test_deployment_canary.py`.

## DEEP-HISTORY TTL-BOUNDARY CACHE REUSE — COMPLETE
PR #94 passed exact-head Security and Reliability run `34290656077` on `6e54b4822fe4e606d0e3bf899dcf26337ccf7f98` and was squash-merged as `4e3e9bd2c13d4134fd8990a9a17496376f3bbe97`.
Still-fresh exact-request immutable history may be reused across one TTL bucket boundary only when actual age is strictly inside TTL and integrity/chronology checks pass. Corrupt current cache remains rejection and cannot silently fall back. This reduces redundant full deep-history refetches at bucket boundaries without stretching TTL, changing source behavior, chronology, OOS evidence, concurrency, or cost policy.

## KRAKEN BROKER-DISCONNECTED SHADOW EXECUTION — COMPLETE
PR #95 passed exact-head Security and Reliability run `34292185973` on `5134af4980f02586d72518c69761d63f61baa26d` and was squash-merged as `dd2ecd13ce5860f31a33580b890b56d39ca60f8d`.
Public timestamped Kraken order-book snapshots can now be walked for hypothetical visible-depth VWAP/slippage/fee-adjusted fills. Stale/future/malformed/insufficient-depth books fail closed; hidden liquidity is never extrapolated. The adapter has broker/order/trade authority false and contains no private credentials or order endpoints.

## PRODUCTION SCAN PERSISTENCE FAILURE DIAGNOSTICS — COMPLETE
PR #97 passed exact-head Security and Reliability run `34292801678` on `1e07b192ea619286113cf4df4161bdf1e4178165` and was squash-merged as `4a1f30beb42d1b2f64b7956ad8404e5ff400b6ea`.
GitHub Crypto 15m Scan run `34292249175` showed a transient Render HTTP 502 followed by a completed scan response that failed validation because opportunity persistence failed. The pre-fix response exposed only a generic failure to the workflow, preventing safe root-cause classification. The engine now preserves failure semantics while emitting only exception type plus deterministic component/type fingerprint, keeps raw exception detail redacted, and logs the full traceback server-side. No persistence failure is ignored or marked healthy; trade/promotion authority remains false.

## PREDICTION-LEDGER PRODUCTION SCHEMA DRIFT FIX — COMPLETE
Fresh post-PR #97 Render evidence identified the exact root cause: `fetch_resolved_predictions()` requested nonexistent `prediction_ledger.created_at`, producing Supabase SQLSTATE `42703` and blocking opportunity persistence. PR #98 removed only that nonexistent field from resolved/shadow prediction SELECT lists, preserving `due_at`/`resolved_at` chronology and all forward/OOS logic. Regression tests lock the production-compatible query shape and ordering. Exact-head Security and Reliability run `34293217999` passed on `19218735fe4a5fed1147a0f12ac808dc7ca238d1`; squash merge `f2c5dcaf2e83d97973e161d7f54e121b9060183b`. No schema mutation, history reset, validation threshold, trade authority, broker connectivity, or promotion behavior changed.

## AUTHENTIC PAPER TRADING STATE
The continuous paper account remains forward-only and broker-disconnected. Authentic baseline is exactly `$100,000` from `2026-09-08T01:17:49Z`; never reset or rewrite it. Current account value = immutable starting capital plus realized/open P&L. Safety/execution gates may reject entries but never fabricate or reset history. Paper performance is evidence only.

## COST / SPEED POLICY
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed. Prefer existing shared Render compute, deterministic Python, public/free defensible data, caching/reuse, early rejection and bounded concurrency. No paid feed/service/compute without approval.

## SPEED WITHOUT CHEATING
Preserve stable exact strategy fingerprints while genuine forward observations accumulate. Challengers may run in shadow. Never count overlapping forecasts as independent, lower forward-proof thresholds, reset paper history, raise heavy concurrency, stretch cache TTLs, or change market-data source behavior merely to accelerate results.

## EXACT NEXT STEP
1. Verify PR #98 auto-deploy is live and confirm a fresh Crypto 15m Scan no longer fails on `prediction_ledger.created_at`; if another persistence failure appears, diagnose the new exact root cause rather than masking it.
2. Re-evaluate open PR #96 against the new `main` after PRs #97/#98; refresh/retest exact head if necessary before merge. Its selective-precision analysis remains research-only and must not select thresholds from forward/untouched outcomes to authorize trades.
3. Continue genuine ACC-002 24h/7d forward/OOS evidence and worker-health monitoring. No profitability or accuracy-improvement claim unless genuine evidence passes.
4. Confirm a fresh PONS cycle after PR #92 completes without incrementing worker failures while insufficient public history remains explicitly research-blocked; do not fabricate or lower history requirements.
5. Verify supervisor/canary remain healthy in live Render logs: no stale/crashed workers, restart loop, timeout spike, or rollback recommendation without proven unhealthy evidence.
6. Compare post-PR #94 non-zero cache/history metrics; optimize only proven cold/deep-history inefficiency without changing chronology, market-data source behavior, evidence requirements, or the $30/month ceiling.
7. Extend Kraken readiness only with broker-disconnected public-data shadow execution/reconciliation until genuine forward proof and all canonical approval gates pass; no credentials or real orders yet.
8. Preserve stable exact champion fingerprints while challengers run in shadow; only evidence-backed changes create a new fingerprint.
9. Preserve empty `live_promotions.json`, unused signing keys, PONS fail-closed behavior, immutable $100k paper ledger and broker-disconnected state.
10. Only add microstructure features when genuine timestamped data supports them; never reconstruct unavailable order books/liquidations from candles.
11. Optimize after-cost risk-adjusted realized performance with tail protection and abstention, not headline accuracy.