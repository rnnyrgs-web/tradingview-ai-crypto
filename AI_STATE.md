# AI DEVELOPMENT STATE
Last updated: 2026-09-09

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file from `main` in full before development. Never infer current project state only from ChatGPT memory. Update this file on `main` after every completed development/integration cycle.

## CURRENT ARCHITECTURE
Production: GitHub -> Render -> Python/FastAPI V3 -> Supabase. Production scans run about every 15 minutes and produce separate 24h/7d Top-20 rankings. Cloud research/backtesting runs continuously on the existing Render coordinator with bounded heavy concurrency under the USD 30/month ceiling.

Research architecture now includes the original 17 logical research workers plus continuous research-learning and experiment-factory roles from PR #104. PR #107 adds a research-only heavy experiment admission scheduler that can prioritize immutable predeclared experiment candidates without increasing total heavy concurrency or stealing the reserved ACC-002 lane.

Primary production Render service: `srv-dadliegu01pc73bc7t50` (`tradingview-ai-crypto`).
Continuous research coordinator: `srv-dafgtead0e5s73cc7ekg`.
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed.

Parallel ChatGPT development coordination exists through `AGENTS.md` / `docs/CHATGPT_SPECIALISTS.md` from PR #108. The autonomous lead was hardened to review-only in PR #109/current main: no automated merge authority to `main`.

## SAFETY INVARIANTS
No AI opinion, ranking score, evidence score, current order-book snapshot, paper P&L, ensemble weight, single OOS result, signed historical promotion, observability metric, supervisor status, diagnostic, incident fingerprint, canary result, risk-gate result, selective-precision result, research-memory lesson, experiment priority, or shadow execution result by itself may authorize live BUY/SELL.

Mandatory chain:
RESEARCH -> BACKTEST -> VALIDATION -> UNTOUCHED OOS -> ROBUSTNESS/STABILITY -> MULTIPLE-TESTING FIREWALL -> POINT-IN-TIME UNIVERSE SAFETY -> STRATEGY-REGISTRY APPROVAL -> PRODUCTION-RISK APPROVAL -> GENUINE FORWARD PROOF -> GLOBAL/EXECUTION RISK CLEAR -> LIVE BUY/SELL.

Every later stage is restrictive-only. Missing, stale, contradictory, deteriorating, malformed, overlapping-only, insufficient, illiquid, execution-unsafe, portfolio-unsafe, statistically search-breadth-weak, survivorship-unsafe, or system-unsafe evidence means `WAIT / NO TRADE / RESEARCH_ONLY`.

`live_promotions.json` is verified empty. Signing keys remain unused. Broker remains disconnected. Do not add credentials or real order capability without explicit user approval plus all canonical evidence gates.

## VALIDATION / CALIBRATION
Chronological validation remains train / validation / untouched holdout. Robustness includes deterministic bootstrap/Monte Carlo resampling, parameter perturbation, regime stability, conservative execution-cost stress and false-discovery/search-breadth penalties. Prediction ledger is append-only with fixed `due_at`; forward proof counts only non-overlapping full-horizon resolved forecasts for the exact immutable strategy fingerprint.

Evidence score is not probability. Never choose a production threshold by looking at untouched/forward outcomes and then treating that same evidence as confirmatory. Any future production selectivity change must be predeclared, restrictive-only, fingerprint-aware, and independently validated.

PR #116 fixed a material statistical-independence weakness in selective-precision observability: dense overlapping 15-minute forecast streams can no longer inflate confidence/readiness sample counts. Confidence and readiness now use only deterministic non-overlapping full-horizon rows reconstructed from immutable `due_at`, require `resolved_at >= due_at`, expose raw row counts separately, and fail closed on malformed/missing chronology. Exact tested head `59999f08640caa481a948a66c31985885d42b0b7` passed Security and Reliability run `34306896512` (#871) and was squash-merged as `85cafaec2f8d4c39f179b709f99fd68937a5be3b`.

PR #122 extended the same independence protection to continuous research learning and experiment prioritization. Research-learning diagnostic readiness and priority scores now use conservative non-overlapping full-horizon forecast windows rather than raw overlapping scan rows; missing, malformed, or inverted forecast chronology cannot contribute to sample sufficiency. Raw precision remains descriptive only and every generated hypothesis remains research-only. PR #122 was recreated directly from post-PR-#116 main, exact head `0bdd45925ac0ac2b635ed4f38b1d20e97c62c699` passed Security and Reliability run `34310554965` (#930), and was squash-merged as `17cf8de392831ba6f76255c70d18e96b957fa3a2`. Stale PR #114 was closed as superseded.

## ACCURACY / RESEARCH PROGRAM
- ACC-001 MARKET / EXECUTION REALISM — COMPLETE.
- ACC-002 CROSS-ASSET RANK RESEARCH — IN PROGRESS. Dedicated 24h/7d workers continue genuine chronological/OOS/robustness evidence generation. No profitability claim authorized.
- ACC-003 through ACC-014 safety/validation layers — COMPLETE as previously integrated, including regime gating, champion/challenger, data provenance, deterioration, robustness, genuine forward proof, portfolio/execution risk, size-aware execution, point-in-time universe safety, multiple-testing firewall, shadow champion/challenger and chaos/failure gates.
- SELECTIVE PRECISION measurement — research-only. PRs #99/#101 created fixed-threshold descriptive measurement and protected observability; PR #116 enforces non-overlapping full-horizon evidence for confidence/readiness.
- CONTINUOUS RESEARCH LEARNING — PR #103 merged; PR #122 now requires independent full-horizon windows before diagnostic readiness or experiment-priority sample sufficiency. Advisory lessons remain research-only.
- CONTINUOUS EXPERIMENT FACTORY — PR #104 merged; immutable research hypotheses and prioritization are research-only, with PR #122 preventing overlapping-row inflation of priority readiness.
- BOUNDED HEAVY EXPERIMENT SCHEDULER — PR #107 merged; no heavy-concurrency increase and no trade/promotion authority.

## OPERATIONS / RELIABILITY
Production persistence incident caused by nonexistent `prediction_ledger.created_at` was fixed in PR #98. Repeated post-fix `/scan` requests remain 200.

Continuous AI observer rate-limit backoff from PR #100 remains active. Fresh live logs on 2026-09-09 showed `retry_in=600s` followed by `retry_in=1200s`, while `/health` remained 200 and `/scan` completed 200 with explicit symbol-level collection errors.

Latest live operational evidence before PR #122 integration:
- production and coordinator were both live on main commit `4f3939e6d20c7f86ac1f93694baad12913793138`;
- production `/health`: repeated 200 responses through approximately 04:19 UTC;
- production `/scan`: 200 at approximately 04:06 UTC; 3 symbol collection errors were reported explicitly rather than hidden;
- cross-exchange batch collection had an explicit `HTTPStatusError` in one observed cycle and remained fail-closed;
- coordinator supervisor: healthy, no stale/crashed workers or task restarts;
- worker failures/timeouts: 0 across 507 observed completed jobs in the latest window;
- cache hit rate warmed from cold-start levels to approximately 94-95%, with zero cache rejections and zero history failures;
- ACC-002 24h and 7d workers both continued exiting successfully in observed cycles, but no pass/profitability claim is authorized from those operational exits;
- deployment canary: healthy with no rollback recommendation.

After PR #122 merge, Render auto-deployment must be verified on the resulting main/state commits before treating the new research-learning independence behavior as live.

Cross-exchange batch collection can occasionally be unavailable (`HTTPStatusError`); this remains explicit and fail-closed. Do not manufacture agreement data when source evidence is unavailable.

## AUTHENTIC PAPER TRADING STATE
The continuous paper account remains forward-only and broker-disconnected. Authentic baseline is exactly `$100,000` from `2026-09-08T01:17:49Z`; never reset or rewrite it. Current account value = immutable starting capital plus realized/open P&L. Safety/execution gates may reject entries but never fabricate or reset history. Paper performance is evidence only.

## COST / SPEED POLICY
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed. Prefer existing shared Render compute, deterministic Python, public/free defensible data, caching/reuse, early rejection and bounded concurrency. No paid feed/service/compute without approval.

Preserve stable exact strategy fingerprints while genuine forward observations accumulate. Challengers may run in shadow. Never count overlapping forecasts as independent, lower forward-proof thresholds, reset paper history, raise heavy concurrency, stretch cache TTLs, change market-data source behavior, or cherry-pick confidence thresholds merely to accelerate results.

## CURRENT OPEN DEVELOPMENT
Several specialist PRs were created from pre-PR-#116 main (`0eb01380742c1373129a4bfef979627d3c31c40b`). Because `main` advanced with PRs #116 and #122, they must not be merged merely because an older exact-head CI run was green. Re-sync each candidate to current `main` and require fresh exact-head Security and Reliability before integration.

High-value candidates currently include:
- PR #119 — persist timestamp-safe future-only preforecast market-consensus provenance without historical backfill; highest-value next integration target because genuinely independent agreement evidence cannot be tested safely without timestamped future-only provenance.
- PR #117 — fail closed on incomplete strategy fingerprints; high scientific identity-integrity value, requires refresh.
- PR #118 — suppress same-symbol opposite-direction cross-horizon paper self-hedging; useful after-cost risk restriction, requires refresh.
- PR #113 — timestamp-safe Kraken public-book microstructure research snapshot; research-only, future evidence only, requires refresh.
- PR #115 — beta-neutral residual-momentum challenger; research-only and lower priority than evidence-integrity work, requires refresh.
- PRs #120/#121 — specialist coordination/autonomous cloud specialist runner work; stacked/review separately and do not merge out of order. Preserve the $30/month ceiling and review-only/no-auto-merge safety model.
- stale PR #105 is superseded by the merged current-main hardening in PR #109 and must not be merged.

## EXACT NEXT STEP
1. Refresh PR #119 onto the post-PR-#122 current `main`; preserve future-only timestamp-safe preforecast provenance, prohibit historical backfill/fabrication, and require fresh exact-head Security and Reliability before merge.
2. Re-evaluate PR #117 next for incomplete strategy-fingerprint fail-closed behavior, then PR #118 for same-symbol opposite-direction paper self-hedging; integrate only after current-main refresh and fresh exact-head CI.
3. Continue genuine ACC-002 24h/7d OOS/forward evidence and worker-health monitoring. No profitability or accuracy-improvement claim unless genuine independent evidence passes.
4. Preserve empty `live_promotions.json`, unused signing keys, broker-disconnected state, immutable $100k paper ledger, bounded heavy concurrency and the USD 30/month ceiling.
5. Optimize after-cost risk-adjusted realized performance with abstention and tail protection, not headline accuracy.
