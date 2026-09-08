# AI DEVELOPMENT STATE
Last updated: 2026-09-08

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file from `main` before development. Never infer project state from ChatGPT memory. Update this file on `main` after every completed development/integration cycle.

## CURRENT ARCHITECTURE
Production: GitHub -> Render -> Python/FastAPI V3 -> Supabase. Production scans run about every 15 minutes and produce separate 24h/7d Top-20 rankings. Cloud research/backtesting runs continuously through the existing bounded Python worker army. PONS is included when public data supports it and must fail closed when evidence is insufficient or inconsistent. There are 15 autonomous development roles. Specialists use isolated branches and never write directly to `main`. Verified integration requires exact-head Security and Reliability success before merge.

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
Integrated PRs #56-#60 and #64-#68. Protections: timestamp-safe cross-sectional relative-strength ranking; multi-lookback momentum normalized by realized vol; chronological train/validation/untouched OOS; split purging; non-overlapping forward observations; predeclared candidate grids; sufficient independent OOS depth; nearby-parameter stability; Top-15/30/45 liquidity-subset stability; 1x/1.5x/2x/3x cost stress; deterministic 500-resample bootstrap; dedicated nonstop 24h and 7d workers; bounded deep-history retry/cache. All outputs remain research-only and no profitability claim is authorized yet.

## ACC-003 REGIME-CONDITIONED STRATEGY GATING — COMPLETE
PR #70 passed run `34252423032` on `c192affed37965f75f0972b608b965ae7c40084e`, squash merge `606595e50f3057452714c50eb88e8178213ac5c8`. Causal trailing-only regimes: TREND_UP, TREND_DOWN, HIGH_VOL, COMPRESSION, RANGE. Regime eligibility freezes before holdout.

## ACC-004 CHAMPION / CHALLENGER REGISTRY — COMPLETE
PR #71 passed run `34256093230` on `e40ba49678e7726462df79fb16df6645b00396a0`, squash merge `223bbd094e0ca8350f2673e94bec3d34a8836f87`. Requires >=3 distinct sealed robust OOS runs; conservative quality score; deterioration demotion; correlation/structural-overlap penalties; concentration cap; explicit unallocated WAIT weight; research champion/challengers only.

## ACC-005 PROVENANCE-AWARE MARKET DATA GATING — COMPLETE
PR #72 passed run `34256741680` on `a4e5efe2fe0a0b6bcf89a735216abb37b9cd4651`, squash merge `bb4c0e4060bba067e5bee1a86f1247d30901d19e`. Unique-exchange source counting, stale/future/missing rejection, freshest quote selection, contradiction collapse to zero confidence, single-source restriction, PONS fail-closed.

## ACC-006 ROLLING FORECAST DETERIORATION — COMPLETE
PR #73 passed run `34257098538` on `86b661a45817970ddaf91e56ffb469372125d20a`, squash merge `ad3973d01fe94d52010cdd6628d9f85a9dc23a3d`. Recent 20 comparable forecasts compared with >=30 prior; deterioration requires both weak Wilson lower bound and material precision drop and can only block.

## ACC-007 ADVERSARIAL STRATEGY-DESTRUCTION TESTING — COMPLETE
PR #74 passed run `34257293281` on `59d7af5fcdbf8aee830f571a26f50488b81a6d58`, squash merge `76d83786acf132b6cc848dacf0edf17acba2ed77`. Robustness fails closed on NaN/Infinity/missing/malformed evidence; tests catastrophic tails, parameter collapse, insufficient regime diversity and deterministic bootstrap behavior.

## ACC-008 GENUINE FORWARD-PROOF PROMOTION GATE — COMPLETE
PR #75 passed run `34258912558` on `d47870757d4fdb846a8afadd3fab5835549a29d2`, squash merge `cf66104242467c8cf1177c91e20db206c92f62e5`. Exact immutable fingerprint; non-overlapping full-horizon observations; >=20 independent 24h or >=12 independent 7d; 3x modeled cost; positive after-cost expectancy; Wilson 95% lower >=50%; max compounded forward DD <=12%; no recent deterioration. Wrong fingerprint, malformed chronology, overlapping-only evidence or weak statistics fail closed.

## ACC-009 GLOBAL PORTFOLIO / EXECUTION RISK GATES — COMPLETE
PR #76 passed exact-head run `34264596759` on `285add1ac65903432d8ed4ffaa19aba149f2aa3d`, squash merge `4f70e89f81b4f16df39d4fd2fe88b3c0f298d6f5`.

Restrictive-only Larry Harris-inspired gates:
- global WAIT on broad abnormal volatility, widespread liquidity/spread stress, repeated cross-exchange price disagreement, unhealthy production scan state, or repeated system errors;
- per-candidate execution gate requires reliable market consensus/order-book evidence and rejects malformed/wide spreads, cross-exchange book disagreement, insufficient visible depth and excessive visible slippage;
- paper portfolio kill switch blocks new positions at >=10% drawdown, >=4 consecutive losing closes, malformed/non-finite account state, or >3 same-direction positions;
- no gate creates TRADE authority.

## ACC-010 SIZE-AWARE EXECUTION SIMULATION — COMPLETE
PR #77 `ACC-010: Add size-aware execution simulation` passed exact-head Security and Reliability run `34265226943` on `324fc08f4723190df50e01d28e608e506d3fec95` and was squash-merged as `edbed73a7b4236234ea2ff958e94ca2510db2df1`.

Implemented:
- new current-snapshot execution simulator requires >=2 reliable independent exchange books with complete fills at a supported notional tier;
- chooses the smallest supported tier at or above requested paper size and uses the worse independently observed execution price, plus explicit one-way fee friction;
- never extrapolates hidden liquidity above the largest observed tier and never backfills current order-book state into historical testing;
- authentic paper entries fail closed when current size-aware execution evidence is unavailable;
- paper engine opens only opportunities already marked `TRADE`; WAIT rows cannot become paper positions;
- risk sizing is computed before execution request and recalculated from the actual adverse simulated fill without exceeding supported visible notional;
- stop gaps use the actually worse observed price, while favorable target gaps are capped at the predefined target so paper results are not optimistically over-credited;
- `paper_status` exposes size-aware execution and two-book requirements;
- stored `trading_signals` now apply the same global/execution risk gates as the Top-20 opportunity path and persist those risk reasons/metrics in raw analysis;
- all changes remain broker-disconnected, research-only, restrictive-only, and preserve the original paper ledger.

## AUTHENTIC PAPER TRADING STATE
The continuous paper account remains forward-only and broker-disconnected. PR #52 established the authentic baseline at exactly `$100,000` on `2026-09-08T01:17:49Z`; only post-reset forward trades count. PR #62 fixed P&L reconciliation. PR #69 squash merge `15a48dda50fcdd34916c86f00fe021a07cc258a2` preserves immutable `$100,000` starting capital while current account value moves with realized + open P&L. ACC-009/010 may reject new paper entries but must never reset, rewrite or fabricate the ledger. Paper performance is evidence only and grants no live authority.

## ACCURACY PROGRAM STATUS
- ACC-001 market/execution realism — COMPLETE.
- ACC-002 cross-asset rank research — IN PROGRESS.
- ACC-003 causal regime gating — COMPLETE.
- ACC-004 champion/challenger registry — COMPLETE.
- ACC-005 market-data provenance gating — COMPLETE.
- ACC-006 forecast deterioration — COMPLETE.
- ACC-007 adversarial destruction hardening — COMPLETE.
- ACC-008 genuine forward proof — COMPLETE.
- ACC-009 global portfolio/execution risk gates — COMPLETE.
- ACC-010 size-aware execution simulation/action consistency — COMPLETE.

## COST / SPEED POLICY
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed by the user. Prefer existing shared Render compute, deterministic Python, public/free defensible data, caching/reuse, early rejection, bounded concurrency and event-driven work. Do not add a paid data feed, service or persistent compute without approval.

## BOOK-DERIVED MARKET-MICROSTRUCTURE ROADMAP
Use Larry Harris principles, not obsolete 2002 exchange plumbing. Crypto-specific implementation must account for 24/7 trading, fragmented venues, perpetual funding/liquidations and exchange failure.

Highest-value remaining work:
1. `ACC-012` multiple-testing / false-discovery firewall so the worker army cannot manufacture apparent edge by trying huge numbers of hypotheses.
2. `ACC-011` point-in-time universe / survivorship and delisting protection.
3. `ACC-013` genuine-forward shadow champion/challenger comparison with no challenger authority.
4. `ACC-014` disaster/failure injection: exchange/API timeout, stale/corrupt timestamps, DB outage, restarts, rate limits, extreme spikes and partial service failure; dangerous states => WAIT.
5. Later execution refinements only when supportable data exists: maker/limit queue and fill-probability modeling, latency measurements and adverse-selection estimation. Do not invent these from candle data.

## EXACT NEXT STEP
1. Do not loosen ACC-008/009/010 merely to increase trade count.
2. Start `ACC-012` on a fresh isolated branch from current `main`: count distinct strategy/parameter/hypothesis trials and increase required evidence as search breadth grows; it must only reject/demote and never create authority.
3. Continue genuine 24h/7d ACC-002 evidence and worker-health monitoring; no profitability claim unless both horizon evidence gates support it.
4. Keep PONS fail-closed when independent history/confirmation is insufficient or contradictory.
5. Keep `live_promotions.json` empty and signing keys unused until the full chain genuinely passes.
6. After ACC-012, implement ACC-011, ACC-013, ACC-014.
7. Never optimize headline accuracy alone; optimize after-cost risk-adjusted realized performance with drawdown/tail protection and explicit abstention.
8. Update this file after every completed integration/development cycle.
