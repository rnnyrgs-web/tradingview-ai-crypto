# AI DEVELOPMENT STATE
Last updated: 2026-09-07

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file in full before development. Never infer project state from ChatGPT memory. Every completed development/integration cycle must update this file on `main` so a new agent can continue from the exact repository state.

## CURRENT ARCHITECTURE
Production is GitHub -> Render -> Python/FastAPI V3 -> Supabase. Production scans run approximately every 15 minutes and produce separate 24h and 7d Top-20 opportunity rankings. Cloud research/backtesting runs hourly 24/7. The dynamic intraday research universe targets Top-80 liquid OKX markets on 15m + 1H, with PONS forcibly included as `PONS-USDT-SWAP`; major swing research remains 4H + 1D.

There are 15 autonomous development roles: Lead Integrator plus 14 specialists: quant-trend, quant-mean-reversion, quant-breakout-volatility, quant-cross-asset, data-market, data-integrity, market-microstructure, onchain-tokenomics, news-macro, strategy-registry, portfolio-risk, production-signals, testing-security and infra-cost. Specialist cycles allow exactly one `CHANGE` role plus thirteen read-only `AUDIT` roles. The Lead runs after specialist workflows plus a minute-47 fallback.

Specialist proposals originate from isolated `auto/<role>/<run>` branches. Specialists cannot edit protected orchestration/state files or write directly to `main`. Candidate integration requires exact-SHA Security and Reliability success, independent Security AI and Lead AI approval, bounded/protected-path checks, final tests and canonical `AI_STATE.md` update.

## USER-MANDATED LIVE SIGNAL RULE — ENFORCED
No AI opinion, ranking score, evidence score or single OOS result may authorize live BUY/SELL. Mandatory chain:
RESEARCH -> BACKTEST -> VALIDATION -> UNTOUCHED OOS -> ROBUSTNESS/STABILITY -> STRATEGY-REGISTRY APPROVAL -> PRODUCTION-RISK APPROVAL -> LIVE BUY/SELL.
Missing or unreliable evidence always means `WAIT / NO TRADE / RESEARCH_ONLY`.

`production_validation.py` uses exact-fingerprint live validation and canonical `live_promotions.json`, currently intentionally empty. `strategy_identity.py` binds symbol, horizon, normalized family, required timeframes, strategy version, modeled cost and implementation SHA-256. `engine.py` and `opportunity_engine.py` downgrade unapproved actions to WAIT. Promotion requires >=3 distinct sealed research artifacts plus independent Strategy Registry + Production Risk HMAC-SHA256 attestations. Signing keys remain intentionally unused until all evidence is genuinely complete.

## VALIDATION / CALIBRATION / ROBUSTNESS
Chronological validation remains 60% train / 20% validation / 20% untouched holdout. Research candidates receive deterministic OOS robustness: 500 seeded bootstrap/Monte Carlo resamples, ±10% threshold perturbations, multi-regime holdout testing, realistic cost assumptions and the original chronological gate. Only all-pass candidates become `ROBUST_OOS`, still research-only.

Research artifacts are SHA-256 sealed. `research_aggregation.py` rejects tampering/non-robust runs and requires three distinct sealed runs before `READY_FOR_STRATEGY_REGISTRY_REVIEW`; that status is never live approval.

The append-only Supabase prediction ledger records every ranked 24h/7d forecast before outcome with fixed `due_at`, direction, entry, score, regime, strategy identity, action and calibration snapshot. Outcomes use the first hourly close at or after the deadline. Calibration is horizon + score-bin specific, prefers regime-specific samples once populated, requires >=30 comparable resolved forecasts, and requires a 95% Wilson lower bound >=50%. Calibration can only restrict; it cannot approve or bypass research/registry/risk/promotion gates.

First strict OOS pass set from run `34077019168`: ETH-USDT 1H trend; SOL-USDT 15m mean reversion; DOGE-USDT 1H volatility expansion; ADA-USDT 1H breakout; ADA-USDT 1H volatility expansion. None are live-weighted; one OOS pass is insufficient for promotion.

## MARKET / EXECUTION INTELLIGENCE
Production uses fail-closed fresh OKX + Binance spot price consensus. Fewer than two valid sources, stale observations or excessive disagreement forces WAIT. Derivatives context includes exchange-specific funding/open interest, median funding, dispersion/crowding and optional liquidation pressure represented in raw contract units when USD notional is not defensible.

PR #31 merged as `8aefc5004ca7f9bcfbf3aa07240a97629ccae6e5` and added research-only cross-exchange order-book intelligence for finalists: 10/25 bps depth, spread, bounded imbalance, thin/crossed/wide-book rejection, two-source reliability and explicit disagreement. It cannot promote WAIT to TRADE.

ACC-001 execution-realism work is IN PROGRESS:
- PR #38 passed exact-SHA Security and merged as `18a12236270cc753dfa703b21b51e647edebdd0b`. Backtests now stress the same selected trade path under deterministic 1.0x/1.5x/2.0x/3.0x round-trip cost assumptions for full and untouched-holdout results. Historical executable bid/ask data is not fabricated.
- Event-driven specialist run `34164957501` used compact supervisor context, all 14 specialists, exactly one CHANGE (`market-microstructure`) + thirteen AUDIT roles. Candidate `aa26b262e1846ec8f6b19f89ef246c1455f05e5b` passed exact-SHA Security run `34165052774`, independent reviews, and Lead run `34165057364` integrated it as main commit `3ee439912b7dcf91efd9a9891e40c39649820c91`. This validated the event-driven one-writer/thirteen-auditor path end-to-end.
- That candidate added fail-closed strict timestamp ordering before positional future-bar scoring. Missing, invalid, duplicate or non-increasing timestamps refuse backtests/walk-forward rather than sort/fill/fabricate chronology. Cost scenarios preserve the exact selected trade path.
- PR #39 passed exact-SHA Security and Reliability run `34165273009` and merged as `2e71fd84446a5a527ca82999b15a4b182c236cf4`. `market_data.py` now provides research-only, chronologically deduplicated OKX + Binance funding history and recent Binance USDⓈ-M OI history/change. Funding is reliable only with >=2 populated sources. Missing/invalid upstream data remains explicitly unavailable.
- PR #41 `Add timestamp-safe historical basis evidence` passed Security and Reliability run `34166100995` on exact head `ab485ed6bb366a7ad027cb2bf4b4e7cb6eed69fe` and merged as `d48d627b6d51bdd7262a4707856e5c6fd9280827`. Research now fetches official OKX historical mark-price and index-price candles, rejects incomplete/invalid rows, aligns exact shared timestamps only, and computes mark-vs-index basis in bps. Missing overlap remains explicitly unavailable; no interpolation or historical order-book reconstruction is performed. Deterministic tests cover exact timestamp alignment, basis math and fail-closed upstream failures.

ACC-001 is not complete. Remaining work: defensible liquidation evidence, realistic live fill/slippage research integration, then relevant untouched-OOS/robustness validation. Never fabricate unavailable historical order-book, spread, execution or liquidation notional.

Operational monitoring exposes sanitized health only. The 15-minute workflow validates returned JSON and fails on `ok != true`, empty/degraded scans, AI/opportunity errors, excessive symbol failures, missing fingerprint or any unvalidated TRADE. Security regression, Bandit, dependency audit and committed-secret checks remain enforced.

## 24/7 AI / ORCHESTRATION
A token-free Render `continuous_coordinator.py` watchdog checks production health + this handoff every minute. Render service `srv-dafgtead0e5s73cc7ekg` is live and has no scan/write/promotion/trade authority.

PR #35 added `continuous_ai_agent.py` inside the production FastAPI process. It runs a read-only AI research/operations assessment every five minutes by default and exposes compact state through `/health.continuous_ai`. It has `trade_authority=false`, `write_authority=false`, and `promotion_authority=false`.

The first live cycle exposed `JSONDecodeError`; PR #36 hardened parsing and passed Security run `34164097754`. Subsequent production verification found that after redeploys the observer had no later success/failure completion evidence within the expected window, while the loop wiring in `app.py` was correct. Inspection identified an unbounded OpenAI SDK request as a possible stall path.

PR #40 `Bound continuous AI observer request time` fixed that operational risk. Exact head `c09b33042fbd0cee0116a15d545bd07bc6c859c8` passed Security and Reliability run `34165649218`, then merged as `3e26d60bdf812564203be61df842b7e3456fcf36`. The observer now uses an explicit OpenAI request timeout (default 60s, clamped 10-240s), zero SDK retries, exposes `request_timeout_seconds`, and remains read-only. Render deploy `dep-dafjca7avr4c73c7hrr0` reached LIVE. After the following state-only deploy, `/health` remained HTTP 200 and no observer failure log appeared during a full default timeout window. However the module's INFO completion log is not surfaced by the current production logging configuration and the response body of `/health.continuous_ai` has not been directly read, so `cycle_count>=1` is still not claimed as directly verified.

## EVENT-DRIVEN SUPERVISOR / ACCURACY ROADMAP — LIVE
PR #37 passed exact-final-SHA Security run `34164722593` and merged as `6314dbe518bf2c1989b87507a656b73955735c90`.

The control plane:
- wakes after completed `Crypto 15m Scan` and `Cloud Crypto Research` workflows plus the minute-17 hourly fallback;
- uses `agents/supervisor_snapshot.py` for compact machine-readable context;
- stores accuracy work in protected `orchestration/priority_backlog.json`;
- allows exactly one CHANGE + thirteen parallel AUDIT workers (`max-parallel: 14`);
- protects `AI_STATE.md`, `agents/`, `orchestration/`, `.github/workflows/`, `requirements.txt` and `Dockerfile` from specialist writes;
- requires exact-SHA Security plus independent Security AI + Lead AI approval before verified autonomous integration.

Protected accuracy backlog:
1. `ACC-001` market-microstructure — realistic execution + richer market-state evidence. IN PROGRESS: execution-cost stress, timestamp chronology, two-source historical funding, recent OI-change and exact-timestamp historical basis are integrated; liquidation/fill-slippage and OOS/robustness evidence remain.
2. `ACC-002` quant-cross-asset — cross-sectional relative-strength/rank prediction across the liquid universe.
3. `ACC-003` quant-breakout-volatility — regime-specialist models for bull, bear, range, high-volatility stress and compression with no-lookahead labels/minimum samples.
4. `ACC-004` strategy-registry — calibrated champion/challenger ensemble weighting with correlation/deterioration penalties and automatic demotion.
5. `ACC-005` data-market — broader high-quality market/exchange coverage with provenance, freshness, contradiction checks, batching and safe PONS handling.
6. `ACC-006` production-signals — continuous forecast scoring and strategy/feature/regime/asset deterioration detection from the immutable prediction ledger.
7. `ACC-007` testing-security — expanded adversarial strategy-destruction tests across exchanges, periods, fees, slippage, parameters, malformed data and regime shifts.

These are research/development priorities only. Each must pass tests, untouched OOS/robustness where applicable, exact-SHA Security, independent reviews and the normal promotion chain before affecting BUY/SELL.

## COST / SPEED POLICY
Use deterministic Python for calculation, backtesting, filtering and evidence checks. Use AI for bounded planning, hypothesis generation, implementation/review and orchestration. Routine planner/specialists use `gpt-5.6-luna`; testing-security, strategy-registry, portfolio-risk and production-signals use `gpt-5.6-sol`; Lead and independent integration reviews use `gpt-5.6-sol`. Recheck official model/pricing before future routing changes.

Prefer event-driven wakeups over idle polling. Preserve concurrency locks so overlapping events cannot create competing write candidates. Increase useful parallelism through read-only audits/research shards, not multiple simultaneous writes to `main`.

## SAFETY INVARIANTS
Specialists use isolated `auto/<role>/<run>` branches and cannot directly write to `main`. Protected paths: `AI_STATE.md`, `agents/`, `orchestration/`, `.github/workflows/`, `requirements.txt`, `Dockerfile`. Candidate code must pass full pytest, cache cleanup and protected-path checks before publication. Candidate publication dispatches Security and Reliability.

Verified-only autonomous merging remains enabled but cannot bypass: exact-SHA Security, independent Security AI, independent Lead AI, bounded/protected diffs, final tests and canonical state update. Research/news/on-chain/order-book/continuous-AI/backlog evidence can never bypass live strategy approval. Missing, malformed, stale, contradictory or chronologically invalid evidence must fail closed.

## EXACT NEXT STEP
1. Obtain direct post-PR #40 observer state evidence: `/health.continuous_ai` must show `configured=true`, `cycle_count>=1`, `last_error_type=null`, five-minute cadence, bounded request timeout and trade/write/promotion authority false. If INFO completion logs remain hidden, improve observer observability without exposing secrets or granting authority.
2. Continue `ACC-001` with defensible liquidation evidence and realistic live fill/slippage estimates from actual current books. Historical order-book/slippage must remain unavailable unless genuinely sourced; do not fabricate it. Keep all new evidence research-only and add deterministic tests.
3. After execution evidence is integrated, run relevant untouched-OOS/robustness comparisons before calling ACC-001 complete.
4. Verify subsequent event-driven specialist cycles continue exactly one CHANGE + thirteen AUDIT roles with compact supervisor context and exact-SHA Security/Lead integration.
5. Execute `ACC-002` through `ACC-007` sequentially by evidence while non-owner specialists audit in parallel. Never mark work complete merely because code was written.
6. Verify full post-order-book production scans remain healthy, order-book evidence stays research-only and no unvalidated trade appears.
7. Verify authenticated production workflow scans have two-source consensus where available, fail closed where not, pass `tools/validate_scan_response.py` and contain no unvalidated trade.
8. After forecast deadlines pass, verify first 24h/7d outcomes use only data at/after `due_at`; calibration remains restrictive until >=30 comparable resolutions and 95% Wilson lower bound >=50%.
9. Keep `live_promotions.json` empty and signing keys unused until repeated backtests, untouched OOS, robustness/stability, registry review and production-risk review genuinely complete.
10. Verify next cloud research emits valid sealed robustness/repeated-run evidence; `READY_FOR_STRATEGY_REGISTRY_REVIEW` remains research-only. Inspect run `34079774231` artifacts before any PONS-specific result or promotion claim.
11. Update this file after every completed development/integration cycle.
