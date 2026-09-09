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

Parallel ChatGPT development coordination exists through `AGENTS.md`, `docs/CHATGPT_SPECIALISTS.md`, and the persistent fail-closed `orchestration/specialist_coordination.json` queue integrated by PR #120. PR #121 adds one cost-bounded autonomous cloud specialist cycle that may only publish a candidate PR and wait for exact-head CI/manual Lead review. No specialist may auto-merge, write directly to main, connect a broker, increase recurring cost, or weaken canonical evidence gates.

## SAFETY INVARIANTS
No AI opinion, ranking score, evidence score, current order-book snapshot, paper P&L, ensemble weight, single OOS result, signed historical promotion, observability metric, supervisor status, diagnostic, incident fingerprint, canary result, risk-gate result, selective-precision result, research-memory lesson, experiment priority, saved market-consensus provenance, microstructure snapshot, residual-momentum challenger result, or shadow execution result by itself may authorize live BUY/SELL.

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

PR #125 completed strategy-identity integrity hardening. Exact head `76818d665991d244b3f25df7b23829c94a32b225` passed Security and Reliability run `34318186208` (#951) and was squash-merged as `1f0cb1923b842861ac7a0d402ba594f1b67eb322`. Incomplete or unsupported strategy identities receive no valid fingerprint and are rejected before promotion/forward-proof lookup.

PR #131 completed a fresh current-main rebuild of the beta-neutral residual-momentum challenger. Exact head `67b867929bc88843f79deb482af08856761e5c0e` passed Security and Reliability run `34338587228` (#979) and was squash-merged as `86146125d31c42dd33cce1a913e461e92075954f`. The challenger remains research-only, uses forecast-time closes only, keeps future returns as labels, and opens untouched OOS only after fixed train/validation preconditions against the canonical control. Unit tests include future-price mutation/no-lookahead, finite bounded beta, and fail-closed untouched-OOS regressions. No accuracy or profitability improvement is claimed from implementation integrity alone.

PR #133 fixed a confirmed research-observability contract defect without changing strategy behavior. Exact head `7d3a3e20fc543444bd5d6dd99912a04f0416538b` passed Security and Reliability run `34341508345` (#988) and was squash-merged as `deb312d4721976c19deec533615eb8c4538ef0e4`. The ACC-002 producer emits bounded `selected_oos` evidence and `history_network.network_latency_ms`; the coordinator had been reading nonexistent legacy keys, causing successful worker runs to appear as unknown and network latency to remain hidden. The coordinator now consumes the producer-shaped contract, distinguishes blocked research from missing telemetry, and still exposes no trade/promotion authority.

PR #135 completed bounded ACC-002 blocker diagnostics after genuine live evidence showed both 24h and 7d workers were repeatedly blocked before untouched OOS. Exact head `7acb9a2108d084ed3dd79d7734fa79eec9050573` passed Security and Reliability run `34346028939` (#998) and was squash-merged as `4c617cca60544010bb179c9c7b489fbb7791afc6`. Private coordinator logs expose only bounded already-produced evidence needed to diagnose the blocker. No research threshold, OOS gate, worker allocation, data source, strategy behavior, paper state, broker state, promotion authority or production signal behavior changed.

PR #136 fixed a confirmed follow-on ACC-002 observability-contract defect found from genuine post-#135 logs. Exact head `07aca6f5871f1c6f9c75a2bc88eb4cd146528e00` passed Security and Reliability run `34355922881` (#1004) and was squash-merged as `baa649f49e84067e80e5dce400d2ec6a35d41866`. The bounded worker summary exposes `supported_liquidity_subsets` and `failed_symbol_count` at the top level, while the coordinator had been looking for a nonexistent nested liquidity object/raw failure list. The coordinator now consumes the actual bounded summary contract and sources the unchanged predeclared 80% coverage constant directly from ACC-002 code. No liquidity threshold, OOS gate, strategy behavior, data source, worker allocation, paper state, broker state, promotion authority or production signal behavior changed.

## ACCURACY / RESEARCH PROGRAM
- ACC-001 MARKET / EXECUTION REALISM — COMPLETE.
- ACC-002 CROSS-ASSET RANK RESEARCH — IN PROGRESS and currently FAIL-CLOSED before untouched OOS. Fresh post-#136 24h evidence now proves only the predeclared Top-15 subset is supported: 24/30 requested assets resolved, `supported_liquidity_subsets=[15]`, canonical minimum subset coverage remains 0.80, failed-symbol count is 6, and untouched OOS remains unopened because two supported subsets are required. A genuine completed post-#136 7d summary is still required; immediately prior genuine 7d runs resolved only about 14-16/30 and remained blocked. There is no ACC-002 pass/fail, survivorship pass/fail, accuracy, or profitability conclusion yet. The beta-neutral residual-momentum challenger from PR #131 must not bypass this blocker or any canonical gate.
- ACC-003 through ACC-014 safety/validation layers — COMPLETE, including regime gating, champion/challenger, data provenance, deterioration, robustness, genuine forward proof, portfolio/execution risk, size-aware execution, point-in-time universe safety, multiple-testing firewall, shadow champion/challenger, and chaos/failure gates.
- SELECTIVE PRECISION — research-only; non-overlapping full-horizon evidence required.
- CONTINUOUS RESEARCH LEARNING / EXPERIMENT FACTORY — research-only; independent full-horizon windows required before diagnostic readiness or experiment-priority sample sufficiency.
- FUTURE-ONLY INDEPENDENT AGREEMENT EVIDENCE — accumulating prospectively from PR #123; no historical backfill and no precision claim yet.
- KRAKEN PUBLIC-BOOK MICROSTRUCTURE — PR #129 integrated as prospective research-only measurement. It summarizes only genuine timestamped public snapshots and exposes spread, top-level/visible-depth imbalance, visible quote depth and microprice. Stale/future/crossed/one-sided/malformed/policy-invalid books fail closed. No historical reconstruction, hidden-liquidity inference, trade authority, promotion authority, or profitability/accuracy claim.
- BOUNDED HEAVY EXPERIMENT SCHEDULER — active without heavy-concurrency increase or trade/promotion authority.

## OPERATIONS / RELIABILITY
The earlier production persistence incident caused by nonexistent `prediction_ledger.created_at` was fixed in PR #98. Repeated post-fix `/scan` requests remain 200.

Continuous AI observer rate-limit backoff from PR #100 remains active and does not affect scan/health availability. Fresh post-PR #127 startup again showed the bounded `RateLimitError` path with `retry_in=600s` rather than a tight retry loop.

PR #127 rebuilt stale PR #118 directly from current main. Exact head `ac72113cf504bd7cb03c7596476d15bf6f537c07` passed Security and Reliability run `34320626916` (#960) and was squash-merged as `aa59e04317ea4f824c9e59fe27eb26dd1de67227`. The paper engine now suppresses only a new opposite-direction same-symbol entry across 24h/7d horizons; it does not close, mutate, reset, or rewrite existing paper positions. Same-direction cross-horizon agreement remains allowed. Invalid candidate symbol/direction fails closed. Stale PR #118 was closed as superseded.

PR #129 rebuilt stale PR #113 directly from current main. Exact head `a842bb3200bd62dda4f03ac104594820ffdd4594` passed Security and Reliability run `34326555109` (#969) and was squash-merged as `ff979ff61afa37409dec5bb5c78fdca2a2c716f4`. Stale PR #113 was closed as superseded. The module is broker-disconnected and research-only and does not change production signal thresholds, fingerprints, paper behavior, paid-data policy, worker concurrency, or any live-trading authority.

PR #131 rebuilt stale PR #115 directly from current main. Exact head `67b867929bc88843f79deb482af08856761e5c0e` passed Security and Reliability run `34338587228` (#979) and was squash-merged as `86146125d31c42dd33cce1a913e461e92075954f`. Stale PR #115 was closed as superseded. The new module is research-only and does not change production signal thresholds, fingerprints, broker status, paper behavior, paid-data policy, worker concurrency, or any live-trading authority.

PR #133 repaired coordinator-only observability for genuine ACC-002 worker evidence and deep-history network latency. Regression coverage uses the exact producer field names, checks both selected-OOS and fail-closed blocked evidence, and confirms raw bootstrap/sample arrays are not copied into bounded private logs. No research thresholds, OOS gates, worker allocation, execution behavior, paper state, broker state, or production signals changed.

PR #135 is an observability-only follow-up to a genuine blocker, not a strategy change. PR #136 is an observability-only correction to PR #135. Regression coverage models the actual bounded producer summary shape, verifies top-level supported-subset and failed-count handling, retains sanitized failure-type aggregation compatibility, and confirms the threshold is the unchanged canonical 80% constant rather than a loosened diagnostic-only value.

PR #120 was refreshed onto the post-#136 main. Exact head `d56620ed0a74f650f87c679fadc8e9726f851f33` passed Security and Reliability run `34356132342` (#1007) and was merged as `b9765adabfa1dde0dae3aa747a406421292a3631`. It adds the persistent fail-closed specialist coordination queue and validation helper without auto-merge, broker connectivity, additional infrastructure/heavy concurrency, production threshold changes, or weakened validation gates.

PR #121 was then refreshed onto the PR #120 main. Exact head `6517155593ccf0738e35484c07ea18ec991edd51` passed Security and Reliability run `34356502033` (#1016) and was merged as `f4a5d9cfac8e70bf2cbd77c2f684aaceba5e6523`. It replaces the legacy scheduled multi-role swarm with a manual-only legacy workflow and adds one cost-bounded autonomous `data-market` specialist cycle scheduled every three hours. The model has no merge, broker, trading, shell, network, or credential tool; candidate publication is PR-only and exact-head CI/manual Lead review remains mandatory. The policy reserves a conservative project total below the canonical USD 30/month ceiling and does not change production strategy behavior or heavy Python research concurrency.

Live evidence after PR #133 and before PR #135:
- both genuine 24h and 7d ACC-002 workers repeatedly exited successfully but reported `research_blocked=true`, `research_blocked_reason=insufficient_supported_liquidity_subsets`, `untouched_oos_opened=false`, with ACC-002/survivorship/promotion fields unset rather than fabricated;
- this is a data/evidence-coverage blocker, not a failed untouched-OOS strategy result;
- at 2026-09-09T11:28Z the coordinator showed 1,028 completed jobs, 0 worker failures, 0 timeouts, 0 task restarts, no stale/crashed workers, supervisor healthy, about 93.7% cache hits, 336 deep-history fetches and 0 recorded deep-history network failures; trade/promotion/signal authority remained false;
- repeated healthy canary samples had rollback recommendation false.

Live verification after PR #135 and before PR #136:
- genuine runs showed 24h repeatedly resolving about 24-26 of 30 requested assets and 7d about 14-16 of 30, while both remained fail-closed with `insufficient_supported_liquidity_subsets` and untouched OOS unopened;
- deep-history network failures remained 0 and worker failures/timeouts/restarts remained 0, making a broad transient source-outage explanation unlikely;
- `supported_liquidity_subsets` and `minimum_subset_coverage` incorrectly appeared as `None` because the coordinator consumed the wrong bounded-summary shape; this confirmed the PR #136 observability defect rather than evidence that those producer fields were absent.

Live verification after PR #136 and descendants #120/#121:
- PR #136 deployed successfully; subsequent PR #120/#121 deployments inherited the fix and reached live with application startup complete and root requests returning 200;
- the first genuine corrected 24h diagnostic showed `universe_requested=30`, `universe_resolved=24`, `supported_liquidity_subsets=[15]`, `minimum_subset_coverage=0.8`, `failed_symbol_count=6`, `research_blocked=true`, and `untouched_oos_opened=false`;
- at that sample the coordinator was healthy with 89 completed worker jobs, 0 worker failures, 0 timeouts, 0 task restarts, no stale/crashed workers, 46 deep-history fetches and 0 deep-history failures; trade/promotion/signal authority remained false and canary rollback recommendation was false;
- aggregate failure-type cause is still unavailable in the bounded producer summary, so do not guess whether the six unresolved histories are mostly insufficient-history or request exceptions;
- wait for a genuine completed post-#136 7d summary before declaring its exact supported subsets.

Main branch protection is currently reported disabled by GitHub. Existing workflow-level fail-closed controls remain important, but repository branch/ruleset protection should be enabled separately for defense in depth when repository administration access is available.

Cross-exchange batch collection can occasionally be unavailable. Never manufacture consensus/agreement or microstructure data when source evidence is unavailable.

## AUTHENTIC PAPER TRADING STATE
The continuous paper account remains forward-only and broker-disconnected. Authentic baseline is exactly `$100,000` from `2026-09-08T01:17:49Z`; never reset or rewrite it. Current account value = immutable starting capital plus realized/open P&L. Safety/execution gates may reject entries but never fabricate or reset history. Paper performance is evidence only.

PR #127 is a restrictive after-cost paper-risk improvement only. It removes deterministic self-cancelling gross exposure/duplicate transaction-cost behavior when 24h and 7d signals disagree on the same asset. No profitability or signal-accuracy improvement is claimed until genuine forward paper evidence resolves.

## COST / SPEED POLICY
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed. Prefer existing shared Render compute, deterministic Python, public/free defensible data, caching/reuse, early rejection and bounded concurrency. No paid feed/service/compute without approval.

Preserve stable exact strategy fingerprints while genuine forward observations accumulate. Challengers may run in shadow. Never count overlapping forecasts as independent, lower forward-proof thresholds, reset paper history, raise heavy concurrency, stretch cache TTLs, change market-data source behavior, or cherry-pick confidence thresholds merely to accelerate results.

## CURRENT OPEN DEVELOPMENT
Persistent specialist task priorities live in `orchestration/specialist_coordination.json`; specialists must follow current-main queue ownership/dependencies and may not use coordination state to bypass evidence gates. PRs #120/#121 are integrated and must not be re-applied. Old PRs #105, #34, #33 and #13 remain stale/non-mergeable against current main and must not be merged as-is.

## EXACT NEXT STEP
1. Inspect the first genuine completed post-#136 7d ACC-002 summary. For both horizons, use only bounded `universe_requested`, `universe_resolved`, `supported_liquidity_subsets`, unchanged `minimum_subset_coverage=0.80`, `failed_symbol_count`, and genuinely available aggregate failure-type evidence. Do not lower the 80% coverage or two-subset requirement merely to open OOS.
2. Highest-information safe observability follow-up: extend the bounded ACC-002 producer summary to include aggregate `failure_type_counts` without symbol identities or raw samples, with regression tests and fresh exact-head Security and Reliability. This is diagnostic only and must not alter strategy behavior, history requirements, subset provenance, data source, or any OOS gate.
3. If aggregate failures prove mostly `InsufficientHistory`, remain fail-closed and let defensible coverage accumulate; never replace missing Top-N members with lower-ranked assets or fabricate history. If transient/request exceptions dominate, investigate the collection path and repair only confirmed defects.
4. Run the PR #131 beta-neutral residual-momentum challenger only as a predeclared ACC-002 research experiment after canonical ACC-002 data/evidence preconditions are satisfied. Preserve untouched OOS, non-overlap, cost stress, bootstrap robustness, point-in-time safety, multiple-testing accounting and genuine forward proof.
5. Allow PR #129 prospective timestamped microstructure measurements and PR #123 future-only consensus provenance to accumulate naturally. Do not reconstruct historical books, infer hidden liquidity, backfill consensus, or claim precision/profitability before enough independent forward evidence resolves.
6. Monitor authentic paper cycles for `cross_horizon_symbol_conflict` suppression without rewriting historical trades.
7. Preserve empty `live_promotions.json`, unused signing keys, broker-disconnected state, immutable $100k paper ledger, bounded heavy concurrency, and the USD 30/month ceiling.
8. Enable GitHub main branch/ruleset protection for defense in depth when repository-admin access is available; until then, preserve no-auto-merge and exact-head CI/manual review controls.
9. Optimize after-cost risk-adjusted realized performance with abstention and tail protection, not headline accuracy.