# AI DEVELOPMENT STATE
Last updated: 2026-09-09

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file from `main` in full before development. Never infer current project state only from ChatGPT memory. Update this file on `main` after every completed development/integration cycle.

## CURRENT ARCHITECTURE
Production: GitHub -> Render -> Python/FastAPI V3 -> Supabase. Production scans run about every 15 minutes and produce separate 24h/7d Top-20 rankings. Cloud research/backtesting runs continuously on the existing Render coordinator with bounded heavy concurrency under the USD 30/month ceiling.

Research architecture includes the original 17 logical research workers plus continuous research-learning and experiment-factory roles from PR #104. PR #107 adds a research-only heavy experiment admission scheduler that prioritizes immutable predeclared experiment candidates without increasing total heavy concurrency or stealing the reserved ACC-002 lane.

Primary production Render service: `srv-dadliegu01pc73bc7t50` (`tradingview-ai-crypto`).
Continuous research coordinator: `srv-dafgtead0e5s73cc7ekg`.
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed.

Parallel ChatGPT development coordination exists through `AGENTS.md` / `docs/CHATGPT_SPECIALISTS.md` from PR #108. The autonomous lead was hardened to review-only in PR #109/current main: no automated merge authority to `main`.

## SAFETY INVARIANTS
No AI opinion, ranking score, evidence score, current order-book snapshot, paper P&L, ensemble weight, single OOS result, signed historical promotion, observability metric, supervisor status, diagnostic, incident fingerprint, canary result, risk-gate result, selective-precision result, research-memory lesson, experiment priority, saved market-consensus provenance, or shadow execution result by itself may authorize live BUY/SELL.

Mandatory chain:
RESEARCH -> BACKTEST -> VALIDATION -> UNTOUCHED OOS -> ROBUSTNESS/STABILITY -> MULTIPLE-TESTING FIREWALL -> POINT-IN-TIME UNIVERSE SAFETY -> STRATEGY-REGISTRY APPROVAL -> PRODUCTION-RISK APPROVAL -> GENUINE FORWARD PROOF -> GLOBAL/EXECUTION RISK CLEAR -> LIVE BUY/SELL.

Every later stage is restrictive-only. Missing, stale, contradictory, deteriorating, malformed, overlapping-only, insufficient, illiquid, execution-unsafe, portfolio-unsafe, statistically search-breadth-weak, survivorship-unsafe, or system-unsafe evidence means `WAIT / NO TRADE / RESEARCH_ONLY`.

`live_promotions.json` is verified empty. Signing keys remain unused. Broker remains disconnected. Do not add credentials or real order capability without explicit user approval plus all canonical evidence gates.

## VALIDATION / CALIBRATION
Chronological validation remains train / validation / untouched holdout. Robustness includes deterministic bootstrap/Monte Carlo resampling, parameter perturbation, regime stability, conservative execution-cost stress and false-discovery/search-breadth penalties. Prediction ledger is append-only with fixed `due_at`; forward proof counts only non-overlapping full-horizon resolved forecasts for the exact immutable strategy fingerprint.

Evidence score is not probability. Never choose a production threshold by looking at untouched/forward outcomes and then treating that same evidence as confirmatory. Any future production selectivity change must be predeclared, restrictive-only, fingerprint-aware, and independently validated.

PR #116 fixed a material statistical-independence weakness in selective-precision observability: dense overlapping 15-minute forecast streams can no longer inflate confidence/readiness sample counts. Confidence and readiness use deterministic non-overlapping full-horizon rows reconstructed from immutable `due_at`, require `resolved_at >= due_at`, expose raw row counts separately, and fail closed on malformed/missing chronology. Exact tested head `59999f08640caa481a948a66c31985885d42b0b7` passed Security and Reliability run `34306896512` (#871) and was squash-merged as `85cafaec2f8d4c39f179b709f99fd68937a5be3b`.

PR #122 extended overlapping-sample protection to continuous research learning and experiment prioritization. Exact head `0bdd45925ac0ac2b635ed4f38b1d20e97c62c699` passed Security and Reliability run `34310554965` (#930) and was squash-merged as `17cf8de392831ba6f76255c70d18e96b957fa3a2`; stale PR #114 was closed.

A follow-on production-shape defect was then identified: PR #122 initially expected `forecast_at`, but production `prediction_ledger` intentionally has no `forecast_at`/`created_at`. This was fail-closed but would keep real research-learning independent sample counts at zero. PR #124 corrected that by reconstructing forecast origin from immutable `due_at - declared horizon`, mirroring the validated PR #116 method; it requires known 24h/7d horizon and `resolved_at >= due_at`, and malformed/premature chronology remains excluded. Exact head `2848b6ef14fec497d2bc7a7e6b329be196809d2f` passed Security and Reliability run `34311111054` (#943) and was squash-merged as `a27906ea99f105723d62e961a0de8175d3a6aecd`.

PR #123 completed the future-only market-consensus provenance layer. New prediction-ledger rows now freeze timestamped preforecast consensus context inside the existing `calibration` JSON; quote timestamps and accepted exchange identities are retained, and resolved research exposes `market_consensus_reliable` only when every accepted observation is provably no later than the saved capture time. Historical rows are never backfilled or fabricated. Exact head `2ac7ab7ef250f1c2b3ea39c2ef8df08e97132ef8` passed Security and Reliability run `34310936643` (#938) and was squash-merged as `f1749e3d794faaac2e4ed30aba9c8a081a75fd06`; stale PR #119 was closed.

## ACCURACY / RESEARCH PROGRAM
- ACC-001 MARKET / EXECUTION REALISM — COMPLETE.
- ACC-002 CROSS-ASSET RANK RESEARCH — IN PROGRESS. Dedicated 24h/7d workers continue genuine chronological/OOS/robustness evidence generation. No profitability claim authorized.
- ACC-003 through ACC-014 safety/validation layers — COMPLETE as previously integrated, including regime gating, champion/challenger, data provenance, deterioration, robustness, genuine forward proof, portfolio/execution risk, size-aware execution, point-in-time universe safety, multiple-testing firewall, shadow champion/challenger and chaos/failure gates.
- SELECTIVE PRECISION measurement — research-only. PRs #99/#101 created fixed-threshold descriptive measurement and protected observability; PR #116 enforces non-overlapping full-horizon evidence for confidence/readiness.
- CONTINUOUS RESEARCH LEARNING — PR #103 merged; PRs #122/#124 require production-compatible independent full-horizon windows before diagnostic readiness or experiment-priority sample sufficiency. Advisory lessons remain research-only.
- CONTINUOUS EXPERIMENT FACTORY — PR #104 merged; immutable research hypotheses and prioritization are research-only, with PRs #122/#124 preventing overlapping-row inflation while retaining usable production chronology.
- FUTURE-ONLY INDEPENDENT AGREEMENT EVIDENCE — PR #123 merged. Timestamp-safe preforecast market-consensus context can now accumulate prospectively for later OOS/forward study; it does not change current production signal authority.
- BOUNDED HEAVY EXPERIMENT SCHEDULER — PR #107 merged; no heavy-concurrency increase and no trade/promotion authority.

## OPERATIONS / RELIABILITY
Production persistence incident caused by nonexistent `prediction_ledger.created_at` was fixed in PR #98. Repeated post-fix `/scan` requests remain 200.

Continuous AI observer rate-limit backoff from PR #100 remains active. Recent live logs showed bounded retries while production health remained unaffected.

Fresh operational evidence during the PR #122/#123 integration window:
- PR #122 and its AI_STATE follow-up auto-deployed successfully to both production and coordinator;
- production `/health` and root remained 200 after cutover;
- coordinator restarted cleanly; supervisor remained healthy with no stale/crashed workers or task restarts and canary returned to healthy after warming;
- immediately before PR #122, 507 completed worker jobs were observed with 0 failures/timeouts and approximately 94-95% warmed cache hit rate, zero cache rejections and zero history failures;
- PR #123 merge `f1749e3d794faaac2e4ed30aba9c8a081a75fd06` auto-deployed successfully to production; application startup completed, `/health` returned 200, and a fresh `/scan` at approximately 04:28 UTC returned 200;
- that scan still reported 3 symbol-level collection errors and one cross-exchange `HTTPStatusError` was observed; both remain explicit/fail-closed rather than fabricated away;
- the AI observer continued bounded rate-limit backoff (`retry_in=600s`) without affecting scan/health availability.

PR #124 is merged after exact-head green CI. Verify its final main/AI_STATE auto-deployment and a fresh coordinator health cycle before assuming production research-learning diagnostics are fully live on the corrected due-at reconstruction.

Cross-exchange batch collection can occasionally be unavailable (`HTTPStatusError`); this remains explicit and fail-closed. Never manufacture agreement data when source evidence is unavailable.

## AUTHENTIC PAPER TRADING STATE
The continuous paper account remains forward-only and broker-disconnected. Authentic baseline is exactly `$100,000` from `2026-09-08T01:17:49Z`; never reset or rewrite it. Current account value = immutable starting capital plus realized/open P&L. Safety/execution gates may reject entries but never fabricate or reset history. Paper performance is evidence only.

## COST / SPEED POLICY
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed. Prefer existing shared Render compute, deterministic Python, public/free defensible data, caching/reuse, early rejection and bounded concurrency. No paid feed/service/compute without approval.

Preserve stable exact strategy fingerprints while genuine forward observations accumulate. Challengers may run in shadow. Never count overlapping forecasts as independent, lower forward-proof thresholds, reset paper history, raise heavy concurrency, stretch cache TTLs, change market-data source behavior, or cherry-pick confidence thresholds merely to accelerate results.

## CURRENT OPEN DEVELOPMENT
Remaining high-value older specialist candidates must be refreshed from current main and rerun through fresh exact-head Security and Reliability before integration:
- PR #117 — fail closed on incomplete strategy fingerprints; highest-value next scientific identity-integrity target.
- PR #118 — suppress same-symbol opposite-direction cross-horizon paper self-hedging; useful after-cost risk restriction after identity integrity.
- PR #113 — timestamp-safe Kraken public-book microstructure research snapshot; research-only/future evidence only.
- PR #115 — beta-neutral residual-momentum challenger; research-only and lower priority than evidence-integrity work.
- PRs #120/#121 — specialist coordination/autonomous cloud specialist runner work; stacked/review separately. Preserve the $30/month ceiling and review-only/no-auto-merge safety model.
- stale PRs #105, #114 and #119 are superseded/closed and must not be merged.

## EXACT NEXT STEP
1. Verify PR #124 and this AI_STATE commit auto-deploy cleanly to production/coordinator; require healthy supervisor/canary and no new persistence/chronology failure.
2. Refresh PR #117 onto the resulting current `main`, confirm incomplete strategy fingerprints fail closed, add/retain regression coverage, and require fresh exact-head Security and Reliability before merge.
3. Then re-evaluate PR #118 for same-symbol opposite-direction cross-horizon paper self-hedging and integrate only after current-main refresh/fresh CI.
4. Allow PR #123 future-only consensus provenance to accumulate naturally. Do not backfill historical rows and do not claim agreement improves precision until enough genuinely independent forward evidence resolves.
5. Continue genuine ACC-002 24h/7d OOS/forward evidence and worker-health monitoring. No profitability or accuracy-improvement claim unless genuine independent evidence passes.
6. Preserve empty `live_promotions.json`, unused signing keys, broker-disconnected state, immutable $100k paper ledger, bounded heavy concurrency and the USD 30/month ceiling.
7. Optimize after-cost risk-adjusted realized performance with abstention and tail protection, not headline accuracy.
