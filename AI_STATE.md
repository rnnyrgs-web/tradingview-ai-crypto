# AI DEVELOPMENT STATE
Last updated: 2026-09-07

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

## ACC-001 MARKET / EXECUTION REALISM — IN PROGRESS
Integrated evidence:
- PR #38 merged `18a12236270cc753dfa703b21b51e647edebdd0b`: deterministic 1.0x/1.5x/2.0x/3.0x execution-cost stress on full and untouched-holdout paths.
- Event-driven candidate `aa26b262e1846ec8f6b19f89ef246c1455f05e5b` integrated as `3ee439912b7dcf91efd9a9891e40c39649820c91`: fail-closed strict timestamp ordering; missing/duplicate/non-increasing timestamps refuse backtest/walk-forward.
- PR #39 merged `2e71fd84446a5a527ca82999b15a4b182c236cf4`: timestamp-safe OKX + Binance funding history and recent Binance USDⓈ-M OI history/change; two populated funding sources required for reliability.
- PR #41 merged `d48d627b6d51bdd7262a4707856e5c6fd9280827`: timestamp-safe historical OKX mark-vs-index basis using exact shared timestamps only; no interpolation.
- PR #42 merged `f6f0e2df83ed7e6d593a2cf3cc99b22809a90cf1`: research-only current-book fill/slippage simulation for ~1k/5k/10k quote notionals, visible-depth-only VWAP/slippage/coverage/partial-fill evidence, and defensible raw liquidation pressure units with no false USD notional.
- PR #43 `Add untouched OOS execution robustness evidence` passed Security and Reliability run `34168441761` on final head `6eb5248189df9ecc53a2c590d58cdee20573639d` and merged as `dbefac4bbc9a145e18d6b871b4edb93cf73a0976`.
  - New `execution_oos.py` keeps threshold selection training-only, then rescored the same untouched 20% holdout trade path across deterministic cost stress.
  - A current OKX/Binance live-slippage snapshot may expand the conservative stress grid only when at least two reliable exchanges show complete fills at the requested notional (default 5k quote).
  - The worst observed one-way snapshot slippage is doubled into a current round-trip stress anchor; it is explicitly `historical=false` and never backfilled into historical timestamps.
  - `research_runner.py` now emits `execution_oos_robustness` in sealed cloud-research artifacts. This evidence is research-only and does not alter Strategy Registry eligibility, promotion gates or live authority.
  - Deterministic tests prove two-source/complete-fill requirements, conservative-only stress expansion, unchanged holdout path/threshold, and fail-closed behavior when no training threshold exists.
- While validating PR #43, Security exposed a pre-existing supervisor test regression caused by compacting the AI_STATE safety heading. Lead fixed `agents/supervisor_snapshot.py` directly on main as `e0a6d234d103e5415ba2342ab09d43d180357b02`; it now preserves safety context under both explicit and compact safety headings without weakening safeguards.
- Original Cloud Crypto Research run `34168479313` was cancelled before jobs/artifacts were produced, so it provides no ACC-001 evidence.
- PR #44 `Accelerate cloud research without weakening gates` passed exact-head Security and Reliability run `34170047571` on `7107d85f6a81ca21e2cc7e2371837094a10552b7` and merged as `442b93e864682326195a3ae6c799fc231d43cbcd`.
  - Cloud research concurrency is isolated by event/ref so stale feature-branch runs cannot block main research.
  - Broad-universe matrix parallelism increases from 8 to 16 when GitHub capacity is available.
  - Dedicated BTC/ETH/SOL/XRP/LINK fast-evidence workers run 15m + 1H in parallel while Top-80 + forced PONS research continues.
  - Expensive bootstrap/perturbation robustness is skipped only for candidates that already fail deterministic train/validation/untouched-OOS quality gates.
  - A separate adversarial artifact audit independently checks sealed integrity, fail-closed promotion, same-holdout execution policy and that live snapshot slippage is never represented as historical.
  - No OOS, robustness, promotion or live-authority gate was weakened.
- Merge `442b93e...` triggered Cloud Crypto Research run `34170631618`. The broad universe, swing research, fast-evidence jobs, independent adversarial artifact audit and repeated-run aggregation have now completed successfully and produced artifacts. Those artifacts still must be inspected for the actual execution OOS results before ACC-001 may be closed.

ACC-001 must NOT be called complete until run `34170631618` artifacts are inspected for real holdout/stress outcomes.

## 24/7 AI / ORCHESTRATION
Token-free Render coordinator checks production health/state every minute with no trade/write/promotion authority.

`continuous_ai_agent.py` runs inside production every five minutes by default, read-only, with `trade_authority=false`, `write_authority=false`, `promotion_authority=false`. PR #40 merged `3e26d60bdf812564203be61df842b7e3456fcf36`; OpenAI requests have bounded timeout (default 60s, clamped 10-240s), zero SDK retries and sanitized timeout state. Direct `/health.continuous_ai` evidence showing `cycle_count>=1` is still required before claiming full live-cycle verification.

Event-driven supervisor from PR #37 wakes on completed production scan/cloud research plus hourly fallback, provides compact supervisor context and allows exactly one CHANGE + thirteen AUDIT workers with max-parallel 14. The one-writer/thirteen-auditor path has been verified end-to-end.

## ACCURACY BACKLOG
1. `ACC-001` market-microstructure — IN PROGRESS; replacement accelerated cloud run finished successfully and artifact/result inspection is now pending.
2. `ACC-002` quant-cross-asset — cross-sectional relative-strength/rank prediction across liquid universe.
3. `ACC-003` quant-breakout-volatility — no-lookahead regime-specialist models for bull/bear/range/high-volatility/compression.
4. `ACC-004` strategy-registry — calibrated champion/challenger ensemble weighting with correlation/deterioration penalties and automatic demotion.
5. `ACC-005` data-market — broader exchange/data coverage with provenance/freshness/contradiction checks and safe PONS handling.
6. `ACC-006` production-signals — continuous forecast scoring and deterioration detection from immutable prediction ledger.
7. `ACC-007` testing-security — expanded adversarial strategy-destruction tests across exchanges, periods, fees, slippage, parameters, malformed data and regimes.

## REAL-MONEY READINESS ACCELERATION
Master tracking issue #45 covers the safe acceleration program.
- PR #44 is integrated: event/ref-isolated cloud concurrency, higher parallelism, liquid-major fast lane, deterministic early rejection and independent artifact audit.
- PR #46 `Add forward shadow and canary readiness gates` is open and remains unmerged pending exact-head verification/rebase after ACC-001 evidence work. It is designed to add read-only forward evidence, de-correlated prediction samples, Wilson/expectancy/drawdown checks and tiny-canary/scale review gates with `trade_authority=false` and `canary_execution_enabled=false`.
- PR #47 `Add compact crypto signal rows with one-click TradingView` passed Security and Reliability run `34172595104` on exact head `975734cc4c164754ab94ad22ae6d578b81f7b661` and was squash-merged as `1d381b6b5f75d8b92bd1feccfaa84196fea6d344`.
  - Dashboard is now a compact multi-crypto row view showing signal, duration, entry area, stop loss and %, expected T1/T2 moves and %, R:R and evidence.
  - Each row has TradingView chart and generated Pine v6 overlay actions. The generated overlay draws BUY/SELL, entry, stop/risk area, T1/T2, expected move %, duration, R:R and evidence directly on TradingView after the one-time Pine Editor paste/add-to-chart step.
  - Standard external TradingView chart URLs cannot inject arbitrary Pine scripts/drawings, so the overlay generator provides the supported workflow without changing signal logic or authority.
  - Render production deploy `dep-dafl71m7bikc73ee7qug` for merge `1d381b6b...` completed live successfully.
- Future acceleration work remains subordinate to the mandatory research-to-live chain; speed must come from parallelism, caching, early rejection, prioritization, event-driven agents and deterministic automation, never weaker evidence.

## COST / SPEED POLICY
Use deterministic Python for calculation/backtesting/filtering/evidence checks. Use AI for bounded planning, hypothesis generation, implementation/review and orchestration. Routine planner/specialists use `gpt-5.6-luna`; testing-security, strategy-registry, portfolio-risk and production-signals use `gpt-5.6-sol`; Lead and independent integration reviews use `gpt-5.6-sol`. Prefer event-driven wakeups over idle polling and read-only parallel audits over competing writes.

## EXACT NEXT STEP
1. Inspect completed Cloud Crypto Research run `34170631618` artifacts. Verify `execution_oos_robustness` exists in real artifacts, uses the same untouched holdout path, current snapshot anchor is never presented as historical, and record which strategies/timeframes retain positive expectancy/sum under maximum conservative execution stress. Also verify the new independent artifact-audit output. Do not infer results before artifact inspection.
2. If the replacement run has infrastructure/data failures, fix only the bounded cause and rerun. If evidence is valid, decide whether ACC-001 has enough execution robustness evidence to close; do not mark complete merely because code exists.
3. Obtain direct production observer state evidence: `/health.continuous_ai` must show `configured=true`, `cycle_count>=1`, `last_error_type=null`, five-minute cadence, bounded timeout and trade/write/promotion authority false.
4. Verify a post-PR #42/#43/#44/#47 production scan remains healthy, execution/liquidation evidence stays research-only, and no unvalidated TRADE appears.
5. After ACC-001 evidence is genuinely complete, refresh PR #46 on current main, require exact-head Security and Reliability success, then integrate only if its shadow/canary layer remains read-only/fail-closed.
6. Only then move to `ACC-002` cross-sectional ranking, then ACC-003 through ACC-007 sequentially while non-owner specialists audit in parallel.
7. Keep `live_promotions.json` empty and signing keys unused until repeated backtests, untouched OOS, robustness/stability, Strategy Registry review and Production Risk review genuinely complete.
8. Update this file after every completed development/integration cycle.
