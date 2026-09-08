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
- PR #43 `Add untouched OOS execution robustness evidence` passed Security and Reliability run `34168441761` on final head `6eb5248189df9ecc53a2c590d58cdee20573639d` and merged as `dbefac4bbc9a145e18d6b871b4edb93cf73a0976`.
- PR #44 `Accelerate cloud research without weakening gates` passed exact-head Security and Reliability run `34170047571` on `7107d85f6a81ca21e2cc7e2371837094a10552b7` and merged as `442b93e864682326195a3ae6c799fc231d43cbcd`.
  - Cloud research concurrency is isolated by event/ref so stale feature-branch runs cannot block main research.
  - Broad-universe matrix parallelism increases from 8 to 16 when GitHub capacity is available.
  - Dedicated BTC/ETH/SOL/XRP/LINK fast-evidence workers run 15m + 1H in parallel while Top-80 + forced PONS research continues.
  - Expensive bootstrap/perturbation robustness is skipped only for candidates that already fail deterministic train/validation/untouched-OOS quality gates.
  - A separate adversarial artifact audit independently checks sealed integrity, fail-closed promotion, same-holdout execution policy and that live snapshot slippage is never represented as historical.
  - No OOS, robustness, promotion or live-authority gate was weakened.
- Merge `442b93e...` triggered Cloud Crypto Research run `34170631618`. Lead inspected the downloaded broad-universe, swing, fast-evidence, repeated-run and adversarial-audit artifacts on 2026-09-08 rather than inferring success from workflow status.
  - 177/177 result records carrying `execution_oos_robustness` were `ok=true`, preserved `same_trade_path_policy=true`, and explicitly reported `historical_slippage_available=false`; current snapshots were never represented as historical evidence.
  - 23 unique symbol/timeframe paths retained positive expectancy and positive cumulative net return at their maximum conservative execution stress: `SOL-USDT 1H`, `CHIP-USDT 1H`, `EDGE-USDT 1H`, `PEPE-USDT 1H`, `ARB-USDT 15m`, `NEAR-USDT 1H`, `CRV-USDT 15m`, `CRV-USDT 1H`, `XMSTR-USDT 1H`, `DOT-USDT 1H`, `AEON-USDT 1H`, `DOOD-USDT 15m`, `UNI-USDT 1H`, `ZAMA-USDT 1H`, `ENA-USDT 1H`, `INJ-USDT 1H`, `ETH-USDT 1D`, `SOL-USDT 4H`, `XRP-USDT 4H`, `LINK-USDT 1D`, `HBAR-USDT 1H`, `FET-USDT 1H`, and `APT-USDT 1H`.
  - Independent `adversarial_audit.json` reported `ok=true`, zero failures, and checked all 17 broad/swing artifact groups (172 results).
  - Repeated-run aggregation validated 51 sealed artifacts and advanced only `ARB-USDT 15m trend`, `DOOD-USDT 15m breakout`, and `DOOD-USDT 15m momentum` to `READY_FOR_STRATEGY_REGISTRY_REVIEW`; all remain `live_approved=false`.
  - ACC-001 is closed as completed market/execution-realism evidence work. It is not a profitability claim and grants no signal, promotion or trading authority.

## 24/7 AI / ORCHESTRATION
Token-free Render coordinator checks production health/state every minute with no trade/write/promotion authority.

`continuous_ai_agent.py` runs inside production every five minutes by default, read-only, with `trade_authority=false`, `write_authority=false`, `promotion_authority=false`. PR #40 merged `3e26d60bdf812564203be61df842b7e3456fcf36`; OpenAI requests have bounded timeout (default 60s, clamped 10-240s), zero SDK retries and sanitized timeout state. Direct pre-PR #46 production evidence on 2026-09-08 showed `configured=true`, `cycle_count=7`, `last_error_type=null`, 300-second cadence, 60-second timeout and all three authorities false. The PR #46 deployment restarted in-memory state and its first AI call hit `RateLimitError`; a fresh post-deploy successful cycle is still required before claiming current live-cycle health.

Event-driven supervisor from PR #37 wakes on completed production scan/cloud research plus hourly fallback, provides compact supervisor context and allows exactly one CHANGE + thirteen AUDIT workers with max-parallel 14. The one-writer/thirteen-auditor path has been verified end-to-end.

PR #55 `Add bounded 24/7 Python research worker army` passed exact-head Security and Reliability run `34180983272` on `73026f62b951ced740b0699e9c0e0c02cb376030` and was squash-merged as `10416b2ef89f54b46632aeabb49968edbb6d8c67`.
- Existing paid Render Starter coordinator now hosts 15 persistent logical Python research loops on the same single paid service; no additional paid Render service was created.
- Worker coverage: BTC, ETH, SOL, XRP, LINK, PONS, eight liquid-universe shards, plus major swing research.
- Heavy subprocess concurrency is hard-bounded to 2 by default and at most 4, with staggered starts, timeouts, temp working directories, and rest/backoff loops. This keeps one inexpensive machine continuously productive without an uncontrolled CPU/process explosion.
- Normal worker-army operation uses deterministic Python and public market-data calls, not OpenAI API calls.
- Worker army is hard-coded research-only: `trade_authority=false`, `write_authority=false`, `promotion_authority=false`, `broker_connected=false`.
- Render auto-deploy `dep-dafndl3bc2fs73df6nj0` for merge `10416b2e...` completed `live` on 2026-09-08.
- Cost policy: keep recurring infrastructure within the user's hard ceiling of USD 30/month. Prefer one shared paid machine, bounded concurrency, free/public data, deterministic Python, caching/reuse and GitHub-hosted research where cost-free/within included quota. Do not add another paid service or paid data/API dependency without explicit user approval.

## ACCURACY BACKLOG
1. `ACC-001` market-microstructure — COMPLETE.
2. `ACC-002` quant-cross-asset — cross-sectional relative-strength/rank prediction across liquid universe.
3. `ACC-003` quant-breakout-volatility — no-lookahead regime-specialist models for bull/bear/range/high-volatility/compression.
4. `ACC-004` strategy-registry — calibrated champion/challenger ensemble weighting with correlation/deterioration penalties and automatic demotion.
5. `ACC-005` data-market — broader exchange/data coverage with provenance/freshness/contradiction checks and safe PONS handling.
6. `ACC-006` production-signals — continuous forecast scoring and deterioration detection from immutable prediction ledger.
7. `ACC-007` testing-security — expanded adversarial strategy-destruction tests across exchanges, periods, fees, slippage, parameters, malformed data and regimes.

## REAL-MONEY READINESS ACCELERATION
Master tracking issue #45 covers the safe acceleration program.
- PR #46 `Add forward shadow and canary readiness gates` was squash-merged as `b19913c383501defe84d8f22ba3590e0f8ed71b2` after exact-head Security and Reliability success.
- PR #47 added compact crypto signal rows with one-click TradingView.
- PR #48 embedded signal levels directly on a TradingView-style chart and deployed live.
- PR #49 added the persistent $100k continuous paper trading simulator, permanently research-only and broker-disconnected.
- PR #51 combined the paper portfolio and ranked signals on the main dashboard.
- PR #52 made paper trading forward-only and realistic. All legacy paper trades/equity were invalidated and Supabase account `default` reset at `2026-09-08T01:17:49Z` to exactly `$100,000` cash/equity, `$0` realized P&L, zero drawdown, zero trades and zero snapshots. Only forward trades opened after this reset count as authentic paper-performance evidence.
- Future acceleration work remains subordinate to the mandatory research-to-live chain; speed must come from parallelism, caching, early rejection, prioritization, event-driven agents and deterministic automation, never weaker evidence.

## COST / SPEED POLICY
Hard infrastructure ceiling: USD 30/month unless the user explicitly changes it. Use the existing single paid Render worker/coordinator rather than multiplying paid machines. Default worker-army heavy concurrency is 2; raise only after measured capacity evidence and never by adding paid capacity without approval. Use deterministic Python for calculation/backtesting/filtering/evidence checks. Use free/public market data where defensible. Use AI only for bounded planning, hypothesis generation, implementation/review and orchestration. Routine planner/specialists use `gpt-5.6-luna`; testing-security, strategy-registry, portfolio-risk and production-signals use `gpt-5.6-sol`; Lead and independent integration reviews use `gpt-5.6-sol`. Prefer event-driven wakeups, caching/reuse, early rejection and read-only parallel audits over idle paid computation or competing writes.

## EXACT NEXT STEP
1. Verify live `/health` on the continuous coordinator reports all 15 logical workers, bounded `max_concurrent<=4` (target 2), `research_only=true`, and broker/trade/write/promotion authorities false. Investigate any repeated worker failures/timeouts before increasing throughput.
2. Recheck production `/health.continuous_ai`; require `cycle_count>=1`, `last_error_type=null`, bounded timeout and trade/write/promotion authority false. If rate limiting persists, fix only the bounded provider/cadence cause without granting authority.
3. Begin `ACC-002` cross-sectional relative-strength/rank prediction across the liquid universe. Keep feature computation timestamp-safe and evaluate rank information coefficient/top-minus-bottom spread using chronological train/validation/untouched OOS plus realistic costs.
4. Tune worker scheduling for throughput-per-dollar rather than raw process count: reuse/caching first, reject weak candidates early, keep the majors/PONS fast lane, and avoid duplicate overlapping research work between Render and GitHub Actions.
5. Let the freshly reset `$100,000` forward-only paper account collect new trades from zero. Treat only trades opened after `2026-09-08T01:17:49Z` as authentic paper-performance evidence. Alert only when the persisted `consistently_profitable` gate is genuinely satisfied; do not infer profitability from unrealized equity or a small sample.
6. Continue ACC-003 through ACC-007 sequentially after ACC-002 evidence, while non-owner specialists audit in parallel.
7. Keep `live_promotions.json` empty and signing keys unused until repeated backtests, untouched OOS, robustness/stability, Strategy Registry review and Production Risk review genuinely complete.
8. Update this file after every completed development/integration cycle.