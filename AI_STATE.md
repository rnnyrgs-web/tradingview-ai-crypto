# AI DEVELOPMENT STATE
Last updated: 2026-09-10

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file from current `main` in full before development. Never infer project state only from ChatGPT memory. Update this file after each completed integration cycle.

## CURRENT MAIN / ARCHITECTURE
Current tested integration baseline: `555c8f5030d61d9e40e8ab24519f1a8f03739cff` after PR #213.

Recent integrated sequence beyond the prior PR #208 baseline:
- PR #210 (`d04c068c28d5ef0de672b0a2a25f042ef53ea361`) added research-only 6h/12h/24h/48h/72h/7d tradeable-move discovery and prepared dashboard support without fabricating unsupported rows.
- PR #211 exact head `95411e569a5729199aecebf170938eeaaac9a0db` passed Security and Reliability #1532 and merged as `2a6b073e2b533d6c29b75a55469a2ff235c64e91`. It added governed persisted production opportunity generation for 6h/12h/24h/48h/72h/7d, exact-horizon immutable deadlines, horizon-specific calibration/genuine-forward chronology and dashboard reads. New horizons begin WAIT/LEARNING and cannot become actionable without the canonical promotion chain.
- PR #213 exact head `edaae28154bdb6d3501581476a55b6541a3fa1d7` passed Security and Reliability #1543 and merged as `555c8f5030d61d9e40e8ab24519f1a8f03739cff`. The combined dashboard now defaults to `all` and accepts every canonical opportunity horizon. Main push Security and Reliability #1545 also passed.

Production: GitHub -> Render -> Python/FastAPI V3 -> Supabase. Production scans run about every 15 minutes. The governed opportunity stream now supports 6h, 12h, 24h, 48h, 72h and 7d. Continuous research/backtesting runs on the existing Render coordinator with bounded heavy concurrency under the USD 30/month recurring-infrastructure ceiling.

Primary production Render service: `srv-dadliegu01pc73bc7t50` (`tradingview-ai-crypto`).
Continuous research coordinator: `srv-dafgtead0e5s73cc7ekg`.
Supabase project used by production/research persistence: `dxgksvzibucwuzmppoqy`.
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed.

Latest operational verification before this state sync:
- production service auto-deployed commit `555c8f5030d61d9e40e8ab24519f1a8f03739cff` and the deploy is `live`;
- research coordinator auto-deployed the same commit and the deploy is `live`;
- no paid service, worker-count increase or heavy-concurrency increase was introduced by PRs #210/#211/#213.

The always-on research architecture includes:
- bounded Python workers;
- autonomous research-director coordination;
- deterministic quant-science experiment factory;
- fail-closed heavy-experiment admission firewall;
- adaptive-accuracy lane sharing the existing heavy accuracy slot;
- 256 active token-free logical specialists per refresh from a much larger deterministic virtual namespace;
- durable research memory in Supabase;
- live read-only adaptive evidence observability including the durable conclusive-trial counter;
- research-only economic meta-WAIT diagnostics over independent non-overlapping full-horizon outcomes, kept horizon-specific;
- research-only regime×strategy diagnostics with chronological development/validation and sealed untouched OOS;
- research-only economic calibration with realistic execution-cost stress and sealed untouched OOS;
- research-only cross-sectional/residual diagnostics using only persisted point-in-time fields;
- prospective microstructure-veto diagnostics using only timestamped persisted evidence;
- ensemble-diversity diagnostics based on matched strategy error behavior;
- resolved-error attribution that proposes falsifiable research buckets without inventing causes;
- selective-WAIT fusion for restrictive abstention hypothesis prioritization only;
- evidence-value scheduling by expected signal impact, information/falsification value, actionable-evidence probability, sample readiness, compute cost and redundancy risk;
- research-only A+ meta-signal trust diagnostics using immutable shadow direction plus timestamp-safe future-only consensus;
- exact separation between research eligibility and production action;
- authentic paper LONG and paper-only Kraken perpetual SHORT execution with conservative visible-depth, fee, slippage and funding assumptions;
- paper SELL exits for same-symbol 7d signal reversal while stop/target/time exits retain priority;
- retryable `TECHNICAL_BLOCKED` execution/data incidents;
- concentration handling that may only allow a candidate when directional concentration is the sole blocker and the candidate strictly reduces absolute signed directional notional;
- exact-key single-flight historical-data coordination without extending freshness or reusing stale data;
- governed multi-horizon opportunity generation for 6h/12h/24h/48h/72h/7d, while actionability remains fail-closed behind existing gates.

Logical scale must never be confused with physical compute scale. Heavy experiment concurrency remains capped at one admitted heavy experiment at a time unless a separately reviewed change explicitly proves a safe/cost-valid reason to alter it.

## SAFETY INVARIANTS
No AI opinion, ranking score, evidence score, current order-book snapshot, paper P&L, ensemble weight, single OOS result, historical promotion, observability metric, diagnostic, research-memory lesson, experiment priority, market-consensus provenance, microstructure snapshot, residual-momentum result, adaptive-accuracy result, meta-WAIT diagnostic, regime-strategy diagnostic, economic-calibration diagnostic, cross-sectional diagnostic, ensemble-diversity diagnostic, error-attribution diagnostic, selective-WAIT fusion result, meta-signal-trust result, shadow execution result, virtual-specialist result, paper result, or new-horizon opportunity row by itself may authorize live BUY/SELL.

Mandatory chain:
RESEARCH -> BACKTEST -> VALIDATION -> UNTOUCHED OOS -> ROBUSTNESS/STABILITY -> MULTIPLE-TESTING FIREWALL -> POINT-IN-TIME UNIVERSE SAFETY -> STRATEGY-REGISTRY APPROVAL -> PRODUCTION-RISK APPROVAL -> GENUINE FORWARD PROOF -> GLOBAL/EXECUTION RISK CLEAR -> LIVE BUY/SELL.

Every later stage is restrictive-only. Missing, stale, contradictory, deteriorating, malformed, overlapping-only, insufficient, illiquid, execution-unsafe, portfolio-unsafe, statistically weak, survivorship-unsafe, identity-incomplete, persistence-unsafe, label-unsafe, chronology-unsafe, or system-unsafe evidence means `WAIT / NO TRADE / RESEARCH_ONLY`.

`live_promotions.json` remains empty. Signing keys remain unused. Broker remains disconnected. Do not add credentials or real-order capability without explicit user approval plus all canonical evidence gates.

Authentic paper account baseline remains exactly `$100,000` from `2026-09-08T01:17:49Z`. Never reset, rewrite, replace, or manufacture its history. Paper performance is evidence only.

## SCIENTIFIC RESEARCH DISCIPLINE
Chronological validation remains development -> validation -> untouched holdout/OOS. Robustness includes deterministic bootstrap/Monte Carlo resampling, parameter perturbation, regime stability, conservative execution-cost stress, search-breadth protection and genuine forward confirmation. Forward proof counts only non-overlapping full-horizon resolved forecasts for the exact immutable strategy fingerprint.

Core invariants:
- no lookahead or leakage;
- no threshold/parameter mining against untouched OOS;
- no OOS reuse as fresh confirmation;
- no pooling historical/OOS evidence with genuine-forward evidence to inflate confidence;
- no survivorship substitution for missing point-in-time universe evidence;
- no backfilling prospective order-book/consensus/cross-sectional fields;
- realistic fees, spread, slippage, funding/carry and execution assumptions remain mandatory;
- repeated/disproven hypotheses receive a research-memory penalty rather than blind recycling;
- idea generation is not evidence;
- missing durable research memory fails the adaptive lane closed;
- overlapping forecasts are never independent observations;
- malformed, missing or delayed outcome chronology fails closed;
- diagnostics and research candidates cannot themselves open untouched OOS, mutate production action or grant trade/promotion authority;
- ensemble member count is not independent evidence;
- ambiguous errors remain unexplained rather than receiving invented causes;
- future-only consensus and microstructure evidence must be timestamp-safe and never reconstructed historically;
- paper execution failures never receive synthetic fills;
- new 6h/12h/48h/72h horizons must accumulate their own independent forward proof; they must not borrow evidence from 24h/7d;
- hourly self-improvement review must not force paid model calls, bypass the 12-hour successful-run cooldown, exceed the $1/day API budget, increase physical concurrency, or change production authority.

Existing 24h/7d forward thresholds are unchanged. For the newer horizons, 6h and 12h require at least 30 independent forward samples, 48h requires at least 20, and 72h requires at least 16 before forward-proof sample sufficiency; forward proof is still restrictive-only and cannot authorize a trade by itself.

## ACCURACY / RESEARCH PROGRAM
- ACC-001 MARKET / EXECUTION REALISM — COMPLETE.
- ACC-002 CROSS-ASSET RANK RESEARCH — FAIL-CLOSED before untouched OOS because the second predeclared liquidity subset is not yet defensibly supported.
- ACC-003 through ACC-014 safety/validation layers — COMPLETE.
- SELECTIVE PRECISION — research-only; independent non-overlapping full-horizon evidence required.
- ECONOMIC META-WAIT — active research-only diagnostic, horizon-specific.
- REGIME × STRATEGY ROUTER — active research-only diagnostic; untouched OOS sealed.
- ECONOMIC CALIBRATION — active research-only diagnostic with multi-level cost stress; untouched OOS sealed.
- SELECTIVE-WAIT FUSION — active research-only experiment prioritization.
- A+ META-SIGNAL TRUST — active research-only diagnostic using immutable shadow direction and timestamp-safe future-only consensus.
- CROSS-SECTIONAL / RESIDUAL SIGNAL SCIENCE — active research-only diagnostics; missing point-in-time fields stay missing.
- MICROSTRUCTURE VETO — active prospective research-only diagnostic; no historical order-book reconstruction.
- ENSEMBLE DIVERSITY — active research-only diagnostic.
- RESOLVED ERROR ATTRIBUTION — active research-only diagnostic.
- FUTURE-ONLY AGREEMENT EVIDENCE — accumulating naturally; no backfill or precision claim.
- BETA-NEUTRAL RESIDUAL MOMENTUM — challenger only.
- UNIVERSAL SIGNAL-DEVELOPMENT / LEARNING LOOP — active.
- QUANT-SCIENCE RESEARCH FACTORY — active.
- EVIDENCE-VALUE RESEARCH SCHEDULER — active.
- ADAPTIVE ACCURACY EXPERIMENT LANE — active with durable sequential multiple-testing protection.
- TOKEN-FREE SPECIALIST FACTORY — 256 active deterministic logical specialists; do not raise the count without measured information-value evidence.
- MULTI-HORIZON OPPORTUNITY LEARNING — active for 6h/12h/24h/48h/72h/7d. New horizons remain WAIT/LEARNING until their own canonical evidence gates pass.

### ACC-002 genuine bounded evidence
The blocker remains natural history, not a strategy pass/fail result. Do not lower `minimum_subset_coverage=0.80`, remove the two-supported-subset requirement, substitute lower-ranked assets, shorten required history merely to pass, fabricate/backfill history, or repeatedly spend scarce cycles re-diagnosing pure `InsufficientHistory` outcomes.

Pure ACC-002 `InsufficientHistory` outcomes use the bounded recheck delay so the shared accuracy lane can spend more time on falsifiable adaptive research. Mixed request/source/software failures must not receive that exemption.

## OPERATIONS / RELIABILITY
Prediction-ledger persistence, observer rate-limit backoff, conservative Kraken spot/perpetual paper execution, stable-quote USD bridge marking, retryable technical incident classification, queue-state supervision, deployment canary, aggregate failure classification and worker-supervisor protections remain active.

Relevant recent exact-head checks:
- PR #211 head `95411e569a5729199aecebf170938eeaaac9a0db` -> Security and Reliability #1532 -> success -> merged as `2a6b073e2b533d6c29b75a55469a2ff235c64e91`.
- PR #213 head `edaae28154bdb6d3501581476a55b6541a3fa1d7` -> Security and Reliability #1543 -> success -> merged as `555c8f5030d61d9e40e8ab24519f1a8f03739cff`.
- Main commit `555c8f5030d61d9e40e8ab24519f1a8f03739cff` -> Security and Reliability #1545 -> success.

Earlier PRs #149 through #208 established the universal signal objective, deterministic experiment factory, adaptive evaluator, autonomous research director, fail-closed heavy admission, 256 logical specialists, durable research memory, sequential multiple-testing, chronology-safe calibration/forward proof, research-only meta-WAIT/regime/economic/microstructure/diversity/error-attribution diagnostics, paper LONG/SHORT execution realism, retryable technical blocks, signal-reversal exits, concentration-only net-risk-reducing handling and exact-key history single-flight. Their historical exact-head details remain in git history and prior AI_STATE revisions; they must not be re-applied.

GitHub currently reports `main` branch protection disabled. Workflow exact-head/manual-review controls remain mandatory. Enable branch/ruleset protection when repository-admin access is available; do not weaken current controls meanwhile.

Cross-exchange/public-data collection may be unavailable at times. Never manufacture consensus, microstructure, history, agreement data, outcome labels, cross-sectional fields, funding, perpetual contract metadata or error causes when source evidence is unavailable or temporally invalid.

## COST / SPEED POLICY
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed. Prefer existing shared Render compute, deterministic Python, free/public defensible data, caching/reuse, early rejection and bounded concurrency. No paid feed/service/compute without explicit approval.

The current logical-worker scale does not raise physical heavy concurrency. The token-free specialist factory uses zero normal-operation AI calls. Heavy experiment admission remains capped at one. API/model spending remains separately budget-gated.

Preserve exact strategy fingerprints while genuine forward observations accumulate. Challengers may run in shadow. Never count overlapping forecasts as independent, lower forward-proof thresholds, reset paper history, raise heavy concurrency, stretch data freshness beyond safe semantics, change source behavior, or cherry-pick thresholds merely to accelerate results.

Blind RSI/MACD/EMA parameter permutations without a diagnosed resolved-error mechanism are deprioritized. Redundant ensemble members, repeated falsified hypotheses without materially new evidence, repeated ACC-002 investigation while failures are purely `InsufficientHistory`, and worker-count expansion without demonstrated information-value benefit are also deprioritized.

## CURRENT OPEN DEVELOPMENT
Open PRs at this sync:
- PR #214 `Rebase FFriZz secondary shadow system onto current main`, head `5baa20db1ad3ef07f7efd55cc11dff5c49fe3e69`. It is research/shadow-only and was still waiting on exact-head Security and Reliability #1574 when this state sync began. Do not merge unless that exact head is fully green, current-main compatible and no new safety issue is found.
- PRs #34, #33 and #13 are stale against current main and must not be merged as-is without a fresh compatibility/relevance review.

PR #212 was stale/closed during rebasing and is superseded by #214. PR #205 is stale/superseded by #207. PR #206 was an internal branch-reconciliation step. PR #180 is a stale state-only sync branch. PR #166 and #140 are superseded. Do not resurrect them unchanged.

Persistent specialist priorities live in `orchestration/specialist_coordination.json`. The accuracy/profitability roadmap lives in `orchestration/accuracy_profitability_roadmap.json`. Specialists may create isolated candidate work only and may not bypass the canonical evidence gates or recurring-cost ceiling.

## EXACT NEXT STEP
1. Finish this state-only synchronization through an isolated PR and exact-head Security and Reliability. Merge only if the tested head exactly matches and current main has not introduced a conflict.
2. Re-check PR #214 exact-head Security and Reliability. If fully green, inspect its complete diff and current-main compatibility before considering merge. It must remain research/shadow-only and must not mutate production, paper, broker, promotion or live authority.
3. Continue accumulating genuine non-overlapping forward evidence separately for every horizon. New horizons must remain WAIT/LEARNING until their own calibration, robustness, OOS, multiple-testing, point-in-time, promotion, forward-proof and execution/risk gates pass.
4. Review recent resolved errors, false positives/false negatives, regime×strategy behavior, economic calibration, feature usefulness, cross-sectional relationships, prospective microstructure evidence and paper execution incidents. Convert only defensible recurring mechanisms into predeclared falsifiable challengers.
5. Prioritize experiments by expected after-cost signal-quality impact, information gain, sample readiness, compute cost and overfitting risk. Preserve research-memory penalties for repeated/disproven ideas.
6. Keep ACC-002 fail-closed while the blocker remains natural history. Do not weaken history coverage, point-in-time universe, chronology or untouched-OOS requirements.
7. Keep `live_promotions.json` empty, broker disconnected, signing keys unused, paper baseline immutable, heavy concurrency bounded and recurring infrastructure within USD 30/month until genuine governed evidence plus explicit approval justifies any change.
