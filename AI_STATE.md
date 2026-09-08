# AI DEVELOPMENT STATE
Last updated: 2026-09-08

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file from `main` before development. Never infer project state from ChatGPT memory. Update this file on `main` after every completed development/integration cycle.

## CURRENT ARCHITECTURE
Production: GitHub -> Render -> Python/FastAPI V3 -> Supabase. Production scans run about every 15 minutes and produce separate 24h/7d Top-20 rankings. Cloud research/backtesting runs continuously through the existing bounded Python worker army. PONS is included when public data supports it and must fail closed when evidence is insufficient or inconsistent.

There are 15 autonomous development roles. Specialists use isolated branches and never write directly to `main`. Verified integration requires exact-head Security and Reliability success before merge.

## SAFETY INVARIANTS
No AI opinion, ranking score, evidence score, current order-book snapshot, paper P&L, ensemble weight, single OOS result, signed historical promotion, or risk-gate result by itself may authorize live BUY/SELL.

Mandatory chain:
RESEARCH -> BACKTEST -> VALIDATION -> UNTOUCHED OOS -> ROBUSTNESS/STABILITY -> STRATEGY-REGISTRY APPROVAL -> PRODUCTION-RISK APPROVAL -> GENUINE FORWARD PROOF -> GLOBAL/EXECUTION RISK CLEAR -> LIVE BUY/SELL.

Every later stage is restrictive-only. Missing, stale, contradictory, deteriorating, malformed, overlapping-only, insufficient, illiquid, execution-unsafe, portfolio-unsafe, or system-unsafe evidence means `WAIT / NO TRADE / RESEARCH_ONLY`.

`live_promotions.json` remains intentionally empty. Signing keys remain unused until genuine evidence is complete. A signed historical promotion remains insufficient without ACC-008 exact-fingerprint forward proof and all later risk gates.

## VALIDATION / CALIBRATION
Chronological validation remains train / validation / untouched holdout. Robustness includes deterministic bootstrap/Monte Carlo resampling, parameter perturbation, regime stability, and conservative execution-cost stress. Prediction ledger is append-only with fixed `due_at`; forward proof counts only non-overlapping full-horizon resolved forecasts for the exact immutable strategy fingerprint. Calibration and deterioration can only restrict eligibility.

## ACC-001 MARKET / EXECUTION REALISM — COMPLETE
Integrated across PRs #38-#44 and follow-on work. Protections include realistic execution-cost stress, timestamp-safe funding/OI/basis, visible-depth fill/slippage estimates without inventing hidden liquidity, untouched-OOS execution robustness, strict chronology, and research-only status until all promotion gates pass.

## 24/7 RESEARCH / ORCHESTRATION
PR #55 added bounded continuous Python research workers. PRs #65-#68 strengthened dedicated 24h/7d ACC-002 evidence collection, reserved accuracy capacity, sufficient independent history, and bounded retry/cache behavior. Existing paid infrastructure only unless explicitly approved; heavy concurrency remains bounded; recurring infrastructure ceiling is USD 30/month. Workers remain `research_only=true`, `trade_authority=false`, `write_authority=false`, `promotion_authority=false`, `broker_connected=false`.

## ACC-002 CROSS-ASSET RANK RESEARCH — IN PROGRESS
Integrated PRs #56-#60 and #64-#68. Current protections: timestamp-safe cross-sectional relative-strength ranking; multi-lookback momentum normalized by realized vol; chronological train/validation/untouched OOS; split purging; non-overlapping forward observations; predeclared candidate grids; sufficient independent OOS depth; nearby-parameter stability; Top-15/30/45 liquidity-subset stability; 1x/1.5x/2x/3x cost stress; deterministic 500-resample bootstrap; dedicated nonstop 24h and 7d workers; bounded deep-history retry/cache. All outputs remain research-only and no profitability claim is authorized yet.

## ACC-003 REGIME-CONDITIONED STRATEGY GATING — COMPLETE
PR #70 passed exact-head Security and Reliability run `34252423032` on `c192affed37965f75f0972b608b965ae7c40084e`, squash merge `606595e50f3057452714c50eb88e8178213ac5c8`. Causal trailing-only regimes are TREND_UP, TREND_DOWN, HIGH_VOL, COMPRESSION, RANGE. Regime eligibility is frozen from train + validation before holdout; unproven regimes cannot authorize.

## ACC-004 CHAMPION / CHALLENGER REGISTRY — COMPLETE
PR #71 passed exact-head run `34256093230` on `e40ba49678e7726462df79fb16df6645b00396a0`, squash merge `223bbd094e0ca8350f2673e94bec3d34a8836f87`. Requires >=3 distinct sealed robust OOS runs; conservative quality score; deterioration demotion; correlation/structural overlap penalties; concentration cap; explicit `unallocated_wait_weight`; one research champion plus challengers; `live_approved=false`.

## ACC-005 PROVENANCE-AWARE MARKET DATA GATING — COMPLETE
PR #72 passed exact-head run `34256741680` on `a4e5efe2fe0a0b6bcf89a735216abb37b9cd4651`, squash merge `bb4c0e4060bba067e5bee1a86f1247d30901d19e`. Independent sources count by unique exchange; missing/future/stale timestamps rejected; freshest valid quote retained; cross-exchange contradiction collapses confidence to zero; single-source evidence restricted; unreliable consensus forces WAIT; PONS naturally fails closed if independent confirmation is missing.

## ACC-006 ROLLING FORECAST DETERIORATION — COMPLETE
PR #73 passed exact-head run `34257098538` on `86b661a45817970ddaf91e56ffb469372125d20a`, squash merge `ad3973d01fe94d52010cdd6628d9f85a9dc23a3d`. Recent 20 comparable resolved forecasts are compared with at least 30 prior; both weak Wilson lower bound and material precision drop are required to flag deterioration. Deterioration can block only.

## ACC-007 ADVERSARIAL STRATEGY-DESTRUCTION TESTING — COMPLETE
PR #74 passed exact-head run `34257293281` on `59d7af5fcdbf8aee830f571a26f50488b81a6d58`, squash merge `76d83786acf132b6cc848dacf0edf17acba2ed77`. Robustness fails closed on NaN/Infinity/missing/malformed evidence; tests catastrophic tails, parameter collapse, insufficient regime diversity and deterministic bootstrap behavior.

## ACC-008 GENUINE FORWARD-PROOF PROMOTION GATE — COMPLETE
PR #75 passed exact-head run `34258912558` on `d47870757d4fdb846a8afadd3fab5835549a29d2`, squash merge `cf66104242467c8cf1177c91e20db206c92f62e5`. Requirements: exact immutable strategy fingerprint; chronological non-overlapping full-horizon forecasts; >=20 independent 24h or >=12 independent 7d observations; subtract 3x modeled round-trip cost; positive after-cost expectancy; Wilson 95% lower bound >=50%; max compounded forward DD <=12%; no active recent deterioration. Wrong fingerprint, malformed chronology, overlapping-only evidence, weak confidence, negative expectancy, excessive DD or deterioration fail closed.

## ACC-009 GLOBAL PORTFOLIO / EXECUTION RISK GATES — COMPLETE
PR #76 `ACC-009: Add Harris-inspired global and execution risk gates` passed exact-head Security and Reliability run `34264596759` on `285add1ac65903432d8ed4ffaa19aba149f2aa3d` and was squash-merged as `4f70e89f81b4f16df39d4fd2fe88b3c0f298d6f5`.

Implemented as restrictive-only gates inspired by Larry Harris market-microstructure principles:
- global WAIT on broad abnormal volatility, widespread liquidity/spread stress, repeated cross-exchange price disagreement, unhealthy production scan state, or repeated system errors;
- per-candidate execution gate requires reliable market consensus and reliable order-book evidence; rejects malformed/wide spreads, cross-exchange book-direction disagreement, insufficient visible depth at the requested size, and excessive current visible slippage;
- portfolio kill switch blocks new paper positions on >=10% drawdown, >=4 consecutive losing closes, malformed/non-finite account state, or >3 same-direction positions;
- paper status exposes global-risk WAIT state and reasons;
- new gates never create TRADE authority and cannot bypass validation/calibration/forward-proof/promotion requirements;
- first CI run found 2 legacy-fixture compatibility failures with 183 tests passing; the tests were isolated from the new execution gate rather than weakening production behavior; the final exact-head run passed.

ACC-009 thresholds must not be tuned to current paper P&L merely to keep trading active. Missing execution evidence may restrict a candidate rather than inventing liquidity.

## AUTHENTIC PAPER TRADING STATE
The continuous paper account remains forward-only and broker-disconnected. PR #52 established the authentic reset baseline at exactly `$100,000` on `2026-09-08T01:17:49Z`; only post-reset forward trades count. PR #62 fixed P&L reconciliation. PR #69 squash merge `15a48dda50fcdd34916c86f00fe021a07cc258a2` preserves immutable original `$100,000` starting capital while current account value moves with realized + open P&L. ACC-009 may stop new paper entries for portfolio risk but must never reset, rewrite or fabricate the ledger. Paper performance is evidence only and grants no live authority.

## ACCURACY PROGRAM STATUS
- ACC-001 market/execution realism — COMPLETE.
- ACC-002 cross-asset rank research — IN PROGRESS.
- ACC-003 causal regime-conditioned gating — COMPLETE.
- ACC-004 champion/challenger weighting — COMPLETE.
- ACC-005 provenance/freshness/contradiction gating — COMPLETE.
- ACC-006 forecast deterioration — COMPLETE.
- ACC-007 adversarial destruction hardening — COMPLETE.
- ACC-008 exact-fingerprint genuine forward proof — COMPLETE.
- ACC-009 global portfolio/execution risk gates — COMPLETE.

## COST / SPEED POLICY
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed by the user. Prefer existing shared Render compute, deterministic Python, public/free defensible data, caching/reuse, early rejection, bounded concurrency and event-driven work. Do not add a paid data feed, service or persistent compute without approval.

## BOOK-DERIVED MARKET-MICROSTRUCTURE ROADMAP
Larry Harris principles should be used as principles, not copied mechanically from 2002 traditional-market plumbing. Crypto-specific implementation must account for 24/7 trading, fragmented exchanges, perpetual funding/liquidations and exchange failure.

Highest-value remaining work:
1. `ACC-010` stricter execution/fill simulator and execution-intelligence layer. Separate alpha quality from execution quality. Model only observable/supportable spread, visible depth, size-dependent slippage, partial/insufficient fill, maker/taker economics, latency stress and conservative stop gaps. Never backfill current order-book snapshots into historical data.
2. Integrate the global/execution gate consistently across every action surface, including stored `trading_signals`, so no path can display TRADE while the Top-20 path says WAIT.
3. `ACC-012` multiple-testing / false-discovery firewall so the worker army cannot manufacture apparent edge by trying huge numbers of hypotheses.
4. `ACC-011` point-in-time universe / survivorship and delisting protection.
5. `ACC-013` genuine-forward shadow champion/challenger comparison with no challenger authority.
6. `ACC-014` disaster/failure injection: exchange/API timeout, stale/corrupt timestamps, DB outage, restarts, rate limits, extreme spikes and partial service failure; dangerous states => WAIT.

## EXACT NEXT STEP
1. Do not loosen ACC-008 or ACC-009 thresholds to make a strategy trade faster.
2. Start ACC-010 on a fresh isolated branch from current `main`: make paper/execution simulation size-aware using current reliable multi-exchange visible-depth/slippage evidence; do not extrapolate hidden liquidity; preserve existing open trades and the immutable $100k ledger.
3. Ensure all outward action surfaces use the same restrictive execution/global-risk decision.
4. Continue genuine 24h/7d ACC-002 evidence collection and worker-health monitoring in parallel; no profitability claim unless both horizon evidence gates support it.
5. Keep PONS fail-closed if independent history/confirmation is insufficient or contradictory.
6. Keep `live_promotions.json` empty and signing keys unused until the full chain genuinely passes.
7. After ACC-010, prioritize ACC-012, ACC-011, ACC-013 and ACC-014 in that order unless new evidence justifies reprioritization.
8. Never optimize headline accuracy alone; optimize after-cost risk-adjusted realized performance with drawdown/tail protection and explicit abstention.
9. Update this file after every completed integration/development cycle.
