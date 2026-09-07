# AI DEVELOPMENT STATE
Last updated: 2026-09-07

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file in full before development. Never infer project state from ChatGPT memory. Update this file on `main` after every completed development/integration cycle.

## CURRENT ARCHITECTURE
Production: GitHub -> Render -> Python/FastAPI V3 -> Supabase. Production scans run about every 15 minutes and produce separate 24h/7d Top-20 rankings. Cloud research/backtesting runs hourly 24/7. Intraday research targets Top-80 liquid OKX markets on 15m + 1H, with PONS forcibly included as `PONS-USDT-SWAP`; swing research uses 4H + 1D.

There are 15 autonomous development roles: Lead Integrator plus 14 specialists. Each specialist cycle permits exactly one `CHANGE` role plus thirteen read-only `AUDIT` roles. Specialists work on isolated `auto/<role>/<run>` branches and cannot write `main` or protected orchestration/state paths. Verified integration requires exact-SHA Security and Reliability success, independent Security AI + Lead AI approval, bounded/protected-path checks, final tests, and this canonical state update.

## LIVE SIGNAL SAFETY — ENFORCED
No AI opinion, ranking score, evidence score or single OOS result may authorize live BUY/SELL. Mandatory chain:
RESEARCH -> BACKTEST -> VALIDATION -> UNTOUCHED OOS -> ROBUSTNESS/STABILITY -> STRATEGY-REGISTRY APPROVAL -> PRODUCTION-RISK APPROVAL -> LIVE BUY/SELL.
Missing/unreliable evidence means `WAIT / NO TRADE / RESEARCH_ONLY`.

`live_promotions.json` remains intentionally empty. Strategy identity binds symbol, horizon, family, required timeframes, strategy version, modeled cost and implementation SHA-256. Promotion requires >=3 distinct sealed research artifacts plus independent Strategy Registry + Production Risk HMAC-SHA256 attestations. Signing keys remain unused until genuine evidence is complete.

## VALIDATION / CALIBRATION
Chronological validation remains 60% train / 20% validation / 20% untouched holdout. Robustness uses 500 seeded bootstrap/Monte Carlo resamples, parameter perturbations, multi-regime holdout testing and realistic costs. Only all-pass candidates become `ROBUST_OOS`, still research-only. Research artifacts are SHA-256 sealed and three distinct sealed robust runs are required before `READY_FOR_STRATEGY_REGISTRY_REVIEW`.

Prediction ledger is append-only with fixed `due_at`. Outcomes use the first hourly close at/after deadline. Calibration is horizon + score-bin specific, requires >=30 comparable resolved forecasts and 95% Wilson lower bound >=50%, and can only restrict.

## ACC-001 MARKET / EXECUTION REALISM — IN PROGRESS
Integrated evidence:
- PR #38 merged `18a12236270cc753dfa703b21b51e647edebdd0b`: deterministic 1.0x/1.5x/2.0x/3.0x execution-cost stress on full and untouched-holdout research paths.
- Event-driven candidate `aa26b262e1846ec8f6b19f89ef246c1455f05e5b` integrated as main commit `3ee439912b7dcf91efd9a9891e40c39649820c91`: fail-closed strict timestamp ordering; missing/duplicate/non-increasing timestamps refuse backtest/walk-forward.
- PR #39 merged `2e71fd84446a5a527ca82999b15a4b182c236cf4`: timestamp-safe OKX + Binance funding history and recent Binance USDⓈ-M OI history/change; two populated funding sources required for reliability.
- PR #41 merged `d48d627b6d51bdd7262a4707856e5c6fd9280827`: timestamp-safe historical OKX mark-vs-index basis using exact shared timestamps only; no interpolation.
- PR #42 `Add live slippage and defensible liquidation evidence` passed exact-SHA Security and Reliability run `34166772184` on head `c99889b1525f3f58147fed9a2bfa706ba36260c5` and merged as `f6f0e2df83ed7e6d593a2cf3cc99b22809a90cf1`.
  - `market_intelligence.py` now simulates current-book market fills from actual visible spot order-book depth for quote notionals 1k/5k/10k by default.
  - It reports VWAP, slippage bps vs current mid, complete/partial fill, coverage ratio and visible-depth insufficiency.
  - It never extrapolates unseen depth and explicitly marks this evidence `research_only=true` and `historical=false`.
  - Liquidation evidence now reports event counts, raw contract sizes and price*size pressure units only, with `pressure_units_are_usd=false`; no false USD notional is claimed.
  - Cross-exchange order-book output reports how many reliable exchanges have current live-slippage evidence.
  - Deterministic tests cover complete/partial fills, empty/crossed books and fail-closed liquidation evidence.

ACC-001 is NOT complete. The next step is untouched-OOS/robustness comparison using the integrated execution evidence. Historical order-book/slippage remains unavailable unless genuinely sourced; never fabricate it.

## 24/7 AI / ORCHESTRATION
Token-free Render coordinator checks production health/state every minute with no trade/write/promotion authority.

`continuous_ai_agent.py` runs inside production every five minutes by default, read-only, with `trade_authority=false`, `write_authority=false`, `promotion_authority=false`. PR #40 merged `3e26d60bdf812564203be61df842b7e3456fcf36`; OpenAI requests now have explicit bounded timeout (default 60s, clamped 10-240s), zero SDK retries and sanitized timeout state. Direct `/health.continuous_ai` evidence showing `cycle_count>=1` is still required before claiming full live-cycle verification.

Event-driven supervisor from PR #37 wakes on completed `Crypto 15m Scan` and `Cloud Crypto Research` workflows plus hourly fallback, provides compact supervisor context and allows exactly one CHANGE + thirteen AUDIT workers with max-parallel 14. The one-writer/thirteen-auditor path has been verified end-to-end.

## ACCURACY BACKLOG
1. `ACC-001` market-microstructure — execution realism + market-state evidence. IN PROGRESS; execution evidence integrated, OOS/robustness comparison next.
2. `ACC-002` quant-cross-asset — cross-sectional relative-strength/rank prediction across liquid universe.
3. `ACC-003` quant-breakout-volatility — no-lookahead regime-specialist models for bull/bear/range/high-volatility/compression.
4. `ACC-004` strategy-registry — calibrated champion/challenger ensemble weighting with correlation/deterioration penalties and automatic demotion.
5. `ACC-005` data-market — broader high-quality exchange/data coverage with provenance/freshness/contradiction checks and safe PONS handling.
6. `ACC-006` production-signals — continuous forecast scoring and deterioration detection from immutable prediction ledger.
7. `ACC-007` testing-security — expanded adversarial strategy-destruction tests across exchanges, periods, fees, slippage, parameters, malformed data and regimes.

## COST / SPEED POLICY
Use deterministic Python for calculation/backtesting/filtering/evidence checks. Use AI for bounded planning, hypothesis generation, implementation/review and orchestration. Routine planner/specialists use `gpt-5.6-luna`; testing-security, strategy-registry, portfolio-risk and production-signals use `gpt-5.6-sol`; Lead and independent integration reviews use `gpt-5.6-sol`. Prefer event-driven wakeups over idle polling. Increase useful parallelism through read-only audits/research shards, never competing writes to `main`.

## EXACT NEXT STEP
1. Obtain direct production observer state evidence: `/health.continuous_ai` must show `configured=true`, `cycle_count>=1`, `last_error_type=null`, five-minute cadence, bounded timeout and trade/write/promotion authority false. If necessary, improve sanitized observability only.
2. Run relevant untouched-OOS/robustness comparisons with ACC-001 execution-cost/slippage evidence before marking ACC-001 complete. Live snapshot slippage must not be backfilled into historical periods as if it were historical data; use it only as current evidence and/or to inform explicitly conservative stress scenarios.
3. Verify a post-PR #42 production scan remains healthy, order-book/slippage/liquidation evidence stays research-only, and no unvalidated TRADE appears.
4. Then move to `ACC-002` cross-sectional ranking, followed sequentially by ACC-003 through ACC-007 while non-owner specialists audit in parallel.
5. Keep `live_promotions.json` empty and signing keys unused until repeated backtests, untouched OOS, robustness/stability, Strategy Registry review and Production Risk review genuinely complete.
6. Update this file after every completed development/integration cycle.
