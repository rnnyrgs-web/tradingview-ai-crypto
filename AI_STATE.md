# AI DEVELOPMENT STATE
Last updated: 2026-09-08

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file before development. Never infer project state from ChatGPT memory. Update this file on `main` after every completed development/integration cycle.

## CURRENT ARCHITECTURE
Production: GitHub -> Render -> Python/FastAPI V3 -> Supabase.

Production scans run about every 15 minutes and produce separate 24h/7d Top-20 rankings. Cloud research/backtesting runs continuously through the existing bounded worker army. Intraday research targets a broad liquid OKX universe on 15m + 1H; swing research uses 4H + 1D. PONS is deliberately included when public data supports it, but must fail closed when data is insufficient or inconsistent.

There are 15 autonomous development roles: Lead Integrator plus 14 specialists. Specialists use isolated branches and do not write directly to `main`. Verified integration requires exact-head Security and Reliability success plus the existing review/integration safeguards.

## SAFETY INVARIANTS
No AI opinion, ranking score, evidence score, current order-book snapshot, paper P&L, ensemble weight, or single OOS result may authorize live BUY/SELL.

Mandatory chain:
RESEARCH -> BACKTEST -> VALIDATION -> UNTOUCHED OOS -> ROBUSTNESS/STABILITY -> STRATEGY-REGISTRY APPROVAL -> PRODUCTION-RISK APPROVAL -> LIVE BUY/SELL.

Missing, stale, contradictory, deteriorating, malformed, or insufficient evidence means `WAIT / NO TRADE / RESEARCH_ONLY`.

`live_promotions.json` remains intentionally empty. Promotion still requires repeated sealed robust evidence plus independent Strategy Registry and Production Risk approval. Signing keys remain unused until genuine evidence is complete.

## VALIDATION / CALIBRATION
Chronological validation remains train / validation / untouched holdout. Robustness includes deterministic bootstrap/Monte Carlo resampling, parameter perturbation, regime stability, and realistic execution costs.

Prediction ledger remains append-only with fixed `due_at`. Outcomes are resolved from market data at/after the deadline. Calibration is horizon + score-bin specific and can only restrict live eligibility.

## ACC-001 MARKET / EXECUTION REALISM — COMPLETE
Integrated earlier across PRs #38-#44 and follow-on validation work.

Key protections remain:
- realistic execution-cost stress including conservative multi-x cost scenarios;
- strict timestamp ordering and fail-closed malformed chronology;
- timestamp-safe funding/open-interest/basis evidence;
- current-book visible-depth fill/slippage estimates without inventing unseen liquidity;
- untouched-OOS execution robustness;
- research-only status until full promotion gates pass.

Repeated historical screening advanced only a small set of candidates to Strategy Registry review; it did not grant live authority.

## 24/7 RESEARCH / ORCHESTRATION
PR #55 added the bounded continuous Python research worker army on the existing paid Render coordinator. PRs #65-#68 strengthened dedicated 24h/7d ACC-002 evidence collection, reserved accuracy capacity, sufficient independent history, and bounded retry/cache behavior.

Current policy:
- existing paid infrastructure only unless user explicitly changes the budget;
- heavy subprocess concurrency remains bounded;
- deterministic Python and public/free market data are preferred;
- workers remain research-only with `trade_authority=false`, `write_authority=false`, `promotion_authority=false`, and `broker_connected=false`;
- USD 30/month recurring infrastructure ceiling remains in force.

## ACC-002 CROSS-ASSET RANK RESEARCH — IN PROGRESS
Integrated PRs #56-#60 and #64-#68.

Current ACC-002 protections include:
- timestamp-safe cross-sectional relative-strength ranking;
- multi-lookback momentum normalized by realized volatility;
- chronological train/validation/untouched OOS;
- split purging and non-overlapping forward observations;
- predeclared candidate grids chosen before OOS;
- sufficient independent OOS depth;
- parameter stability across nearby configurations;
- Top-15/Top-30/Top-45 liquidity-universe stability;
- 1x/1.5x/2x/3x execution-cost stress;
- deterministic 500-resample bootstrap confidence;
- dedicated nonstop 24h and 7d workers;
- bounded deep-history retry/cache reliability.

All ACC-002 outputs remain `research_only=true`, `live_approved=false`, `trade_authority=false`. Genuine forward/public-data evidence must continue accumulating; no profitability claim is authorized yet.

## ACC-003 REGIME-CONDITIONED STRATEGY GATING — COMPLETE
PR #70 `ACC-003: Add causal regime-conditioned strategy gating` passed exact-head Security and Reliability run `34252423032` on `c192affed37965f75f0972b608b965ae7c40084e` and was squash-merged as `606595e50f3057452714c50eb88e8178213ac5c8`.

Implemented:
- causal/trailing-only regimes: `TREND_UP`, `TREND_DOWN`, `HIGH_VOL`, `COMPRESSION`, `RANGE`;
- strategy regime eligibility frozen from train + validation before untouched holdout inspection;
- holdout/robustness evidence restricted to preselected proven regimes;
- no strategy may gain authority in a market state where it did not demonstrate pre-OOS edge;
- tests for no-lookahead classification, directional trend regimes, and rejection of unproven regimes.

## ACC-004 CHAMPION / CHALLENGER STRATEGY REGISTRY — COMPLETE
PR #71 `ACC-004: Add champion challenger ensemble weighting` passed exact-head Security and Reliability run `34256093230` on `e40ba49678e7726462df79fb16df6645b00396a0` and was squash-merged as `223bbd094e0ca8350f2673e94bec3d34a8836f87`.

Implemented:
- only strategies with >=3 distinct sealed robust OOS runs can enter the research ensemble;
- conservative quality score uses validation + untouched-holdout expectancy, profit factor, drawdown, and bounded sample confidence;
- chronological recent-deterioration penalty;
- severe deterioration => zero research weight / `DEMOTED`;
- correlation and structural-overlap penalties reduce duplicate exposure;
- per-strategy concentration cap;
- insufficient trustworthy candidates leave explicit `unallocated_wait_weight` rather than forcing weak strategies to fill 100%;
- one research `CHAMPION` plus `CHALLENGER` members;
- `live_approved=false` remains mandatory.

## ACC-005 PROVENANCE-AWARE MARKET DATA GATING — COMPLETE
PR #72 `ACC-005: Add provenance-aware market data gating` passed exact-head Security and Reliability run `34256741680` on `a4e5efe2fe0a0b6bcf89a735216abb37b9cd4651` and was squash-merged as `bb4c0e4060bba067e5bee1a86f1247d30901d19e`.

Implemented:
- independent market sources are counted by unique exchange, so duplicate quotes from one venue cannot fake confirmation;
- missing timestamps, future timestamps, and stale quotes are rejected;
- only the freshest valid observation per exchange is retained;
- explicit provenance records accepted/rejected exchanges and freshness/source quality;
- cross-exchange price contradiction collapses market-data confidence to zero;
- single-source evidence remains research-visible but restricted and cannot authorize a live action;
- opportunity evidence score and ranking can only be reduced by market-data quality;
- unreliable consensus always forces `WAIT`;
- legacy `MARKET_CONSENSUS_UNRELIABLE` marker is preserved for compatibility;
- PONS naturally remains fail-closed when a second independent source is unavailable.

## ACC-006 ROLLING FORECAST DETERIORATION — COMPLETE
PR #73 `ACC-006: Add rolling forecast deterioration gating` passed exact-head Security and Reliability run `34257098538` on `86b661a45817970ddaf91e56ffb469372125d20a` and was squash-merged as `ad3973d01fe94d52010cdd6628d9f85a9dc23a3d`.

Implemented:
- resolved prediction reads include `resolved_at` for chronological scoring;
- recent comparable forecasts are evaluated separately from prior history;
- default deterioration window compares the most recent 20 resolved comparable forecasts with at least 30 prior comparable forecasts;
- both Wilson lower bound and material precision-drop requirements are used to avoid reacting to tiny/noisy samples;
- recent collapse can block an otherwise acceptable long-run calibration result;
- insufficient deterioration evidence does not create authority or a false deterioration claim;
- 24h and 7d calibration summaries expose deterioration status separately;
- deterioration detection is restrictive only and cannot authorize a strategy.

## ACC-007 ADVERSARIAL STRATEGY-DESTRUCTION TESTING — COMPLETE
PR #74 `ACC-007: Add adversarial strategy destruction tests` passed exact-head Security and Reliability run `34257293281` on `59d7af5fcdbf8aee830f571a26f50488b81a6d58` and was squash-merged as `76d83786acf132b6cc848dacf0edf17acba2ed77`.

Implemented:
- robustness evaluation fails closed on NaN, Infinity, missing, or malformed OOS/parameter/regime return inputs;
- bounded Monte Carlo simulation-count validation;
- adversarial tests for catastrophic tail loss;
- parameter-collapse destruction test despite strong base OOS;
- single-regime dependence cannot substitute for multi-regime robustness;
- missing parameter/regime evidence fails closed;
- deterministic bootstrap behavior retained;
- these tests can only reject/demote research evidence, never promote or authorize live use.

## AUTHENTIC PAPER TRADING STATE
The continuous paper account remains forward-only and broker-disconnected.

PR #52 established the authentic reset baseline at exactly `$100,000` on `2026-09-08T01:17:49Z`. Only post-reset forward trades count as authentic evidence.

PR #62 fixed P&L reconciliation so current equity matches starting capital + realized P&L + open P&L.

PR #69 `Preserve authentic paper trading ledger` was squash-merged as `15a48dda50fcdd34916c86f00fe021a07cc258a2` and preserves the original `$100,000` baseline while `Current Account Value` moves with realized + open P&L. Starting capital must not be reset or rewritten.

Paper performance is evidence only. It does not authorize real-money trading.

## ACCURACY PROGRAM STATUS
- `ACC-001` market/execution realism — COMPLETE.
- `ACC-002` cross-asset rank research — IN PROGRESS; continue genuine 24h/7d evidence collection and horizon robustness.
- `ACC-003` causal regime-conditioned strategy gating — COMPLETE.
- `ACC-004` champion/challenger weighting + deterioration/correlation/concentration controls — COMPLETE.
- `ACC-005` provenance/freshness/contradiction market-data gating — COMPLETE.
- `ACC-006` continuous resolved-forecast deterioration gating — COMPLETE.
- `ACC-007` adversarial strategy-destruction hardening — COMPLETE.

## COST / SPEED POLICY
Hard recurring infrastructure ceiling: USD 30/month unless the user explicitly changes it.

Prefer:
- existing shared paid Render machine;
- deterministic Python;
- public/free defensible data;
- caching/reuse;
- early rejection of weak candidates;
- event-driven scheduling;
- reserved accuracy capacity;
- read-only parallel audits.

Do not buy another service, paid market-data feed, or additional persistent compute without explicit approval.

## EXACT NEXT STEP
1. Do NOT add more indicators/models merely for complexity. Measure whether ACC-003 through ACC-007 improve genuine forward accuracy and after-cost paper performance.
2. Inspect genuine 24h and 7d ACC-002 `/workers` evidence: supported liquidity subsets, pre-OOS stability, fixed candidate, whether OOS opened, independent OOS sample count, rank IC, 3x-cost top-minus-bottom spread, and bootstrap lower bounds. Do not claim profitability if either horizon gate fails.
3. Recheck continuous worker health and ensure both accuracy workers plus majors/PONS/universe/swing workers continue bounded progress without repeated timeout/failure.
4. Let the authentic `$100,000` forward-only paper ledger continue without reset. Track current account value, realized/open P&L, drawdown, win rate, expectancy, and calibration over a meaningful forward sample.
5. Use the immutable prediction ledger to monitor 24h/7d precision and recent deterioration. If deterioration triggers, restrict/WAIT rather than retuning on the same forward sample.
6. Keep PONS fail-closed when independent data confirmation/history is insufficient or contradictory.
7. Continue research only when a new hypothesis can be tested with predeclared rules, untouched OOS, robust costs, regime stability, and adversarial validation.
8. Keep `live_promotions.json` empty and signing keys unused until repeated robust evidence plus Strategy Registry and Production Risk approvals genuinely complete.
9. Never optimize for headline accuracy alone; optimize for after-cost risk-adjusted realized performance while preserving drawdown/tail protection and abstention when evidence is weak.
10. Update this file after every completed integration/development cycle.