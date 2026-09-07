# AI DEVELOPMENT STATE
Last updated: 2026-09-07

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file in full before development. Never infer project state from ChatGPT memory. Every completed development/integration cycle must update this file on `main` so a new agent can continue from the exact repository state.

## CURRENT ARCHITECTURE
Production is GitHub -> Render -> Python/FastAPI V3 -> Supabase. Production scans run approximately every 15 minutes and produce separate 24h and 7d Top-20 opportunity rankings. Cloud research/backtesting runs hourly 24/7. The dynamic intraday research universe targets Top-80 liquid OKX markets on 15m + 1H, with PONS forcibly included as `PONS-USDT-SWAP`; major swing research remains 4H + 1D.

There are 15 autonomous development roles: Lead Integrator plus 14 specialists: quant-trend, quant-mean-reversion, quant-breakout-volatility, quant-cross-asset, data-market, data-integrity, market-microstructure, onchain-tokenomics, news-macro, strategy-registry, portfolio-risk, production-signals, testing-security and infra-cost. The specialist cycle uses exactly one `CHANGE` role plus thirteen read-only `AUDIT` roles to avoid stale competing branches. The Lead runs after specialist workflows plus a minute-47 fallback.

## USER-MANDATED LIVE SIGNAL RULE — ENFORCED
No AI opinion, ranking score, evidence score or single OOS result may authorize live BUY/SELL. The mandatory chain is:
RESEARCH -> BACKTEST -> VALIDATION -> UNTOUCHED OOS -> ROBUSTNESS/STABILITY -> STRATEGY-REGISTRY APPROVAL -> PRODUCTION-RISK APPROVAL -> LIVE BUY/SELL.
Missing or unreliable evidence always means `WAIT / NO TRADE / RESEARCH_ONLY`.

PR #19 merged as `1a0004c31f1f8be570c72cfe0380a99994797316` and established exact-fingerprint live validation. `production_validation.py` uses the canonical `live_promotions.json`, currently intentionally empty. `strategy_identity.py` binds symbol, horizon, normalized family, required timeframes, strategy version, modeled cost and implementation SHA-256. `engine.py` and `opportunity_engine.py` both downgrade unapproved actions to WAIT. Promotion requires at least three distinct sealed research artifacts and independent Strategy Registry + Production Risk HMAC-SHA256 attestations. Signing keys remain intentionally unused until all evidence is genuinely complete.

## VALIDATION / CALIBRATION / ROBUSTNESS
Chronological validation remains 60% train / 20% validation / 20% untouched holdout. Research candidates receive deterministic OOS robustness: 500 seeded bootstrap/Monte Carlo resamples, ±10% threshold perturbations, multi-regime holdout testing, realistic cost assumptions and the original chronological gate. Only all-pass candidates become `ROBUST_OOS`, still research-only.

Research artifacts are SHA-256 sealed. `research_aggregation.py` rejects tampering/non-robust runs and requires three distinct sealed runs before `READY_FOR_STRATEGY_REGISTRY_REVIEW`; that status is never live approval.

The append-only Supabase prediction ledger records every ranked 24h/7d forecast before outcome with fixed `due_at`, direction, entry, score, regime, strategy identity, action and calibration snapshot. Outcomes use the first hourly close at or after the deadline. Calibration is horizon + score-bin specific, prefers regime-specific samples once populated, requires >=30 comparable resolved forecasts, and requires a 95% Wilson lower bound >=50%. Calibration can only restrict; it cannot approve or bypass research/registry/risk/promotion gates.

The first strict OOS pass set from run `34077019168` was: ETH-USDT 1H trend; SOL-USDT 15m mean reversion; DOGE-USDT 1H volatility expansion; ADA-USDT 1H breakout; ADA-USDT 1H volatility expansion. None are live-weighted.

## MARKET / EXECUTION INTELLIGENCE
Production uses fail-closed fresh OKX + Binance spot price consensus. Fewer than two valid sources, stale observations or excessive disagreement forces WAIT. Derivatives context includes exchange-specific funding/open interest, median funding, dispersion/crowding and optional liquidation pressure represented in raw contract units when USD notional is not defensible.

PR #31 merged as `8aefc5004ca7f9bcfbf3aa07240a97629ccae6e5` and added research-only cross-exchange order-book intelligence for AI finalists: 10/25 bps depth, spread, bounded imbalance, thin/crossed/wide-book rejection, two-source reliability and explicit disagreement. It has no path that promotes WAIT to TRADE.

ACC-001 execution-realism work has begun. PR #38 `Add execution-cost stress testing to research backtests` passed exact-SHA Security and Reliability run `34164900477` (unit tests, dependency audit, static security and committed-secret rejection) and merged as `18a12236270cc753dfa703b21b51e647edebdd0b`. `backtest.py` now stress-tests the same research trade path under deterministic 1.0x/1.5x/2.0x/3.0x round-trip cost assumptions and reports both full-backtest and untouched-holdout cost stress. Historical candle data does not contain executable bid/ask history, so no historical spread is fabricated. This is an initial ACC-001 stage only; richer timestamp-safe funding/basis/OI/liquidation history and fill/slippage evidence still need research and validation before ACC-001 can be considered complete.

Operational monitoring exposes sanitized health only. The 15-minute workflow validates returned JSON and fails on `ok != true`, empty/degraded scans, AI/opportunity errors, excessive symbol failures, missing fingerprint or any unvalidated TRADE. Security regression, Bandit, dependency audit and committed-secret checks remain enforced.

## 24/7 AI / ORCHESTRATION
A token-free Render `continuous_coordinator.py` watchdog checks production health and this canonical handoff every minute. Render service `srv-dafgtead0e5s73cc7ekg` is live and has no scan/write/promotion/trade authority.

The owner requested a real AI agent active 24/7. PR #35 merged as `0b199acdca36c666091940d8b5c6a591ff03adc0`, adding `continuous_ai_agent.py` inside the production FastAPI process. It performs a bounded AI research/operations assessment every five minutes by default and exposes the compact result through `/health.continuous_ai`. It has explicit `trade_authority=false`, `write_authority=false`, and `promotion_authority=false`.

The first live cycle exposed a model-output `JSONDecodeError`. PR #36 merged as `433421d244259e749827e8fba63e13cee4bbc7a5`, hardened parsing while keeping malformed output fail-closed, and passed Security and Reliability run `34164097754`. Main state sync commit `641d4688fc959ecc466e6c1a853767b4392728ba` deployed live. A successful post-fix cycle still needs direct verification.

## EVENT-DRIVEN SUPERVISOR / ACCURACY ROADMAP — LIVE
PR #37 `Add event-driven AI supervisor and accuracy backlog` passed exact-final-SHA Security and Reliability run `34164722593` and merged as `6314dbe518bf2c1989b87507a656b73955735c90`.

The autonomous control plane now:
- wakes on completed `Crypto 15m Scan` and `Cloud Crypto Research` workflows as well as the minute-17 hourly fallback;
- uses `agents/supervisor_snapshot.py` to provide a compact machine-readable context with trigger metadata, safety invariants, exact next steps and prioritized backlog;
- stores signal-accuracy work in protected `orchestration/priority_backlog.json`, which autonomous specialists cannot edit and which cannot authorize live promotion;
- still permits exactly one `CHANGE` worker and thirteen parallel read-only `AUDIT` workers with `max-parallel: 14`;
- protects `AI_STATE.md`, `agents/`, `orchestration/`, `.github/workflows/`, `requirements.txt` and `Dockerfile` from autonomous specialist writes.

The protected accuracy backlog is:
1. `ACC-001` market-microstructure — realistic execution + richer market-state evidence. IN PROGRESS: deterministic execution-cost stress is merged; historical funding/basis/OI/liquidation and defensible fill/slippage evidence remain.
2. `ACC-002` quant-cross-asset — cross-sectional relative-strength/rank prediction across the liquid universe.
3. `ACC-003` quant-breakout-volatility — regime-specialist models for bull, bear, range, high-volatility stress and compression with no-lookahead labels/minimum samples.
4. `ACC-004` strategy-registry — calibrated champion/challenger ensemble weighting with correlation/deterioration penalties and automatic demotion.
5. `ACC-005` data-market — broader high-quality market/exchange coverage with provenance, freshness, contradiction checks, batching and safe PONS handling.
6. `ACC-006` production-signals — continuous forecast scoring and strategy/feature/regime/asset deterioration detection from the immutable prediction ledger.
7. `ACC-007` testing-security — expanded adversarial strategy-destruction tests across exchanges, periods, fees, slippage, parameters, malformed data and regime shifts.

These items are research/development priorities only. Each must still pass its own tests, untouched OOS/robustness where applicable, exact-SHA Security, independent reviews and the normal promotion chain before affecting BUY/SELL.

## COST / SPEED POLICY
Use deterministic Python for calculation, backtesting, filtering and evidence checks. Use AI for bounded planning, research hypothesis generation, implementation/review and orchestration. Routine planner/specialists use `gpt-5.6-luna`; testing-security, strategy-registry, portfolio-risk and production-signals use `gpt-5.6-sol`; Lead and independent integration reviews use `gpt-5.6-sol`. Recheck official model/pricing information before future routing changes.

Prefer event-driven wakeups over idle polling when a meaningful repository/research/production event already exists. Preserve concurrency locks so overlapping events do not create competing write candidates. Increase useful parallelism through read-only audits/research shards, not multiple simultaneous writes to `main`.

## SAFETY INVARIANTS
Specialists work on isolated `auto/<role>/<run>` branches. Protected orchestration/state paths are `AI_STATE.md`, `agents/`, `orchestration/`, `.github/workflows/`, `requirements.txt` and `Dockerfile`; specialists must never modify them. Candidate code must pass full pytest, generated-cache cleanup and protected-path checks before publication. Candidate publication dispatches Security and Reliability. Lead requires exact candidate SHA success, rejects oversized/protected diffs, requires independent Security AI + Lead AI approval, final post-squash pytest and canonical AI_STATE update before pushing `main`.

Verified-only autonomous merging is enabled, but these gates remain mandatory. Research, news, on-chain, order-book, continuous-AI and backlog evidence can never bypass live strategy approval.

## EXACT NEXT STEP
1. Verify the post-PR #36 production AI observer live cycle: `/health.continuous_ai` must show `configured=true`, `cycle_count>=1`, no current parser error, five-minute bounded cadence, and trade/write/promotion authority false; Render logs should show `continuous AI observer cycle completed`.
2. Verify the first post-PR #37 `workflow_run`-triggered Autonomous Specialist Agents cycle after a production scan or cloud-research completion; it must use the compact supervisor context and still produce exactly one CHANGE + thirteen AUDIT roles without overlapping write candidates.
3. Continue `ACC-001` with the next bounded evidence layer: investigate and implement timestamp-safe historical funding/basis/open-interest change data where genuinely available, plus defensible execution/fill/slippage stress. Do not fabricate unavailable historical order-book data. Require tests and relevant OOS/robustness evidence before calling ACC-001 complete.
4. Then execute `ACC-002` through `ACC-007` sequentially by evidence while non-owner specialists audit in parallel. Never mark an item complete merely because code was written.
5. Verify the first full post-order-book production scan keeps latency/errors healthy, order-book evidence stays research-only and no unvalidated trade appears.
6. Verify an authenticated production workflow scan has two-source consensus where available, fails closed where not, passes `tools/validate_scan_response.py` and contains no unvalidated trade.
7. After forecast deadlines pass, verify first 24h/7d outcomes use only data at/after `due_at` and calibration remains restrictive until >=30 comparable resolutions and Wilson lower bound >=50%.
8. Keep `live_promotions.json` empty and signing keys unused until strategies complete repeated backtests, untouched OOS, robustness/stability, registry review and production-risk review.
9. Verify the next cloud research run emits valid sealed robustness/repeated-run evidence; `READY_FOR_STRATEGY_REGISTRY_REVIEW` remains research-only. Inspect run `34079774231` artifacts before any PONS-specific result claim or promotion.
10. Update this file after every completed development/integration cycle.
