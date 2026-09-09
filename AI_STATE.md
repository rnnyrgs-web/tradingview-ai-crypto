# AI DEVELOPMENT STATE
Last updated: 2026-09-09

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file from current `main` in full before development. Never infer project state only from ChatGPT memory. Update this file after each completed integration cycle.

## CURRENT MAIN / ARCHITECTURE
Current tested integration baseline after PR #170: `0fbd13643c01ca9dfd63fcfbd0b60ec5300c2fe6`.

Production: GitHub -> Render -> Python/FastAPI V3 -> Supabase. Production scans run about every 15 minutes and produce separate 24h/7d Top-20 rankings. Continuous research/backtesting runs on the existing Render coordinator with bounded heavy concurrency under the USD 30/month recurring-infrastructure ceiling.

Primary production Render service: `srv-dadliegu01pc73bc7t50` (`tradingview-ai-crypto`).
Continuous research coordinator: `srv-dafgtead0e5s73cc7ekg`.
Supabase project used by production/research persistence: `dxgksvzibucwuzmppoqy`.
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed.

The always-on research architecture now includes:
- the bounded Python worker army;
- an autonomous research-director coordination layer;
- a deterministic quant-science experiment factory;
- a fail-closed heavy-experiment admission firewall;
- an adaptive-accuracy lane sharing the existing heavy accuracy slot;
- 256 active token-free logical specialists per refresh from a much larger deterministic virtual namespace;
- durable research memory in Supabase;
- live read-only adaptive evidence observability.

Logical scale must never be confused with physical compute scale. The virtual idea population may be very large, but heavy experiment concurrency remains capped at one admitted heavy experiment at a time unless a separately reviewed change explicitly proves a safe/cost-valid reason to alter it.

## SAFETY INVARIANTS
No AI opinion, ranking score, evidence score, current order-book snapshot, paper P&L, ensemble weight, single OOS result, historical promotion, observability metric, diagnostic, research-memory lesson, experiment priority, market-consensus provenance, microstructure snapshot, residual-momentum result, adaptive-accuracy result, shadow execution result, virtual-specialist result, or paper result by itself may authorize live BUY/SELL.

Mandatory chain:
RESEARCH -> BACKTEST -> VALIDATION -> UNTOUCHED OOS -> ROBUSTNESS/STABILITY -> MULTIPLE-TESTING FIREWALL -> POINT-IN-TIME UNIVERSE SAFETY -> STRATEGY-REGISTRY APPROVAL -> PRODUCTION-RISK APPROVAL -> GENUINE FORWARD PROOF -> GLOBAL/EXECUTION RISK CLEAR -> LIVE BUY/SELL.

Every later stage is restrictive-only. Missing, stale, contradictory, deteriorating, malformed, overlapping-only, insufficient, illiquid, execution-unsafe, portfolio-unsafe, statistically weak, survivorship-unsafe, identity-incomplete, persistence-unsafe, or system-unsafe evidence means `WAIT / NO TRADE / RESEARCH_ONLY`.

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
- missing durable research memory must fail the adaptive lane closed rather than reset prior trials.

PR #149 introduced `UNIVERSAL_SIGNAL_DEVELOPMENT_V1`, the canonical machine-readable objective: optimize genuine forward 24h/7d BUY/SELL/WAIT quality and positive after-cost expectancy, not headline historical accuracy.

PR #155 added the deterministic quant-science factory with predeclared methods/endpoints, minimum effects, one-search budgets, no-parameter-mining/no-OOS-reuse rules, and bounded per-method breadth.

PR #158 added the adaptive research evaluator: hypotheses originate on development evidence, are frozen before validation, and untouched OOS remains sealed unless the predeclared validation gate passes.

PR #160 added the autonomous 24/7 research-director coordination layer. It coordinates missions and scarce compute but has no production-promotion authority.

PR #163 bridges safe logical-specialist diagnoses into the quant experiment factory so useful resolved-error hypotheses can enter the same governed scientific queue.

PR #164 hardened massive virtual research with a fail-closed firewall. Every admitted quant-science design must remain research-only and satisfy, among other requirements: one predeclared search, one candidate mutation, no parameter mining, no untouched-OOS reuse, no OOS/forward pooling, mandatory multiple-testing protection, independent replication, genuine-forward replication, duplicate-hypothesis penalties, no paid-compute escalation by default, and no trade/promotion/strategy-mutation authority. Heavy concurrency remains one.

PR #165 scales token-free logical research from 32 core specialists to 256 active deterministic specialists per refresh while retaining one shared immutable-ledger read and zero normal-operation AI calls. A much larger virtual hypothesis namespace is metadata/search space only; it does not imply materializing or executing that many workers.

PR #167 surfaces the adaptive-accuracy worker's latest evidence through read-only research observability. This changes visibility only, not research or promotion gates.

PR #168 makes the multiple-testing requirement real before adaptive OOS admission. It adds a monotonic conclusive research-trial count and a sequential alpha-spending policy (`alpha_i = 0.05 / (i * (i + 1))`). The retained validation candidate must clear the resulting multiple-testing-adjusted Wilson lower-bound gate above baseline precision in addition to existing minimum-sample, minimum-lift, actionable-coverage, complete-return and positive after-cost-expectancy requirements. Failure keeps untouched OOS sealed.

PR #168 also moves adaptive research memory off ephemeral Render `/tmp` in production and onto the existing Supabase project. `public.research_learning_state` is a service-role-only, RLS-enabled singleton store with an atomic append function. It retains a bounded lesson list plus a monotonic conclusive-trial count across deploys. A configured persistent-store failure is not replaced by an empty local state; research fails closed instead. Local/test explicit paths retain the file adapter.

PR #170 increases the cloud-specialist eligibility check cadence from every three hours to hourly while preserving the 12-hour successful-run cooldown, one concurrent/model run, the $1/day runner API budget, the $30/month recurring-infrastructure ceiling, review-only Lead behavior, no automatic merge, and no trade authority. This improves orchestration responsiveness without increasing permitted model-call frequency or physical heavy-research concurrency.

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
- ADAPTIVE ACCURACY EXPERIMENT LANE — active; now protected by durable trial memory and sequential multiple-testing-adjusted OOS admission.
- TOKEN-FREE SPECIALIST FACTORY — 256 active deterministic logical specialists per refresh, zero normal-operation AI calls, research-only.

### ACC-002 genuine bounded evidence
The blocker remains natural history, not a strategy pass/fail result. Do not lower `minimum_subset_coverage=0.80`, remove the two-supported-subset requirement, substitute lower-ranked assets, shorten required history merely to pass, fabricate/backfill history, or repeatedly spend scarce cycles re-diagnosing pure `InsufficientHistory` outcomes.

Recent live coordinator evidence before/around the PR #168 deployment continued to show only the Top-15 subset defensibly supported for ACC-002. The 24h/7d workers therefore remained `insufficient_supported_liquidity_subsets` and untouched OOS remained unopened. Exact resolved-symbol counts vary naturally as history accumulates; use live observability rather than stale numbers in this file for current counts.

Pure ACC-002 `InsufficientHistory` outcomes use the bounded recheck delay so the shared accuracy lane can spend more time on falsifiable adaptive research. Mixed request/source/software failures must not receive that exemption.

## OPERATIONS / RELIABILITY
Prediction-ledger persistence, observer rate-limit backoff, paper conflict suppression, conservative Kraken paper execution, stable-quote USD bridge marking, queue-state supervision, deployment canary, aggregate failure classification and worker-supervisor protections remain active.

PR #164 exact head passed Security and Reliability #1232 before merge.
PR #165 exact head `1067e7c79443fbe532fa36e7e922529d83d5eafb` passed Security and Reliability #1238 before merge as `581121bd2585e4bfdee82b9b7685b74320e44afd`.
PR #167 exact head `0813b9e352b071a3cb882828a2faeb1867df8ebe` passed Security and Reliability #1246 before merge as `6058aed4f62dd5519d81965ead2bad26503ac820`.
PR #168 initially failed only because Bandit interpreted a metadata key containing the substring `pass` as a password-like field; the key was renamed without weakening the scientific gate. All unit tests and dependency audit had passed on that attempt. Exact final head `ca3181193fb2c1f0f0ef1be6d661f9e0bfe5aea2` then passed Security and Reliability #1260 before squash merge as `c73f93ca90dc70e6ecb4810f0ed591994a7d434b`.
PR #170 exact head `bc7d49c3d94839b45e79a42e5b1895d43079efb4` passed Security and Reliability #1277 before squash merge as `0fbd13643c01ca9dfd63fcfbd0b60ec5300c2fe6`.

Post-PR #168 Render deployment `dep-dagqva6q1p3s73d47jrg` reached `live`. Startup logs showed the coordinator running normally, `specialist_factory workers=256 cycles=1 error=None ai_calls=0`, supervisor healthy, no stale/crashed workers at startup, and no promotion authority. Treat this as operational evidence only.

Supabase security hardening performed during PR #168 integration:
- `research_learning_state` has RLS enabled;
- anon/authenticated table access revoked;
- service role receives the required access;
- the atomic append RPC is executable only by service role among application roles;
- the pre-existing `enforce_paper_trade_append_only()` function received a fixed `search_path=public`, removing the security-advisor mutable-search-path warning without changing append-only behavior.

GitHub currently reports `main` branch protection disabled. Workflow exact-head/manual-review controls remain mandatory. Enable branch/ruleset protection when repository-admin access is available; do not weaken current controls meanwhile.

Cross-exchange/public-data collection may be unavailable at times. Never manufacture consensus, microstructure, history or agreement data when source evidence is unavailable.

## COST / SPEED POLICY
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed. Prefer existing shared Render compute, deterministic Python, free/public defensible data, caching/reuse, early rejection and bounded concurrency. No paid feed/service/compute without explicit approval.

The current logical-worker scale does not raise physical heavy concurrency. The token-free specialist factory uses zero normal-operation AI calls. Heavy experiment admission remains capped at one. API/model spending remains separately budget-gated.

The shared historical cache is intentionally provenance/integrity checked and bounded by freshness. Current live hit rates are low enough to justify continued optimization, but do not stretch TTLs or reuse stale snapshots merely to improve a cache metric. Any cache improvement must preserve exact request identity, point-in-time safety, chronology, completed-candle semantics and authoritative-source fallback.

Preserve exact strategy fingerprints while genuine forward observations accumulate. Challengers may run in shadow. Never count overlapping forecasts as independent, lower forward-proof thresholds, reset paper history, raise heavy concurrency, stretch data freshness beyond safe semantics, change source behavior, or cherry-pick thresholds merely to accelerate results.

## CURRENT OPEN DEVELOPMENT
PRs #160/#163/#164/#165/#167/#168/#170 are integrated and must not be re-applied. PR #166 is a stale state-sync branch based before #167/#168 and must not be merged as-is. Older PRs #140, #105, #34, #33 and #13 are stale/non-mergeable against current main and must not be merged as-is without a fresh compatibility/relevance review.

Persistent specialist priorities live in `orchestration/specialist_coordination.json`. Specialists may create isolated candidate work only and may not bypass the canonical evidence gates or recurring-cost ceiling.

## EXACT NEXT STEP
1. Inspect naturally completed adaptive-accuracy evidence after PR #168. Confirm the durable Supabase trial counter changes only for genuinely conclusive `validation_failed` or `oos_evaluated` lessons and that untouched OOS remains sealed unless the sequential adjusted validation gate passes.
2. Preserve the ACC-002 natural-history blocker while aggregate failures remain `InsufficientHistory`; never weaken the 80% coverage, two-supported-subset, Top-N ordering or untouched-OOS rules.
3. Continue improving cheap research throughput and hypothesis quality without raising physical heavy concurrency. Historical-cache improvements must preserve freshness and point-in-time correctness.
4. Expand executable science only when a deterministic timestamp-safe evaluator exists. High-value directions remain selective WAIT/abstention, regime-conditioned suppression, calibration, deterioration detection, cross-asset structure and prospective execution/microstructure features.
5. Keep prospective microstructure/consensus evidence accumulating naturally; never reconstruct unavailable historical order books or backfill future-only provenance.
6. Monitor the authentic append-only paper ledger without rewriting history. Paper results remain evidence only.
7. Keep `live_promotions.json` empty, broker disconnected, signing keys unused, paper baseline immutable, heavy concurrency bounded, and recurring infrastructure within USD 30/month until genuine governed evidence justifies any separately approved change.
8. Keep exact-head Security and Reliability plus current-main compatibility review mandatory for every integration.
