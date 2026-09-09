# AI DEVELOPMENT STATE
Last updated: 2026-09-09

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file from current `main` in full before development. Never infer project state only from ChatGPT memory. Update this file after every completed development/integration cycle.

## CURRENT ARCHITECTURE
Production: GitHub -> Render -> Python/FastAPI V3 -> Supabase. Production scans run about every 15 minutes and produce separate 24h/7d Top-20 rankings. Cloud research/backtesting runs continuously on the existing Render coordinator with bounded heavy concurrency under the USD 30/month ceiling.

Research architecture includes the original 17 logical research workers plus continuous research-learning and experiment-factory roles from PR #104 and the bounded heavy experiment admission scheduler from PR #107. The scheduler prioritizes immutable predeclared research candidates without increasing total heavy concurrency or stealing the reserved ACC-002 lane.

Primary production Render service: `srv-dadliegu01pc73bc7t50` (`tradingview-ai-crypto`).
Continuous research coordinator: `srv-dafgtead0e5s73cc7ekg`.
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed.

Parallel ChatGPT development coordination exists through `AGENTS.md` / `docs/CHATGPT_SPECIALISTS.md`. The autonomous lead remains review-only with no automated merge authority to `main`.

## SAFETY INVARIANTS
No AI opinion, ranking score, evidence score, current order-book snapshot, paper P&L, ensemble weight, single OOS result, signed historical promotion, observability metric, supervisor status, diagnostic, incident fingerprint, canary result, risk-gate result, selective-precision result, research-memory lesson, experiment priority, saved market-consensus provenance, or shadow execution result by itself may authorize live BUY/SELL.

Mandatory chain:
RESEARCH -> BACKTEST -> VALIDATION -> UNTOUCHED OOS -> ROBUSTNESS/STABILITY -> MULTIPLE-TESTING FIREWALL -> POINT-IN-TIME UNIVERSE SAFETY -> STRATEGY-REGISTRY APPROVAL -> PRODUCTION-RISK APPROVAL -> GENUINE FORWARD PROOF -> GLOBAL/EXECUTION RISK CLEAR -> LIVE BUY/SELL.

Every later stage is restrictive-only. Missing, stale, contradictory, deteriorating, malformed, overlapping-only, insufficient, illiquid, execution-unsafe, portfolio-unsafe, statistically search-breadth-weak, survivorship-unsafe, identity-incomplete, or system-unsafe evidence means `WAIT / NO TRADE / RESEARCH_ONLY`.

`live_promotions.json` remains empty. Signing keys remain unused. Broker remains disconnected. Do not add credentials or real order capability without explicit user approval plus all canonical evidence gates.

## VALIDATION / CALIBRATION
Chronological validation remains train / validation / untouched holdout. Robustness includes deterministic bootstrap/Monte Carlo resampling, parameter perturbation, regime stability, conservative execution-cost stress and false-discovery/search-breadth penalties. Prediction ledger is append-only with fixed `due_at`; forward proof counts only non-overlapping full-horizon resolved forecasts for the exact immutable strategy fingerprint.

Evidence score is not probability. Never choose a production threshold by looking at untouched/forward outcomes and then treat that same evidence as confirmatory. Any future production selectivity change must be predeclared, restrictive-only, fingerprint-aware, and independently validated.

PR #116 prevents dense overlapping 15-minute forecast streams from inflating selective-precision confidence/readiness. Confidence/readiness use deterministic non-overlapping full-horizon rows reconstructed from immutable `due_at`, require `resolved_at >= due_at`, expose raw counts separately, and fail closed on malformed chronology.

PRs #122/#124 apply the same independence discipline to continuous research learning and experiment prioritization. PR #124 reconstructs forecast origin from immutable `due_at - declared horizon` because production intentionally has no `forecast_at`/`created_at` field; malformed/premature chronology remains excluded.

PR #123 completed future-only market-consensus provenance. New prediction-ledger rows freeze timestamped preforecast consensus context inside existing calibration JSON. Historical rows are never backfilled or fabricated, and agreement evidence has no trade/promotion authority.

PR #125 completed the current strategy-identity integrity hardening. Exact head `76818d665991d244b3f25df7b23829c94a32b225` passed Security and Reliability run `34318186208` (#951) and was squash-merged as `1f0cb1923b842861ac7a0d402ba594f1b67eb322`. Incomplete or unsupported strategy identities now set `identity_complete=false`, receive an empty fingerprint, and are rejected before promotion/forward-proof lookup. The identity policy itself is part of the research-code hash, intentionally creating fresh valid fingerprints after the policy change so old evidence cannot silently carry over. Stale PR #117 was closed as superseded.

## ACCURACY / RESEARCH PROGRAM
- ACC-001 MARKET / EXECUTION REALISM — COMPLETE.
- ACC-002 CROSS-ASSET RANK RESEARCH — IN PROGRESS. Dedicated 24h/7d workers continue genuine chronological/OOS/robustness evidence generation. No profitability claim authorized.
- ACC-003 through ACC-014 safety/validation layers — COMPLETE, including regime gating, champion/challenger, data provenance, deterioration, robustness, genuine forward proof, portfolio/execution risk, size-aware execution, point-in-time universe safety, multiple-testing firewall, shadow champion/challenger, and chaos/failure gates.
- SELECTIVE PRECISION — research-only; non-overlapping full-horizon evidence required.
- CONTINUOUS RESEARCH LEARNING / EXPERIMENT FACTORY — research-only; independent full-horizon windows required before diagnostic readiness or experiment-priority sample sufficiency.
- FUTURE-ONLY INDEPENDENT AGREEMENT EVIDENCE — accumulating prospectively from PR #123; no historical backfill and no precision claim yet.
- BOUNDED HEAVY EXPERIMENT SCHEDULER — active without heavy-concurrency increase or trade/promotion authority.

## OPERATIONS / RELIABILITY
The earlier production persistence incident caused by nonexistent `prediction_ledger.created_at` was fixed in PR #98. Repeated post-fix `/scan` requests remain 200.

Continuous AI observer rate-limit backoff from PR #100 remains active and does not affect scan/health availability.

Fresh live evidence after PR #124 and before PR #125 integration:
- both production and coordinator were live on commit `f1c7cb36f988d35b47bbfdb7e8ca2e64f7ef5075`;
- production `/health`, `/scan`, and `/evaluate` remained 200;
- cross-exchange batch collection still occasionally reports explicit `HTTPStatusError`, and scans can complete with a small number of symbol-level collection errors; these remain fail-closed and are never fabricated away;
- coordinator reached 2,748 completed worker jobs with 0 worker failures, 0 timeouts, 0 task restarts and about 95% cache hit rate;
- transient stale-worker canary alerts occurred for major workers, but cleared without crashes/restarts; the latest observed coordinator cycle before PR #125 was healthy with no stale/crashed workers and rollback recommendation false.

PR #125 auto-deployed successfully to both production and coordinator on exact merge `1f0cb1923b842861ac7a0d402ba594f1b67eb322`; both latest Render deploys were `live` after cutover. Verify a fresh post-deploy health/canary cycle before relying on the new identity policy operationally.

Cross-exchange batch collection can occasionally be unavailable. Never manufacture consensus/agreement data when source evidence is unavailable.

## AUTHENTIC PAPER TRADING STATE
The continuous paper account remains forward-only and broker-disconnected. Authentic baseline is exactly `$100,000` from `2026-09-08T01:17:49Z`; never reset or rewrite it. Current account value = immutable starting capital plus realized/open P&L. Safety/execution gates may reject entries but never fabricate or reset history. Paper performance is evidence only.

## COST / SPEED POLICY
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed. Prefer existing shared Render compute, deterministic Python, public/free defensible data, caching/reuse, early rejection and bounded concurrency. No paid feed/service/compute without approval.

Preserve stable exact strategy fingerprints while genuine forward observations accumulate. Challengers may run in shadow. Never count overlapping forecasts as independent, lower forward-proof thresholds, reset paper history, raise heavy concurrency, stretch cache TTLs, change market-data source behavior, or cherry-pick confidence thresholds merely to accelerate results.

## CURRENT OPEN DEVELOPMENT
Highest-value remaining specialist candidates must be refreshed from current main and rerun through fresh exact-head Security and Reliability before integration:
- PR #118 — suppress same-symbol opposite-direction cross-horizon paper self-hedging; next highest-value after-cost risk restriction.
- PR #113 — timestamp-safe Kraken public-book microstructure research snapshot; research-only/future evidence only.
- PR #115 — beta-neutral residual-momentum challenger; research-only and lower priority than evidence/risk integrity.
- PRs #120/#121 — coordination/autonomous cloud specialist runner work; review separately and preserve the $30/month ceiling and review-only/no-auto-merge safety model.
- stale PRs #105, #114, #117 and #119 are superseded/closed and must not be merged.

## EXACT NEXT STEP
1. Verify a fresh post-PR #125 production/coordinator cycle: production health/scan success, coordinator supervisor/canary healthy, and no new identity/persistence/chronology failures.
2. Refresh PR #118 directly onto current `main`, re-review the restrictive same-symbol opposite-direction cross-horizon paper-entry suppression, add/retain regression coverage, and require fresh exact-head Security and Reliability before merge.
3. Allow PR #123 future-only consensus provenance and new PR #125 strategy fingerprints to accumulate naturally. Do not backfill historical rows or claim improved precision/profitability until enough genuinely independent forward evidence resolves.
4. Continue ACC-002 genuine 24h/7d OOS/forward evidence and worker-health monitoring.
5. Preserve empty `live_promotions.json`, unused signing keys, broker-disconnected state, immutable $100k paper ledger, bounded heavy concurrency, and the USD 30/month ceiling.
6. Optimize after-cost risk-adjusted realized performance with abstention and tail protection, not headline accuracy.
