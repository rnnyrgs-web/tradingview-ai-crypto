# AI DEVELOPMENT STATE
Last updated: 2026-09-09

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file from current `main` in full before development. Never infer project state only from ChatGPT memory. Update this file after each completed integration cycle.

## CURRENT MAIN / ARCHITECTURE
Current tested integration baseline after PR #181: `15d40568a250b3d6ac5d71e19bc1a1bf25e91c20`.

Production: GitHub -> Render -> Python/FastAPI V3 -> Supabase. Production scans run about every 15 minutes and produce separate 24h/7d Top-20 rankings. Continuous research/backtesting runs on the existing Render coordinator with bounded heavy concurrency under the USD 30/month recurring-infrastructure ceiling.

Primary production Render service: `srv-dadliegu01pc73bc7t50` (`tradingview-ai-crypto`).
Continuous research coordinator: `srv-dafgtead0e5s73cc7ekg`.
Supabase project used by production/research persistence: `dxgksvzibucwuzmppoqy`.
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed.

The always-on research architecture includes:
- bounded Python workers;
- autonomous research-director coordination;
- deterministic quant-science experiment factory;
- fail-closed heavy-experiment admission firewall;
- adaptive-accuracy lane sharing the existing heavy accuracy slot;
- 256 active token-free logical specialists per refresh from a much larger deterministic virtual namespace;
- durable research memory in Supabase;
- live read-only adaptive evidence observability including the durable conclusive-trial counter.

Logical scale must never be confused with physical compute scale. Heavy experiment concurrency remains capped at one admitted heavy experiment at a time unless a separately reviewed change explicitly proves a safe/cost-valid reason to alter it.

## SAFETY INVARIANTS
No AI opinion, ranking score, evidence score, current order-book snapshot, paper P&L, ensemble weight, single OOS result, historical promotion, observability metric, diagnostic, research-memory lesson, experiment priority, market-consensus provenance, microstructure snapshot, residual-momentum result, adaptive-accuracy result, shadow execution result, virtual-specialist result, or paper result by itself may authorize live BUY/SELL.

Mandatory chain:
RESEARCH -> BACKTEST -> VALIDATION -> UNTOUCHED OOS -> ROBUSTNESS/STABILITY -> MULTIPLE-TESTING FIREWALL -> POINT-IN-TIME UNIVERSE SAFETY -> STRATEGY-REGISTRY APPROVAL -> PRODUCTION-RISK APPROVAL -> GENUINE FORWARD PROOF -> GLOBAL/EXECUTION RISK CLEAR -> LIVE BUY/SELL.

Every later stage is restrictive-only. Missing, stale, contradictory, deteriorating, malformed, overlapping-only, insufficient, illiquid, execution-unsafe, portfolio-unsafe, statistically weak, survivorship-unsafe, identity-incomplete, persistence-unsafe, label-unsafe, chronology-unsafe, or system-unsafe evidence means `WAIT / NO TRADE / RESEARCH_ONLY`.

`live_promotions.json` remains empty. Signing keys remain unused. Broker remains disconnected. Do not add credentials or real-order capability without explicit user approval plus all canonical evidence gates.

Authentic paper account baseline remains exactly `$100,000` from `2026-09-08T01:17:49Z`. Never reset, rewrite, replace, or manufacture its history. Paper performance is evidence only.

## SCIENTIFIC RESEARCH DISCIPLINE
Chronological validation remains train/development -> validation -> untouched holdout/OOS. Robustness includes deterministic bootstrap/Monte Carlo resampling, parameter perturbation, regime stability, conservative execution-cost stress, search-breadth protection, and genuine forward confirmation. Forward proof counts only non-overlapping full-horizon resolved forecasts for the exact immutable strategy fingerprint.

Core invariants:
- no lookahead or leakage;
- no threshold/parameter mining against untouched OOS;
- no OOS reuse as fresh confirmation;
- no pooling historical/OOS evidence with genuine-forward evidence to inflate confidence;
- no survivorship substitution for missing point-in-time universe evidence;
- no backfilling prospective order-book/consensus features;
- realistic fees, spread, slippage and execution assumptions remain mandatory;
- repeated/disproven hypotheses receive a research-memory penalty rather than blind recycling;
- idea generation is not evidence;
- missing durable research memory must fail the adaptive lane closed rather than reset prior trials;
- overlapping forecasts must never be treated as independent observations;
- malformed, missing, or delayed outcome chronology must fail closed instead of fabricating labels or sample independence.

PR #149 introduced `UNIVERSAL_SIGNAL_DEVELOPMENT_V1`, the canonical machine-readable objective: optimize genuine forward 24h/7d BUY/SELL/WAIT quality and positive after-cost expectancy, not headline historical accuracy.

PR #155 added the deterministic quant-science factory with predeclared methods/endpoints, minimum effects, one-search budgets, no-parameter-mining/no-OOS-reuse rules, and bounded per-method breadth.

PR #158 added the adaptive research evaluator: hypotheses originate on development evidence, are frozen before validation, and untouched OOS remains sealed unless the predeclared validation gate passes.

PR #160 added the autonomous 24/7 research-director coordination layer. It coordinates missions and scarce compute but has no production-promotion authority.

PR #163 bridges safe logical-specialist diagnoses into the quant experiment factory so useful resolved-error hypotheses can enter the same governed scientific queue.

PR #164 hardened massive virtual research with a fail-closed firewall. Every admitted quant-science design must remain research-only and satisfy one predeclared search, one candidate mutation, no parameter mining, no untouched-OOS reuse, no OOS/forward pooling, mandatory multiple-testing protection, independent replication, genuine-forward replication, duplicate-hypothesis penalties, no paid-compute escalation by default, and no trade/promotion/strategy-mutation authority. Heavy concurrency remains one.

PR #165 scales token-free logical research to 256 active deterministic specialists per refresh while retaining one shared immutable-ledger read and zero normal-operation AI calls.

PR #167 surfaces adaptive-accuracy evidence through read-only research observability.

PR #168 enforces durable sequential multiple-testing before adaptive OOS admission using a monotonic conclusive-trial count and sequential alpha spending. Production research memory is persisted in the existing Supabase project and fails closed if the configured persistent store is unavailable.

PR #170 increases cloud-specialist eligibility checks from every three hours to hourly while preserving the 12-hour successful-run cooldown, one concurrent/model run, the $1/day runner API budget, the $30/month recurring-infrastructure ceiling, review-only Lead behavior, no automatic merge, and no trade authority.

PR #172 exposes the durable adaptive `conclusive_trial_count` in live read-only research evidence. It does not change research thresholds, OOS gates, costs, or authority.

PR #173 fixes logical specialists to consume the actual live prediction-ledger vocabulary: production LONG/SHORT directions, live regime labels, and WAIT from `action_at_forecast`, while retaining legacy compatibility and stable specialist identities.

PR #175 fixes live calibration independence: calibration readiness, Wilson confidence, and deterioration checks now use deterministic full-horizon non-overlapping forecasts reconstructed from immutable `due_at - horizon`; missing/malformed chronology does not count as evidence.

PR #176 fixes genuine forward-proof chronology for the production ledger: origin is reconstructed from immutable `due_at - horizon`, `resolved_at >= due_at` is required, and overlapping full-horizon windows are deterministically de-overlapped without outcome-based selection.

PR #177 applies the same full-horizon non-overlap discipline to shadow-readiness evidence and fails closed when immutable due chronology is unavailable.

PR #178 applies exact matched, full-horizon, non-overlapping windows to champion/challenger shadow competition, matching strategies only on exact due endpoints rather than calendar buckets.

PR #179 hardens prediction-outcome label integrity. The prediction evaluator now accepts the first 1H candle at/after the forecast deadline only within an explicit 2-hour maximum lag; a stale delayed candle leaves the prediction unresolved instead of creating a contaminated outcome label. This changes no strategy, calibration threshold, OOS gate, trade authority, or promotion authority.

PR #181 fixes a live paper-cycle reliability defect found after the PR #179 deployment. `paper_signal_decisions` writes now declare `on_conflict=signal_key` together with `resolution=ignore-duplicates`, so re-processing an already-recorded paper decision is idempotent instead of aborting the cycle with a Supabase 409 unique-key error. This does not rewrite the authentic paper ledger, change account values, alter strategy logic, or add trade/promotion authority.

No accuracy or profitability improvement is claimed merely because these infrastructure/scientific changes exist. Any such claim still requires independent evidence through the canonical chain.

## ACCURACY / RESEARCH PROGRAM
- ACC-001 MARKET / EXECUTION REALISM — COMPLETE.
- ACC-002 CROSS-ASSET RANK RESEARCH — FAIL-CLOSED before untouched OOS because the second predeclared liquidity subset is not yet defensibly supported.
- ACC-003 through ACC-014 safety/validation layers — COMPLETE, including regime gating, champion/challenger, provenance, deterioration, robustness, genuine forward proof, portfolio/execution risk, size-aware execution, point-in-time universe safety, multiple-testing firewall, shadow comparison and chaos/failure gates.
- SELECTIVE PRECISION — research-only; independent non-overlapping full-horizon evidence required.
- FUTURE-ONLY AGREEMENT EVIDENCE — accumulating naturally; no backfill or precision claim.
- KRAKEN PUBLIC-BOOK MICROSTRUCTURE — prospective research-only measurement; stale/future/crossed/one-sided/malformed books fail closed; no historical reconstruction or hidden-liquidity inference.
- BETA-NEUTRAL RESIDUAL MOMENTUM — challenger only; cannot bypass canonical validation gates.
- UNIVERSAL SIGNAL-DEVELOPMENT / LEARNING LOOP — active; research-only and information-gain aware.
- QUANT-SCIENCE RESEARCH FACTORY — active; predeclared science, bounded executable breadth and blocker-aware scheduling.
- ADAPTIVE ACCURACY EXPERIMENT LANE — active; protected by durable trial memory and sequential multiple-testing-adjusted OOS admission.
- TOKEN-FREE SPECIALIST FACTORY — 256 active deterministic logical specialists per refresh, zero normal-operation AI calls, research-only.

### ACC-002 genuine bounded evidence
The blocker remains natural history, not a strategy pass/fail result. Do not lower `minimum_subset_coverage=0.80`, remove the two-supported-subset requirement, substitute lower-ranked assets, shorten required history merely to pass, fabricate/backfill history, or repeatedly spend scarce cycles re-diagnosing pure `InsufficientHistory` outcomes.

Post-PR #179 coordinator evidence still showed only the Top-15 subset defensibly supported for ACC-002. The 24h worker resolved 26/30 symbols and the 7d worker resolved 18/30, with remaining failures classified as `InsufficientHistory`; both remained `insufficient_supported_liquidity_subsets`, untouched OOS stayed closed, and authority flags remained false. These counts are operational snapshots and will change naturally; use live observability for current values.

Pure ACC-002 `InsufficientHistory` outcomes use the bounded recheck delay so the shared accuracy lane can spend more time on falsifiable adaptive research. Mixed request/source/software failures must not receive that exemption.

## OPERATIONS / RELIABILITY
Prediction-ledger persistence, observer rate-limit backoff, conservative Kraken paper execution, stable-quote USD bridge marking, queue-state supervision, deployment canary, aggregate failure classification and worker-supervisor protections remain active.

PR #165 exact head `1067e7c79443fbe532fa36e7e922529d83d5eafb` passed Security and Reliability #1238 before merge as `581121bd2585e4bfdee82b9b7685b74320e44afd`.
PR #167 exact head `0813b9e352b071a3cb882828a2faeb1867df8ebe` passed Security and Reliability #1246 before merge as `6058aed4f62dd5519d81965ead2bad26503ac820`.
PR #168 exact final head `ca3181193fb2c1f0f0ef1be6d661f9e0bfe5aea2` passed Security and Reliability #1260 before squash merge as `c73f93ca90dc70e6ecb4810f0ed591994a7d434b`.
PR #170 exact head `bc7d49c3d94839b45e79a42e5b1895d43079efb4` passed Security and Reliability #1277 before squash merge as `0fbd13643c01ca9dfd63fcfbd0b60ec5300c2fe6`.
PR #179 exact head `9755aea5e44b5becf9af81c616cf79e4147ca818` passed Security and Reliability #1317 before squash merge as `946c6f7ec5e41ab5c364aa7f5e93f0bc56a32de9`.
PR #181 exact head `7e26f6ae6fe9de5afb075c5fb58a32ea4e172048` passed Security and Reliability #1326 before squash merge as `15d40568a250b3d6ac5d71e19bc1a1bf25e91c20`.

PR #179 deployed successfully to both production and the continuous coordinator. Both Render deploys reached `live`. Production `/health` returned 200 after startup. The coordinator restarted cleanly with 256 specialists, zero AI calls, no specialist error, no failed/time-out workers in the observed startup window, and trade/promotion/signal authority false. The prior coordinator snapshot showed 1363 completed workers, zero failures, a healthy deployment canary, and ACC-002 still fail-closed.

A live startup log exposed one material paper-cycle defect: a repeated decision write hit Supabase unique constraint `paper_signal_decisions_signal_key_key` and aborted that paper cycle despite the intended ignore-duplicates behavior. PR #181 addresses exactly that idempotency defect. Verify the post-#181 deploy no longer reports duplicate-key paper-cycle failures before treating the issue as operationally cleared.

Supabase security hardening from PR #168 remains required: `research_learning_state` has RLS enabled; anon/authenticated table access is revoked; service role has required access; the atomic append RPC is service-role-only among application roles; and the pre-existing paper append-only function has a fixed `search_path=public`.

GitHub currently reports `main` branch protection disabled. Workflow exact-head/manual-review controls remain mandatory. Enable branch/ruleset protection when repository-admin access is available; do not weaken current controls meanwhile.

Cross-exchange/public-data collection may be unavailable at times. Never manufacture consensus, microstructure, history, agreement data, or outcome labels when source evidence is unavailable or temporally invalid.

## COST / SPEED POLICY
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed. Prefer existing shared Render compute, deterministic Python, free/public defensible data, caching/reuse, early rejection and bounded concurrency. No paid feed/service/compute without explicit approval.

The current logical-worker scale does not raise physical heavy concurrency. The token-free specialist factory uses zero normal-operation AI calls. Heavy experiment admission remains capped at one. API/model spending remains separately budget-gated.

The shared historical cache is provenance/integrity checked and bounded by freshness. Do not stretch TTLs or reuse stale snapshots merely to improve a cache metric. Any cache improvement must preserve exact request identity, point-in-time safety, chronology, completed-candle semantics and authoritative-source fallback.

Preserve exact strategy fingerprints while genuine forward observations accumulate. Challengers may run in shadow. Never count overlapping forecasts as independent, lower forward-proof thresholds, reset paper history, raise heavy concurrency, stretch data freshness beyond safe semantics, change source behavior, or cherry-pick thresholds merely to accelerate results.

## CURRENT OPEN DEVELOPMENT
PRs #160/#163/#164/#165/#167/#168/#170/#172/#173/#175/#176/#177/#178/#179/#181 are integrated and must not be re-applied. PR #180 was a state-only sync branch superseded by this fresh current-main sync and must not be merged. PR #166 is stale/superseded and must not be merged as-is. Older PRs #140, #34, #33 and #13 are stale against current main and must not be merged as-is without a fresh compatibility/relevance review.

Persistent specialist priorities live in `orchestration/specialist_coordination.json`. Specialists may create isolated candidate work only and may not bypass the canonical evidence gates or recurring-cost ceiling.

## EXACT NEXT STEP
1. Verify the post-PR #181 Render deploy reaches `live` on both production and the research coordinator. Specifically confirm repeated paper signal-decision writes no longer generate Supabase 409 duplicate-key failures or abort paper cycles.
2. Inspect naturally completed adaptive-accuracy evidence. Confirm the durable Supabase trial counter changes only for genuinely conclusive `validation_failed` or `oos_evaluated` lessons and that untouched OOS remains sealed unless the sequential adjusted validation gate passes.
3. Audit prediction-ledger outcomes for temporal integrity after PR #179: stale delayed candles should remain unresolved, while valid first-at/after-deadline 1H candles within the explicit tolerance should resolve normally. Do not backfill invalid historical labels merely to increase sample count.
4. Preserve the ACC-002 natural-history blocker while aggregate failures remain `InsufficientHistory`; never weaken the 80% coverage, two-supported-subset, Top-N ordering or untouched-OOS rules.
5. Continue improving cheap research throughput and hypothesis quality without raising physical heavy concurrency. Prioritize falsifiable selective-WAIT, regime-conditioned suppression, calibration, deterioration, cross-asset and prospective execution/microstructure experiments with deterministic timestamp-safe evaluators.
6. Keep prospective microstructure/consensus evidence accumulating naturally; never reconstruct unavailable historical order books or backfill future-only provenance.
7. Monitor the authentic append-only paper ledger without rewriting history. Paper results remain evidence only.
8. Keep `live_promotions.json` empty, broker disconnected, signing keys unused, paper baseline immutable, heavy concurrency bounded, and recurring infrastructure within USD 30/month until genuine governed evidence justifies any separately approved change.
9. Keep exact-head Security and Reliability plus current-main compatibility review mandatory for every integration.
