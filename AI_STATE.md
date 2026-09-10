# AI DEVELOPMENT STATE
Last updated: 2026-09-10

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file from current `main` in full before development. Never infer project state only from ChatGPT memory. Update this file after each completed integration cycle.

## CURRENT MAIN / ARCHITECTURE
Current tested functional integration baseline after PR #225: `d6505d0ccf79e86da96b30c224ac7edf6dd47641`.

Recent integrated sequence relevant to current architecture:
- #210/#211/#213 established governed persisted 6h/12h/24h/48h/72h/7d opportunity generation, exact-horizon deadlines, horizon-specific calibration/genuine-forward chronology, and all-horizon dashboard reads while new horizons remain WAIT/LEARNING.
- #214 added the FFriZz-inspired secondary six-horizon family as research/shadow only, with zero production, paper, broker, or promotion authority.
- #216 added prospective FFriZz SHADOW_BUY/SHADOW_SELL collection inside the existing bounded adaptive-accuracy lane, using full-horizon bucket identity and exact deadlines.
- #217 hardened FFriZz scientific semantics: cross-symbol pooled diagnostics are descriptive/non-independent, OHLC-only historical diagnostics do not match the prospective OI-capable fingerprint, and feature-family agreement is not treated as proven independence.
- #219 fixed FFriZz `scan_id` persistence to deterministic UUIDv5 keyed by system+horizon+full-horizon bucket.
- #221 fixed the canonical action contract: FFriZz shadow action remains research metadata, immutable direction remains LONG/SHORT, and `action_at_forecast` remains WAIT.
- #223 exact head `d5b3c353ff54d73a8673c1026cbc522a5d0ebc40` passed Security and Reliability #1619 and merged as `14318165650e2c9ca46146347c40dec2a252506c`. A live Supabase schema audit showed `prediction_ledger.score` is constrained to 0..100 while FFriZz raw scores are signed. Eligible SHORT rows therefore carried negative ledger scores and could reject the entire insert batch. #223 maps only the persisted ledger score to absolute shadow strength and preserves the signed raw score in calibration metadata.
- #225 exact head `d947496c9af5f4502c9f3fe471445df2385dacdf` passed Security and Reliability #1628 and merged as `d6505d0ccf79e86da96b30c224ac7edf6dd47641`. It exposes a bounded read-only `ffrizz_forward` summary from already-recorded adaptive-worker evidence in the private coordinator observability log. This makes legitimate all-WAIT source output distinguishable from FFriZz collection/persistence failure without exposing raw ledger rows or changing research/trading behavior.

Production: GitHub -> Render -> Python/FastAPI V3 -> Supabase. Production scans run about every 15 minutes. The governed opportunity stream supports 6h, 12h, 24h, 48h, 72h and 7d. Continuous research/backtesting runs on the existing Render coordinator with bounded heavy concurrency under the USD 30/month recurring-infrastructure ceiling.

Primary production Render service: `srv-dadliegu01pc73bc7t50` (`tradingview-ai-crypto`).
Continuous research coordinator: `srv-dafgtead0e5s73cc7ekg`.
Supabase project: `dxgksvzibucwuzmppoqy`.
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed.

Always-on research architecture includes bounded Python workers, autonomous research-director coordination, deterministic quant-science experiment factory, fail-closed heavy-experiment admission firewall, adaptive-accuracy lane sharing the existing heavy slot, 256 active token-free logical specialists per refresh, durable research memory in Supabase, non-overlapping full-horizon calibration/forward-proof logic, research-only meta-WAIT/regime×strategy/economic-calibration/cross-sectional/residual/prospective-microstructure/ensemble-diversity/error-attribution/selective-WAIT/A+ meta-signal diagnostics, exact-key single-flight historical-data coordination without freshness relaxation, authentic paper LONG and paper-only Kraken perpetual SHORT execution with conservative visible-depth/fee/slippage/funding assumptions, retryable `TECHNICAL_BLOCKED` incidents, and FFriZz prospective shadow evidence collection inside existing bounded compute only.

Logical scale must never be confused with physical compute scale. Heavy experiment concurrency remains capped at one admitted heavy experiment at a time unless a separately reviewed change proves a safe/cost-valid reason to alter it.

## SAFETY INVARIANTS
No AI opinion, ranking score, evidence score, order-book snapshot, paper P&L, ensemble weight, historical diagnostic, single OOS result, research-memory lesson, experiment priority, market-consensus provenance, microstructure snapshot, FFriZz diagnostic, FFriZz forward row, FFriZz observability summary, or paper result by itself may authorize live BUY/SELL.

Mandatory chain:
RESEARCH -> BACKTEST -> VALIDATION -> UNTOUCHED OOS -> ROBUSTNESS/STABILITY -> MULTIPLE-TESTING FIREWALL -> POINT-IN-TIME UNIVERSE SAFETY -> STRATEGY-REGISTRY APPROVAL -> PRODUCTION-RISK APPROVAL -> GENUINE FORWARD PROOF -> GLOBAL/EXECUTION RISK CLEAR -> LIVE BUY/SELL.

Every later stage is restrictive-only. Missing, stale, contradictory, malformed, overlapping-only, insufficient, illiquid, execution-unsafe, portfolio-unsafe, statistically weak, survivorship-unsafe, identity-incomplete, persistence-unsafe, label-unsafe, chronology-unsafe, or system-unsafe evidence means `WAIT / NO TRADE / RESEARCH_ONLY`.

`live_promotions.json` remains empty. Signing keys remain unused. Broker remains disconnected. Do not add credentials or real-order capability without explicit user approval plus all canonical evidence gates.

Authentic paper account baseline remains exactly `$100,000` from `2026-09-08T01:17:49Z`. Never reset, rewrite, replace, or manufacture its history. Paper performance is evidence only.

## SCIENTIFIC RESEARCH DISCIPLINE
Chronological validation remains development -> validation -> untouched holdout/OOS. Robustness includes deterministic bootstrap/Monte Carlo resampling, parameter perturbation, regime stability, conservative execution-cost stress, search-breadth protection, and genuine forward confirmation. Forward proof counts only non-overlapping full-horizon resolved forecasts for the exact immutable strategy fingerprint.

Core invariants:
- no lookahead or leakage;
- no threshold/parameter mining against untouched OOS;
- no OOS reuse as fresh confirmation;
- no pooling historical/OOS evidence with genuine-forward evidence to inflate confidence;
- no survivorship substitution for missing point-in-time universe evidence;
- no backfilling prospective order-book/consensus/cross-sectional/OI evidence;
- realistic fees, spread, slippage, funding/carry and execution assumptions remain mandatory;
- repeated/disproven hypotheses receive research-memory penalties rather than blind recycling;
- idea generation is not evidence;
- missing durable research memory fails the adaptive lane closed;
- overlapping forecasts are never independent observations;
- cross-symbol observations sharing market intervals/common factors are not independent merely because symbols differ;
- feature families must not be called independent unless independence is demonstrated;
- historical FFriZz OHLC-only diagnostics are descriptive because historical OI is intentionally not backfilled and therefore do not match the prospective OI-capable fingerprint;
- prospective FFriZz SHADOW_BUY/SHADOW_SELL remains research metadata only; canonical `action_at_forecast` stays WAIT;
- FFriZz direction is encoded in immutable LONG/SHORT. The ledger `score` is a nonnegative 0..100 strength field; the signed FFriZz research score remains separately in `calibration.raw_score`;
- FFriZz operational observability is diagnosis only: raw ledger rows/error detail are not logged and `ffrizz_forward` has no trade, signal, paper, promotion, or strategy authority;
- malformed, missing, or delayed outcome chronology fails closed;
- diagnostics cannot open untouched OOS, mutate production action, or grant trade/promotion authority;
- ensemble member count is not independent evidence;
- ambiguous errors remain unexplained rather than receiving invented causes;
- new 6h/12h/48h/72h horizons accumulate their own independent forward proof and may not borrow evidence from 24h/7d;
- hourly self-improvement review must not force paid model calls, bypass the successful-run cooldown, exceed the $1/day API budget, increase physical concurrency, or change production authority.

Existing 24h/7d forward thresholds are unchanged. Newer 6h and 12h horizons require at least 30 independent forward samples, 48h at least 20, and 72h at least 16 before forward-proof sample sufficiency. Forward proof remains restrictive-only and cannot authorize a trade by itself.

## ACCURACY / RESEARCH PROGRAM
- ACC-001 MARKET / EXECUTION REALISM — COMPLETE.
- ACC-002 CROSS-ASSET RANK RESEARCH — FAIL-CLOSED before untouched OOS because the second predeclared liquidity subset is not yet defensibly supported.
- ACC-003 through ACC-014 safety/validation layers — COMPLETE.
- SELECTIVE PRECISION — research-only; independent non-overlapping full-horizon evidence required.
- ECONOMIC META-WAIT — active research-only, horizon-specific.
- REGIME × STRATEGY ROUTER — active research-only; untouched OOS sealed.
- ECONOMIC CALIBRATION — active research-only with multi-level cost stress; untouched OOS sealed.
- SELECTIVE-WAIT FUSION — active research-only experiment prioritization.
- A+ META-SIGNAL TRUST — active research-only using immutable shadow direction and timestamp-safe future-only consensus.
- CROSS-SECTIONAL / RESIDUAL SIGNAL SCIENCE — active research-only; missing point-in-time fields stay missing.
- MICROSTRUCTURE VETO — active prospective research-only; no historical order-book reconstruction.
- ENSEMBLE DIVERSITY — active research-only.
- RESOLVED ERROR ATTRIBUTION — active research-only.
- BETA-NEUTRAL RESIDUAL MOMENTUM — challenger only.
- QUANT-SCIENCE / ADAPTIVE ACCURACY / EVIDENCE-VALUE SCHEDULER — active under durable sequential multiple-testing protection.
- TOKEN-FREE SPECIALIST FACTORY — 256 active deterministic logical specialists; do not raise the count without measured information-value evidence.
- MULTI-HORIZON OPPORTUNITY LEARNING — active for all six horizons; new horizons remain WAIT/LEARNING until their own canonical gates pass.
- FFRIZZ SECONDARY V1 — prospective research/shadow challenger only. Historical pooled diagnostics are descriptive and ineligible as validation evidence. #219, #221, and #223 fixed UUID, action-enum, and score-range persistence contracts; #225 adds bounded collection observability so absence of rows can be diagnosed without weakening abstention. No edge is claimed until genuine resolved non-overlapping evidence accumulates.

### ACC-002 bounded evidence policy
Recent live coordinator evidence remains dominated by `InsufficientHistory`; untouched OOS stays closed. Do not lower `minimum_subset_coverage=0.80`, remove the two-supported-subset requirement, substitute lower-ranked assets, shorten required history, fabricate/backfill history, or repeatedly spend scarce cycles re-diagnosing pure `InsufficientHistory` outcomes. Natural history accumulation is the blocker unless live evidence materially changes.

## LIVE OPERATIONAL EVIDENCE
PR #225 exact-head Security and Reliability #1628 completed successfully, including unit tests, dependency vulnerability audit, static security scan, and committed-secret checks. Current main had not moved relative to the branch base while the PR was tested, so #225 merged only after exact-head compatibility was confirmed.

Both production and the research coordinator reached `live` on merge commit `d6505d0ccf79e86da96b30c224ac7edf6dd47641`. The first post-deploy coordinator log included the new bounded `ffrizz_forward` object with authority fields false. At initial startup its worker evidence fields were naturally null because no adaptive worker result had completed on the new process yet.

A read-only Supabase query during the #225 cycle still found zero rows containing `ffrizz` in `prediction_ledger.strategy_identity` or `calibration`. This is now a live diagnostic question rather than evidence of another schema defect: wait for the next adaptive FFriZz collection result and use `ffrizz_forward.collection_ok`, `eligible_shadow_forecasts`, and `error_type` to distinguish all-WAIT source behavior from collection failure. Never create a synthetic signal merely to prove persistence.

Read-only research-memory inspection showed zero stored lessons and zero conclusive adaptive trials at the sampled time. This is not a reason to lower validation thresholds or manufacture evidence; it means the durable adaptive lane has not yet produced a conclusive result worth recording under its existing rules.

Coordinator evidence immediately before #225 remained healthy: sampled logs showed zero worker failures/timeouts, no history-fetch failures, a healthy supervisor, 256 logical specialists with zero normal-operation AI calls, and ACC-002 still blocked only by insufficient supported liquidity subsets. Recent ACC-002 snapshots had 24h resolve 28/30 with two `InsufficientHistory` failures and 7d resolve 15/30 with fifteen `InsufficientHistory` failures; untouched OOS remained closed and trade/promotion/signal authority false.

Recent raw overlapping production prediction rows must not be treated as independent accuracy evidence. Only canonical de-overlapped diagnostics may support inference.

## COST / SPEED POLICY
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed. Prefer existing shared Render compute, deterministic Python, free/public defensible data, caching/reuse, early rejection, and bounded concurrency. No paid feed/service/compute without explicit approval.

The token-free specialist factory uses zero normal-operation AI calls. Heavy experiment admission remains capped at one. API/model spending remains separately budget-gated.

Preserve exact strategy fingerprints while genuine forward observations accumulate. Challengers may run in shadow. Never count overlapping forecasts as independent, lower forward-proof thresholds, reset paper history, raise heavy concurrency, stretch data freshness, change source behavior, or cherry-pick thresholds merely to accelerate results.

Blind RSI/MACD/EMA parameter permutations without a diagnosed resolved-error mechanism are deprioritized. Redundant ensemble members, repeated falsified hypotheses without materially new evidence, repeated ACC-002 investigation while failures are purely `InsufficientHistory`, and worker-count expansion without measured information-value benefit are also deprioritized.

## CURRENT OPEN DEVELOPMENT
PR #225 is integrated and must not be re-applied. PRs #214/#216/#217/#219/#221/#223 are also integrated functional prerequisites. State-only sync PRs through #224 are integrated.
PRs #34, #33 and #13 remain stale against current main and must not be merged as-is without a fresh compatibility/relevance review. #212 is superseded by #214; #205 by #207; #206 was branch reconciliation; #180 is stale state-only work; #166 and #140 are superseded.

Persistent specialist priorities live in `orchestration/specialist_coordination.json`. The accuracy/profitability roadmap lives in `orchestration/accuracy_profitability_roadmap.json`.

## EXACT NEXT STEP
1. Wait for the next natural adaptive/FFriZz worker result and inspect the bounded coordinator `ffrizz_forward` evidence.
2. If `collection_ok=true` and `eligible_shadow_forecasts=0`, treat zero ledger rows as legitimate source abstention for that cycle; do not loosen FFriZz thresholds merely to create observations.
3. If `collection_ok=false`, repair only the confirmed collection/data/persistence defect and add regression coverage; do not fabricate a row.
4. If `collection_ok=true` and eligible forecasts are positive, query `prediction_ledger` read-only and validate deterministic UUID `scan_id`, immutable LONG/SHORT direction, canonical WAIT action, nonnegative bounded ledger strength, signed `calibration.raw_score`, preserved `shadow_action`, exact `due_at`, and full-horizon bucket identity.
5. Let first valid FFriZz rows resolve naturally. Do not promote or tune from unresolved, overlapping, fingerprint-mismatched, or historically backfilled evidence.
6. Continue normal resolved-error diagnostics, selective-WAIT, regime×strategy, economic calibration, cross-sectional/residual, prospective microstructure, and ensemble-diversity research using evidence-value scheduling.
7. Preserve ACC-002 natural-history fail-closed behavior while failures remain pure `InsufficientHistory`.
8. Keep `live_promotions.json` empty, broker disconnected, signing keys unused, authentic paper history immutable, heavy concurrency bounded, and recurring infrastructure under USD 30/month.
9. Every future integration still requires an isolated branch, confirmed-defect regression tests where applicable, exact-head Security and Reliability, current-main compatibility review, and post-deploy health verification. No profitability or accuracy claim is justified by #225 itself.
