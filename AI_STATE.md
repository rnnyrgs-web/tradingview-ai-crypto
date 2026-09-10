# AI DEVELOPMENT STATE
Last updated: 2026-09-10

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file from current `main` in full before development. Never infer project state only from ChatGPT memory. Update this file after each completed integration cycle.

## CURRENT MAIN / ARCHITECTURE
Current tested integration baseline: `5ed36f22faa769e88c73e2dbfd769494ba4c0ef5` after PR #217.

Recent integrated sequence:
- PR #210 (`d04c068c28d5ef0de672b0a2a25f042ef53ea361`) added research-only 6h/12h/24h/48h/72h/7d tradeable-move discovery and dashboard preparation without fabricating unsupported rows.
- PR #211 exact head `95411e569a5729199aecebf170938eeaaac9a0db` passed Security and Reliability #1532 and merged as `2a6b073e2b533d6c29b75a55469a2ff235c64e91`. It added governed persisted production opportunity generation for all six horizons, exact-horizon deadlines, horizon-specific calibration/genuine-forward chronology and dashboard reads. New horizons begin WAIT/LEARNING.
- PR #213 exact head `edaae28154bdb6d3501581476a55b6541a3fa1d7` passed Security and Reliability #1543 and merged as `555c8f5030d61d9e40e8ab24519f1a8f03739cff`. The combined dashboard defaults to `all`; main push Security and Reliability #1545 also passed.
- PR #215 state-only synchronization passed exact-head Security and Reliability #1577 and merged as `1e3043796cdfeea86ea7a9bf82a3092332e9d673`.
- PR #214 exact head `5baa20db1ad3ef07f7efd55cc11dff5c49fe3e69` passed Security and Reliability #1574 and merged as `1e21335847b7a15a32c5d9a04f6efcc0382f78f5`. It added the FFriZz-inspired secondary 6h/12h/24h/48h/72h/7d shadow signal family. It is research/shadow-only and has zero production, paper, broker or promotion authority.
- PR #216 exact head `59341f3e93e99ec6ddc000280325e67256a1a4f9` passed Security and Reliability #1585 and merged as `4102c3c08f4fbb901c9e791e3ac15b3d77719bb1`. It collects prospective FFriZz SHADOW_BUY/SHADOW_SELL evidence inside the existing bounded adaptive-accuracy lane, uses full-horizon bucket identity and exact deadlines, never persists WAIT as directional evidence, and does not add workers/services/concurrency/cost.
- PR #217 exact head `325e9295a6c2cb820bd8d889f69d27b4849d949d` passed Security and Reliability #1591 and merged as `5ed36f22faa769e88c73e2dbfd769494ba4c0ef5`. It hardens FFriZz scientific evidence semantics: pooled cross-symbol diagnostics are explicitly descriptive/non-independent and ineligible for validation evidence; historical OHLC-only diagnostics explicitly do not match the prospective OI-capable fingerprint; family agreement no longer claims proven independence in persisted calibration.

Production: GitHub -> Render -> Python/FastAPI V3 -> Supabase. Production scans run about every 15 minutes. The governed opportunity stream supports 6h, 12h, 24h, 48h, 72h and 7d. Continuous research/backtesting runs on the existing Render coordinator with bounded heavy concurrency under the USD 30/month recurring-infrastructure ceiling.

Primary production Render service: `srv-dadliegu01pc73bc7t50` (`tradingview-ai-crypto`).
Continuous research coordinator: `srv-dafgtead0e5s73cc7ekg`.
Supabase project: `dxgksvzibucwuzmppoqy`.
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed.

Always-on research architecture includes:
- bounded Python workers;
- autonomous research-director coordination;
- deterministic quant-science experiment factory;
- fail-closed heavy-experiment admission firewall;
- adaptive-accuracy lane sharing the existing heavy slot;
- 256 active token-free logical specialists per refresh;
- durable research memory in Supabase;
- non-overlapping full-horizon calibration/forward-proof logic;
- research-only meta-WAIT, regime×strategy, economic-calibration, cross-sectional/residual, prospective microstructure, ensemble-diversity, error-attribution, selective-WAIT and A+ meta-signal diagnostics;
- exact-key single-flight historical-data coordination without freshness relaxation;
- authentic paper LONG and paper-only Kraken perpetual SHORT execution with conservative visible-depth, fee, slippage and funding assumptions;
- retryable `TECHNICAL_BLOCKED` execution/data incidents;
- FFriZz secondary prospective shadow evidence collection inside existing bounded compute only.

Logical scale must never be confused with physical compute scale. Heavy experiment concurrency remains capped at one admitted heavy experiment at a time unless a separately reviewed change explicitly proves a safe/cost-valid reason to alter it.

## SAFETY INVARIANTS
No AI opinion, ranking score, evidence score, order-book snapshot, paper P&L, ensemble weight, historical diagnostic, single OOS result, research-memory lesson, experiment priority, market-consensus provenance, microstructure snapshot, FFriZz diagnostic, FFriZz forward row, or paper result by itself may authorize live BUY/SELL.

Mandatory chain:
RESEARCH -> BACKTEST -> VALIDATION -> UNTOUCHED OOS -> ROBUSTNESS/STABILITY -> MULTIPLE-TESTING FIREWALL -> POINT-IN-TIME UNIVERSE SAFETY -> STRATEGY-REGISTRY APPROVAL -> PRODUCTION-RISK APPROVAL -> GENUINE FORWARD PROOF -> GLOBAL/EXECUTION RISK CLEAR -> LIVE BUY/SELL.

Every later stage is restrictive-only. Missing, stale, contradictory, malformed, overlapping-only, insufficient, illiquid, execution-unsafe, portfolio-unsafe, statistically weak, survivorship-unsafe, identity-incomplete, persistence-unsafe, label-unsafe, chronology-unsafe or system-unsafe evidence means `WAIT / NO TRADE / RESEARCH_ONLY`.

`live_promotions.json` remains empty. Signing keys remain unused. Broker remains disconnected. Do not add credentials or real-order capability without explicit user approval plus all canonical evidence gates.

Authentic paper account baseline remains exactly `$100,000` from `2026-09-08T01:17:49Z`. Never reset, rewrite, replace or manufacture its history. Paper performance is evidence only.

## SCIENTIFIC RESEARCH DISCIPLINE
Chronological validation remains development -> validation -> untouched holdout/OOS. Robustness includes deterministic bootstrap/Monte Carlo resampling, parameter perturbation, regime stability, conservative execution-cost stress, search-breadth protection and genuine forward confirmation. Forward proof counts only non-overlapping full-horizon resolved forecasts for the exact immutable strategy fingerprint.

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
- feature families must not be called independent unless independence is actually demonstrated;
- historical FFriZz OHLC-only diagnostics are descriptive because historical OI is intentionally not backfilled and therefore do not match the prospective OI-capable fingerprint;
- malformed, missing or delayed outcome chronology fails closed;
- diagnostics cannot open untouched OOS, mutate production action or grant trade/promotion authority;
- ensemble member count is not independent evidence;
- ambiguous errors remain unexplained rather than receiving invented causes;
- new 6h/12h/48h/72h horizons must accumulate their own independent forward proof and may not borrow evidence from 24h/7d;
- hourly self-improvement review must not force paid model calls, bypass the successful-run cooldown, exceed the $1/day API budget, increase physical concurrency or change production authority.

Existing 24h/7d forward thresholds are unchanged. Newer 6h and 12h horizons require at least 30 independent forward samples, 48h requires at least 20, and 72h requires at least 16 before forward-proof sample sufficiency. Forward proof remains restrictive-only and cannot authorize a trade by itself.

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
- FFRIZZ SECONDARY V1 — prospective research/shadow challenger only. Historical pooled diagnostics are descriptive and cannot be used as validation evidence. Prospective evidence must resolve naturally before any inference.

### ACC-002 current live bounded evidence
Live coordinator observability around `2026-09-10T04:47Z`:
- 24h: 28/30 symbols resolved, 2 `InsufficientHistory`, only Top-15 subset supported, `insufficient_supported_liquidity_subsets`, untouched OOS closed.
- 7d: 14/30 symbols resolved, 16 `InsufficientHistory`, no supported liquidity subset, `insufficient_supported_liquidity_subsets`, untouched OOS closed.
Do not lower `minimum_subset_coverage=0.80`, remove the two-supported-subset requirement, substitute lower-ranked assets, shorten required history, fabricate/backfill history, or repeatedly spend scarce cycles re-diagnosing pure `InsufficientHistory` outcomes.

## LIVE OPERATIONAL EVIDENCE
Immediately before PR #217 merge, both production and research coordinator were live on PR #216 merge commit `4102c3c08f4fbb901c9e791e3ac15b3d77719bb1`. Coordinator canary was healthy with no rollback recommendation. Observability showed approximately 1,487 completed worker samples, zero worker failures, zero worker timeouts, no stale/crashed workers, and zero history-fetch failures in the sampled window. Specialist factory remained 256 logical workers with zero normal-operation AI calls.

PR #217 deployment was triggered automatically on both Render services after merge; verify it reaches `live` before treating deployment as healthy.

Read-only Supabase checks during this cycle showed:
- no persisted `FFRIZZ_SECONDARY_V1` prediction-ledger rows yet at the time checked; this is not a failure by itself because only genuine SHADOW_BUY/SHADOW_SELL rows are persisted and the bounded adaptive lane may not yet have emitted an eligible forecast;
- research learning state remained at zero conclusive trials and zero lessons, so there is no adaptive evidence claim yet;
- authentic paper account still uses the original $100,000 baseline; current equity was about $102.8k with 9 closed LONG paper trades and 4 open LONG paper trades at the sampled instant. This is operational evidence only and is not profitability proof.

Recent raw overlapping 24h resolved rows were directionally weak in aggregate. These rows must not be treated as independent accuracy evidence; only canonical de-overlapped diagnostics may support inference.

## COST / SPEED POLICY
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed. Prefer existing shared Render compute, deterministic Python, free/public defensible data, caching/reuse, early rejection and bounded concurrency. No paid feed/service/compute without explicit approval.

The token-free specialist factory uses zero normal-operation AI calls. Heavy experiment admission remains capped at one. API/model spending remains separately budget-gated.

Preserve exact strategy fingerprints while genuine forward observations accumulate. Challengers may run in shadow. Never count overlapping forecasts as independent, lower forward-proof thresholds, reset paper history, raise heavy concurrency, stretch data freshness, change source behavior or cherry-pick thresholds merely to accelerate results.

Blind RSI/MACD/EMA parameter permutations without a diagnosed resolved-error mechanism are deprioritized. Redundant ensemble members, repeated falsified hypotheses without materially new evidence, repeated ACC-002 investigation while failures are purely `InsufficientHistory`, and worker-count expansion without measured information-value benefit are also deprioritized.

Relevant current external research ideas for later falsifiable challengers include scale-invariant order-flow/microstructure representations, regime-conditioned order-flow imbalance, and cross-sectional ranking/anchoring/reversal effects. They are hypotheses only; do not add them merely because papers report results. Require timestamp-safe available data, predeclared design, realistic costs, chronological validation and multiple-testing protection.

## CURRENT OPEN DEVELOPMENT
PRs #214, #215, #216 and #217 are integrated and must not be re-applied.
PRs #34, #33 and #13 remain stale against current main and must not be merged as-is without a fresh compatibility/relevance review.
PR #212 is superseded by #214. PR #205 is superseded by #207. PR #206 was branch reconciliation. PR #180 is stale state-only work. PR #166 and #140 are superseded.

Persistent specialist priorities live in `orchestration/specialist_coordination.json`. The accuracy/profitability roadmap lives in `orchestration/accuracy_profitability_roadmap.json`.

## EXACT NEXT STEP
1. Verify PR #217 deployment/production health on both Render services. No rollback unless canary or operational evidence indicates a real regression.
2. Continue prospective FFriZz collection, but use only genuine resolved non-overlapping forward rows. Do not use pooled historical cross-symbol accuracy as independent evidence and do not backfill historical OI.
3. When the first FFriZz rows resolve, analyze false positives/false negatives by horizon, direction, regime/proxy context, family availability and after-cost outcome without changing thresholds from the same evidence slice.
4. Prioritize the next challenger by expected information gain and after-cost signal-quality impact. Current research suggests regime-conditioned microstructure/order-flow and cross-sectional rank/anchoring/reversal ideas are worth predeclared tests only if point-in-time data availability is defensible.
5. Continue accumulating genuine non-overlapping forward evidence separately for every production horizon. New horizons remain WAIT/LEARNING until all canonical gates pass.
6. Keep ACC-002 fail-closed while the blocker remains natural history. Do not weaken coverage, chronology, point-in-time universe or untouched-OOS requirements.
7. Keep `live_promotions.json` empty, broker disconnected, signing keys unused, paper baseline immutable, heavy concurrency bounded and recurring infrastructure within USD 30/month until genuine governed evidence plus explicit approval justifies any change.
