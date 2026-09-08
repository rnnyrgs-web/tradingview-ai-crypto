# AI DEVELOPMENT STATE
Last updated: 2026-09-08

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file in full before development. Never infer project state from ChatGPT memory. Update this file on `main` after every completed development/integration cycle.

## CURRENT ARCHITECTURE
Production: GitHub -> Render -> Python/FastAPI V3 -> Supabase. Production scans run about every 15 minutes and produce separate 24h/7d Top-20 rankings. Cloud research/backtesting runs hourly 24/7. Intraday research targets Top-80 liquid OKX markets on 15m + 1H, with PONS forcibly included as `PONS-USDT-SWAP`; swing research uses 4H + 1D.

There are 15 autonomous development roles: Lead Integrator plus 14 specialists. Each specialist cycle permits exactly one CHANGE role plus thirteen read-only AUDIT roles. Specialists use isolated branches and cannot write `main` or protected orchestration/state paths. Verified integration requires exact-SHA Security and Reliability success, independent Security AI + Lead AI approval where autonomous integration is used, bounded/protected-path checks, final tests, and this canonical state update.

## SAFETY INVARIANTS
No AI opinion, ranking score, evidence score, live order-book snapshot or single OOS result may authorize live BUY/SELL. Mandatory chain:
RESEARCH -> BACKTEST -> VALIDATION -> UNTOUCHED OOS -> ROBUSTNESS/STABILITY -> STRATEGY-REGISTRY APPROVAL -> PRODUCTION-RISK APPROVAL -> LIVE BUY/SELL.
Missing/unreliable evidence means `WAIT / NO TRADE / RESEARCH_ONLY`.

`live_promotions.json` remains intentionally empty. Strategy identity binds symbol, horizon, family, required timeframes, strategy version, modeled cost and implementation SHA-256. Promotion requires >=3 distinct sealed research artifacts plus independent Strategy Registry + Production Risk HMAC-SHA256 attestations. Signing keys remain unused until genuine evidence is complete.

## VALIDATION / CALIBRATION
Chronological validation remains 60% train / 20% validation / 20% untouched holdout. Robustness uses 500 seeded bootstrap/Monte Carlo resamples, parameter perturbations, multi-regime holdout testing and realistic costs. Only all-pass candidates become `ROBUST_OOS`, still research-only. Research artifacts are SHA-256 sealed and three distinct sealed robust runs are required before `READY_FOR_STRATEGY_REGISTRY_REVIEW`.

Prediction ledger is append-only with fixed `due_at`. Outcomes use the first hourly close at/after deadline. Calibration is horizon + score-bin specific, requires >=30 comparable resolved forecasts and 95% Wilson lower bound >=50%, and can only restrict.

## ACC-001 MARKET / EXECUTION REALISM — COMPLETE
Integrated evidence:
- PR #38 merged `18a12236270cc753dfa703b21b51e647edebdd0b`: deterministic 1.0x/1.5x/2.0x/3.0x execution-cost stress on full and untouched-holdout paths.
- Event-driven candidate `aa26b262e1846ec8f6b19f89ef246c1455f05e5b` integrated as `3ee439912b7dcf91efd9a9891e40c39649820c91`: fail-closed strict timestamp ordering; missing/duplicate/non-increasing timestamps refuse backtest/walk-forward.
- PR #39 merged `2e71fd84446a5a527ca82999b15a4b182c236cf4`: timestamp-safe OKX + Binance funding history and recent Binance USDⓈ-M OI history/change; two populated funding sources required for reliability.
- PR #41 merged `d48d627b6d51bdd7262a4707856e5c6fd9280827`: timestamp-safe historical OKX mark-vs-index basis using exact shared timestamps only; no interpolation.
- PR #42 merged `f6f0e2df83ed7e6d593a2cf3cc99b22809a90cf1`: research-only current-book fill/slippage simulation for ~1k/5k/10k quote notionals, visible-depth-only VWAP/slippage/coverage/partial-fill evidence, and defensible raw liquidation pressure units with no false USD notional.
- PR #43 `Add untouched OOS execution robustness evidence` passed Security and Reliability run `34168441761` and merged as `dbefac4bbc9a145e18d6b871b4edb93cf73a0976`.
- PR #44 `Accelerate cloud research without weakening gates` passed Security and Reliability run `34170047571` and merged as `442b93e864682326195a3ae6c799fc231d43cbcd`.
- Replacement research artifacts were inspected: 177/177 execution-OOS records were valid/research-only, 23 unique symbol/timeframe paths remained positive under maximum conservative execution stress, and independent adversarial audit reported zero failures. Repeated-run aggregation advanced only `ARB-USDT 15m trend`, `DOOD-USDT 15m breakout`, and `DOOD-USDT 15m momentum` to `READY_FOR_STRATEGY_REGISTRY_REVIEW`; all remain `live_approved=false`.
- ACC-001 is complete. This is screening evidence, not a profitability claim and grants no live authority.

## 24/7 AI / ORCHESTRATION
Token-free Render coordinator checks production health/state every minute with no trade/write/promotion authority.

`continuous_ai_agent.py` runs inside production every five minutes by default, read-only, with `trade_authority=false`, `write_authority=false`, `promotion_authority=false`. PR #40 merged `3e26d60bdf812564203be61df842b7e3456fcf36`; OpenAI requests have bounded timeout and zero SDK retries. The first post-PR #46 restart call was rate-limited, so current live-cycle health still requires direct recheck before claiming healthy AI cycles.

Event-driven supervisor from PR #37 wakes on completed production scan/cloud research plus hourly fallback, provides compact supervisor context and allows exactly one CHANGE + thirteen AUDIT workers with max-parallel 14. The one-writer/thirteen-auditor path has been verified end-to-end.

PR #55 `Add bounded 24/7 Python research worker army` passed exact-head Security and Reliability run `34180983272` and was squash-merged as `10416b2ef89f54b46632aeabb49968edbb6d8c67`.
- Existing paid Render Starter coordinator hosts persistent logical Python research loops on the same single paid service; no additional paid Render service was created.
- Worker coverage includes BTC, ETH, SOL, XRP, LINK, PONS, eight liquid-universe shards, major swing research, and a dedicated ACC-002 cross-asset worker.
- Heavy subprocess concurrency is hard-bounded to 2 by default and at most 4, with staggered starts, timeouts, temp working directories, and short rest/backoff loops.
- Normal worker-army operation uses deterministic Python and public market-data calls, not OpenAI API calls.
- Worker army is hard-coded research-only: `trade_authority=false`, `write_authority=false`, `promotion_authority=false`, `broker_connected=false`.
- Cost policy: recurring infrastructure hard ceiling USD 30/month. Prefer one shared paid machine, bounded concurrency, free/public data, deterministic Python, caching/reuse and included/free GitHub-hosted research. Do not add another paid service or paid data/API dependency without explicit user approval.

## ACC-002 CROSS-ASSET RANK RESEARCH — IN PROGRESS
- PR #56 `ACC-002: Add nonstop cross-asset rank research` passed exact-head Security and Reliability run `34181843712` on `95976e1c05dd67f84f2a1c31b67ee58b155ceab7` and was squash-merged as `b0524525c48cd92639839e1324914e2d226c3780`.
  - Added timestamp-safe cross-sectional relative-strength ranking over a liquid crypto universe.
  - Uses multi-lookback momentum normalized by realized volatility, chronological train/validation/untouched OOS segmentation, Spearman rank IC, and after-cost top-minus-bottom spread metrics.
  - Added a dedicated nonstop ACC-002 research worker on the existing paid Render coordinator.
- PR #57 `ACC-002: Purge split leakage and stress execution costs` passed exact-head Security and Reliability run `34182015157` on `7dfb7cce0182649e52b44bf5bf4243f6c54ee0e8` and was squash-merged as `876b65135d54beba4771dcec8ce6dc4da48f2a26`.
  - Purges split boundaries by the full forward horizon.
  - Uses non-overlapping forward-horizon observations by default.
  - Adds 1.0x/1.5x/2.0x/3.0x execution-cost stress.
- PR #58 `ACC-002: Enforce enough history for independent OOS evidence` passed Security and Reliability run `34182218869` on `6d4056bfeaf0f5398e9bd7b835216b1d30135c43` and was squash-merged as `f2fa7d61092f499a3906cbeabd1b1284a4428824`.
  - Default 24h/1H worker depth increased to 3000 bars.
  - Runner automatically requires enough history for >=20 independent untouched-OOS observations; unsupported long horizons fail closed and require a coarser bar interval.
- PR #59 `ACC-002: Preselect candidates before opening untouched OOS` passed Security and Reliability run `34182413741` on `5b8d265c707cd549ad174be1cc242f8eb9489cf6` and was squash-merged as `6d72741b0808ad756061309ba422389fcb7bea12`.
  - Uses a small fixed lookback grid declared before OOS: `(4,16,64)`, `(6,24,72)`, `(8,32,96)`.
  - Candidate selection uses train+validation only and requires both splits to survive 3x cost stress.
  - Untouched OOS is opened for at most one preselected candidate; if no candidate passes pre-OOS gates, the holdout is not opened.
- PR #60 `ACC-002: Require parameter stability and bootstrap confidence` passed exact-head Security and Reliability run `34182666817` on `8f168e76537b40572a36c1328de7082f756c00a0` and was squash-merged as `b1486463506912a24afe185353354a7220a12592`.
  - Requires at least 2 of the 3 nearby lookback configurations to independently survive train+validation and 3x cost stress before any untouched OOS is opened.
  - The selected untouched OOS receives 500 deterministic seeded bootstrap resamples.
  - ACC-002 research pass requires positive 95% bootstrap lower bounds for both mean rank IC and maximum-cost net top-minus-bottom spread, in addition to the existing sample/count/positive-spread gates.
  - First implementation triggered Bandit B311 for seeded `random.Random`; it was replaced with deterministic SHA-256 index sampling and the final exact-head Security and Reliability run passed all unit, dependency, static-security and secret checks.
- PR #64 `ACC-002: Require liquidity-subset stability` passed exact-head Security and Reliability run `34236350206` on `8a477b4159a3e14f8b0fe59e517bc206f4ba8eb9` and was squash-merged as `6d56244fa9bf7afd797e56aed90be809fca81cc6`.
  - Adds predeclared Top-15/Top-30/Top-45 liquidity-universe stability using train+validation only.
  - A candidate must survive at least two supported liquidity subsets before any untouched OOS is opened.
  - Lower-ranked assets are never substituted into a failed Top-N subset; each subset requires at least 80% of the requested Top-N histories to resolve.
  - Candidate selection uses the worst passing liquidity-subset score, and untouched OOS is opened exactly once on the largest supported subset so universe size is not selected on OOS.
  - The same fetched histories are reused across subsets to improve robustness without adding paid infrastructure.
  - Render production deploy `dep-dag1e1vavr4c73ckvq20` and coordinator deploy `dep-dag1e1vavr4c73ckvq80` both reached `live` for merge `6d56244fa9bf7afd797e56aed90be809fca81cc6`.
- PR #65 `ACC-002: Add 24h/7d horizon evidence workers` passed updated exact-head Security and Reliability run `34241508307` on `62967e4156b4265717e5a483a5d4d3f51b66ed4f` and was squash-merged as `3f18b03e4dc1187c51b1b0085bf176fffea45488`.
  - Replaces the single ACC-002 loop with dedicated nonstop 24h and 7d logical workers while retaining the existing maximum of two concurrent heavy subprocesses and the USD 30/month ceiling.
  - Uses predeclared 24h `1H/24-bar` and 7d `4H/42-bar` profiles. The 7d lookback grid is fixed before OOS and fits at least 20 independent non-overlapping untouched-OOS observations within the 5,000-bar cap.
  - Each successful worker run now preserves a bounded evidence summary in coordinator `/workers`: supported liquidity subsets, candidate train/validation stability, fixed selection, whether OOS opened, OOS sample count, rank IC, 3x-cost spread and both bootstrap lower bounds.
  - All evidence remains in-memory, research-only, broker-disconnected and without trade/write/promotion authority. A restart clears the displayed summary and requires a fresh genuine run.
- PR #66 `ACC-002: Reserve an accuracy research fast lane` passed exact-head Security and Reliability run `34242515398` on `bad6be9d67e4cc440560575b323d56fba8312461` and was squash-merged as `a668cb6ea978134956b699dbd0c1caa786a32cd1`.
  - Reserves one of the existing two heavy-worker slots for ACC-002 and one for general research. This prevents majors/PONS/universe jobs from delaying both 24h/7d evidence loops for many hours without adding infrastructure or weakening evidence gates.
  - Coordinator deploy `dep-dag294jbc2fs73dqak00` and production deploy `dep-dag294jbc2fs73dqajq0` reached `live`.
  - Live `/workers` verified 17 persistent logical workers, `max_concurrent=2`, `accuracy_reserved_slots=1`, the 24h ACC-002 worker running immediately, zero completed/failed jobs at startup, and all trade/write/promotion/broker authorities false.
  - Production `/health` was healthy with zero recent operational errors. Optional `continuous_ai` remained bounded/read-only but rate-limited; deterministic Python research is unaffected.
- PR #68 `Improve deep history fetch reliability` passed exact-head Security and Reliability run `34246946142` on `f07957f2120452eb80281c01bf5d2d1396542636` and was squash-merged as `2ab5dd9352717bce895821270340386030b82caa`.
  - Reproduced ACC-002 evidence generation was being blocked by transient OKX deep-history `ReadTimeout` failures.
  - Added bounded retries for transient timeout/network/429/5xx failures with exponential backoff.
  - Added bounded process-local reuse of identical deep-history datasets with defensive copies, reducing duplicate public-data calls inside a single research subprocess without adding paid infrastructure.
  - Coordinator deploy `dep-dag3gmu7bikc73alps30` and production deploy `dep-dag3gmu7bikc73alpr20` both reached `live` before the subsequent PR #69 deploy replaced them.
- All ACC-002 outputs remain `research_only=true`, `live_approved=false`, `trade_authority=false`. No profitability has been claimed yet; genuine live public-data evidence must be collected and inspected.

## ACC-003 REGIME-CONDITIONED STRATEGY GATING — COMPLETE
- PR #70 `ACC-003: Add causal regime-conditioned strategy gating` passed exact-head Security and Reliability run `34252423032` on `c192affed37965f75f0972b608b965ae7c40084e` and was squash-merged as `606595e50f3057452714c50eb88e8178213ac5c8`.
- Regime classification is causal/trailing-only and distinguishes `TREND_UP`, `TREND_DOWN`, `HIGH_VOL`, `COMPRESSION`, and `RANGE`.
- Strategy regime eligibility is frozen from train + validation before untouched holdout inspection. Holdout and robustness evidence are restricted to those preselected regimes, preventing a strategy from acquiring authority in market states where it did not demonstrate pre-OOS edge.
- Tests cover no-lookahead regime classification, trend direction, and rejection of unproven regimes.
- Existing OOS/robustness gates remain mandatory; all outputs remain research-only unless the full promotion chain passes.

## ACCURACY BACKLOG
1. `ACC-001` market-microstructure — COMPLETE.
2. `ACC-002` quant-cross-asset — IN PROGRESS; core rank engine, nonstop worker, purge/non-overlap, sufficient independent OOS depth, pre-OOS fixed-grid selection, parameter stability, liquidity-subset stability, 3x cost stress, 500-resample bootstrap confidence, dedicated 24h/7d workers, reserved accuracy capacity and bounded deep-history retry/cache reliability are integrated. Genuine live public-data evidence still needs collection/inspection and horizon robustness.
3. `ACC-003` quant-breakout-volatility / regime-conditioned gating — COMPLETE for causal regime classification and pre-OOS regime eligibility; further specialist models may be added only if they improve independent evidence.
4. `ACC-004` strategy-registry — calibrated champion/challenger ensemble weighting with correlation/deterioration penalties and automatic demotion.
5. `ACC-005` data-market — broader exchange/data coverage with provenance/freshness/contradiction checks and safe PONS handling.
6. `ACC-006` production-signals — continuous forecast scoring and deterioration detection from immutable prediction ledger.
7. `ACC-007` testing-security — expanded adversarial strategy-destruction tests across exchanges, periods, fees, slippage, parameters, malformed data and regimes.

## REAL-MONEY READINESS ACCELERATION
Master tracking issue #45 covers the safe acceleration program.
- PR #46 added forward shadow/canary readiness gates and remains read-only with `trade_authority=false` and `canary_execution_enabled=false`.
- PR #47 added compact crypto signal rows with one-click TradingView.
- PR #48 embedded signal levels directly on a TradingView-style chart.
- PR #49 added the persistent $100k continuous paper trading simulator, permanently research-only and broker-disconnected.
- PR #51 combined the paper portfolio and ranked signals on the main dashboard.
- PR #52 made paper trading forward-only and realistic. All legacy paper trades/equity were invalidated and account `default` reset at `2026-09-08T01:17:49Z` to exactly `$100,000` cash/equity, `$0` realized P&L, zero drawdown, zero trades and zero snapshots. Only forward trades opened after this reset count as authentic paper-performance evidence.
- PR #62 `Fix paper portfolio P&L reconciliation` passed exact-head Security and Reliability run `34235818721` on `3b3a45d52b2c08fce8fce84133f55eb41f08e95f` and was squash-merged as `50d086e7560887ea7d4034ccb5a48151982a1a5f`.
  - Fixed dashboard/accounting mismatch where open-position display double-counted entry friction relative to account equity.
  - Dashboard now reconciles `Total P&L = Realized P&L + Open P&L` and `Current Equity = Starting Capital + Total P&L` from the same live marks, with an explicit Open P&L card.
  - Production and coordinator Render deploys for the merge reached live before the subsequent PR #64 deploy replaced them.
- PR #69 `Preserve authentic paper trading ledger` passed Security and Reliability run `34251552315` on `3910c1126ed87be0e6fb113eb22e02bf9592301f` and was squash-merged as `15a48dda50fcdd34916c86f00fe021a07cc258a2`.
  - `initial_cash` can only be written at account creation, preserving the original `$100,000` baseline while Current Account Value moves with realized + open P&L.
  - Background/manual paper cycles are serialized and a close only credits cash/realized P&L when the persisted OPEN trade was actually claimed, preventing double-credit races.
  - Persisted paper account state now fails closed on a mutated starting balance or non-finite accounting fields.
  - The dashboard now foregrounds dynamic `Current Account Value` while retaining the original starting capital separately.
  - Coordinator deploy `dep-dag3hke7bikc73alr90g` and production deploy `dep-dag3hke7bikc73alr95g` both reached `live`.
- Future acceleration work remains subordinate to the mandatory research-to-live chain; speed must come from parallelism, caching, early rejection, prioritization, event-driven agents and deterministic automation, never weaker evidence.

## COST / SPEED POLICY
Hard infrastructure ceiling: USD 30/month unless the user explicitly changes it. Use the existing single paid Render worker/coordinator rather than multiplying paid machines. Default worker-army heavy concurrency is 2; raise only after measured capacity evidence and never by adding paid capacity without approval. Use deterministic Python for calculation/backtesting/filtering/evidence checks. Use free/public market data where defensible. Use AI only for bounded planning, hypothesis generation, implementation/review and orchestration. Prefer event-driven wakeups, caching/reuse, early rejection and read-only parallel audits over idle paid computation or competing writes.

## EXACT NEXT STEP
1. Implement `ACC-004`: calibrated champion/challenger ensemble weighting that uses only validated research evidence, penalizes correlated strategies and recent deterioration, and automatically demotes strategies when evidence weakens. It must not grant live authority by itself.
2. Inspect the first genuine post-PR-#68 24h and 7d ACC-002 public-data summaries from coordinator `/workers`. Report supported liquidity subsets, each candidate's train/validation stability, selected fixed candidate if any, whether untouched OOS was opened, OOS sample count, rank IC, 3x-cost top-minus-bottom spread and both bootstrap lower bounds. Do not claim profitability if either horizon gate fails or evidence is small.
3. Recheck that both accuracy workers continue cycling without repeated failure/timeout after the retry/cache fix and that the general lane gives every major/PONS/universe/swing worker bounded progress.
4. Recheck production `/health.continuous_ai`; require bounded timeout and all trade/write/promotion authorities false. Fix only bounded provider/cadence issues if rate limiting persists.
5. Tune worker scheduling for throughput-per-dollar: reuse/caching first, reject weak candidates early, retain majors/PONS/ACC-002 fast lanes, and avoid duplicate overlapping research between Render and GitHub Actions.
6. Investigate any repeated PONS worker failure and keep PONS research fail-closed if its public market/history data are insufficient or inconsistent.
7. Let the authentic `$100,000` forward-only paper account continue collecting post-reset trades without resetting or rewriting starting capital. Alert only when persisted `consistently_profitable` is genuinely satisfied.
8. Continue ACC-005 through ACC-007 after ACC-004, while non-owner specialists audit in parallel.
9. Keep `live_promotions.json` empty and signing keys unused until repeated backtests, untouched OOS, robustness/stability, Strategy Registry review and Production Risk review genuinely complete.
10. Update this file after every completed development/integration cycle.