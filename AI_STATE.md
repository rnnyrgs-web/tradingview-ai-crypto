# AI DEVELOPMENT STATE
Last updated: 2026-09-10

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file from current `main` in full before development. Never infer project state only from ChatGPT memory. Update this file after each completed integration cycle.

## CURRENT MAIN / ARCHITECTURE
Current tested functional integration baseline: `b319b4d271bc8ae30bd6a84fe19974509946715f` after PR #219.

Recent integrated sequence:
- PR #210 (`d04c068c28d5ef0de672b0a2a25f042ef53ea361`) added research-only 6h/12h/24h/48h/72h/7d tradeable-move discovery and dashboard preparation without fabricating unsupported rows.
- PR #211 exact head `95411e569a5729199aecebf170938eeaaac9a0db` passed Security and Reliability #1532 and merged as `2a6b073e2b533d6c29b75a55469a2ff235c64e91`. It added governed persisted production opportunity generation for all six horizons, exact-horizon deadlines, horizon-specific calibration/genuine-forward chronology and dashboard reads. New horizons begin WAIT/LEARNING.
- PR #213 exact head `edaae28154bdb6d3501581476a55b6541a3fa1d7` passed Security and Reliability #1543 and merged as `555c8f5030d61d9e40e8ab24519f1a8f03739cff`. The combined dashboard defaults to `all`; main push Security and Reliability #1545 also passed.
- PR #215 state-only synchronization passed exact-head Security and Reliability #1577 and merged as `1e3043796cdfeea86ea7a9bf82a3092332e9d673`.
- PR #214 exact head `5baa20db1ad3ef07f7efd55cc11dff5c49fe3e69` passed Security and Reliability #1574 and merged as `1e21335847b7a15a32c5d9a04f6efcc0382f78f5`. It added the FFriZz-inspired secondary six-horizon shadow family, research/shadow-only with zero production, paper, broker or promotion authority.
- PR #216 exact head `59341f3e93e99ec6ddc000280325e67256a1a4f9` passed Security and Reliability #1585 and merged as `4102c3c08f4fbb901c9e791e3ac15b3d77719bb1`. It added prospective FFriZz SHADOW_BUY/SHADOW_SELL collection inside the existing bounded adaptive-accuracy lane, using full-horizon bucket identity and exact deadlines, never persisting WAIT as directional evidence and adding no worker/service/concurrency/cost.
- PR #217 exact head `325e9295a6c2cb820bd8d889f69d27b4849d949d` passed Security and Reliability #1591 and merged as `5ed36f22faa769e88c73e2dbfd769494ba4c0ef5`. It hardened FFriZz evidence semantics: pooled cross-symbol diagnostics are descriptive/non-independent and ineligible for validation evidence; historical OHLC-only diagnostics do not match the prospective OI-capable fingerprint; family agreement is not called statistically independent.
- PR #218 synchronized this state through PR #217 and merged as `b50556b82360c29d7d0bf57beb4e1fbc749cb52c`.
- PR #219 exact head `c7459f1474a25d829f2a52e41ff2c23dff4caeff` passed Security and Reliability #1600 and merged as `b319b4d271bc8ae30bd6a84fe19974509946715f`. It fixed a confirmed FFriZz forward-evidence persistence defect: the collector previously generated textual `scan_id` values such as `ffrizz:...` while live `prediction_ledger.scan_id` is UUID, so eligible inserts failed closed. The collector now uses deterministic UUIDv5 IDs keyed by immutable system+horizon+full-horizon bucket. Regression tests require UUID-shaped stable same-bucket identity and next-bucket separation. No signal threshold, paper behavior, production authority, broker capability, worker count, paid service or cost changed.

Production: GitHub -> Render -> Python/FastAPI V3 -> Supabase. Production scans run about every 15 minutes. The governed opportunity stream supports 6h, 12h, 24h, 48h, 72h and 7d. Continuous research/backtesting runs on the existing Render coordinator with bounded heavy concurrency under the USD 30/month recurring-infrastructure ceiling.

Primary production Render service: `srv-dadliegu01pc73bc7t50` (`tradingview-ai-crypto`).
Continuous research coordinator: `srv-dafgtead0e5s73cc7ekg`.
Supabase project: `dxgksvzibucwuzmppoqy`.
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed.

Always-on research architecture includes bounded Python workers, autonomous research-director coordination, deterministic quant-science experiment factory, fail-closed heavy-experiment admission firewall, adaptive-accuracy lane sharing the existing heavy slot, 256 active token-free logical specialists per refresh, durable research memory in Supabase, non-overlapping full-horizon calibration/forward-proof logic, research-only meta-WAIT/regime×strategy/economic-calibration/cross-sectional/residual/prospective-microstructure/ensemble-diversity/error-attribution/selective-WAIT/A+ meta-signal diagnostics, exact-key single-flight historical-data coordination without freshness relaxation, authentic paper LONG and paper-only Kraken perpetual SHORT execution with conservative visible-depth/fee/slippage/funding assumptions, retryable `TECHNICAL_BLOCKED` execution/data incidents, and FFriZz prospective shadow evidence collection inside existing bounded compute only.

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
- new 6h/12h/48h/72h horizons accumulate their own independent forward proof and may not borrow evidence from 24h/7d;
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
- FFRIZZ SECONDARY V1 — prospective research/shadow challenger only. Historical pooled diagnostics are descriptive and cannot be used as validation evidence. PR #219 restored the ability of eligible future-only rows to persist with schema-valid deterministic UUID scan IDs; no edge is claimed until genuine resolved non-overlapping evidence accumulates.

### ACC-002 current bounded evidence
Recent live coordinator observability showed 24h 28/30 symbols resolved with 2 `InsufficientHistory` and only Top-15 subset supported; 7d 14/30 resolved with 16 `InsufficientHistory` and no supported liquidity subset. Both remained `insufficient_supported_liquidity_subsets` with untouched OOS closed. Do not lower `minimum_subset_coverage=0.80`, remove the two-supported-subset requirement, substitute lower-ranked assets, shorten required history, fabricate/backfill history, or repeatedly spend scarce cycles re-diagnosing pure `InsufficientHistory` outcomes.

## LIVE OPERATIONAL EVIDENCE
Immediately before PR #219, both production and research coordinator were live on state-sync main `b50556b82360c29d7d0bf57beb4e1fbc749cb52c`.

A read-only live schema check confirmed `prediction_ledger.scan_id` is PostgreSQL `uuid`. At the same sampled instant there were zero persisted `FFRIZZ_SECONDARY_V1` prediction-ledger rows despite the forward collector being integrated. Inspection found the collector generated non-UUID textual IDs and its caller deliberately caught persistence exceptions fail-closed. This was a research evidence-generation failure, not a production/trading safety failure. PR #219 fixes the identity mismatch without weakening any gate.

Read-only Supabase evidence during the PR #219 cycle showed:
- fresh production opportunity/prediction rows continue to be generated across all six horizons and remain production `WAIT` in the sampled slice;
- `research_learning_state` remained at zero conclusive trials and zero lessons, so no adaptive evidence claim exists yet;
- authentic paper account baseline remained exactly $100,000; sampled equity was about $102,356, realized P&L about $3,235 and max drawdown about 1.92%. These are authentic paper operational values only, not evidence of live profitability or strategy proof;
- `live_promotions.json` remained empty.

PR #219 exact head `c7459f1474a25d829f2a52e41ff2c23dff4caeff` passed unit tests, dependency audit, static security scan and committed-secret checks in Security and Reliability #1600 before merge. Both Render services automatically began deploying merge commit `b319b4d271bc8ae30bd6a84fe19974509946715f`; verify both reach `live` before treating the deployment as fully healthy. The first post-deploy eligible FFriZz collection should be checked read-only for actual persisted UUID rows; absence can still be legitimate if the fixed scorer emits only WAIT, so do not fabricate or force a forecast.

Recent raw overlapping production prediction rows must not be treated as independent accuracy evidence. Only canonical de-overlapped diagnostics may support inference.

## COST / SPEED POLICY
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed. Prefer existing shared Render compute, deterministic Python, free/public defensible data, caching/reuse, early rejection and bounded concurrency. No paid feed/service/compute without explicit approval.

The token-free specialist factory uses zero normal-operation AI calls. Heavy experiment admission remains capped at one. API/model spending remains separately budget-gated.

Preserve exact strategy fingerprints while genuine forward observations accumulate. Challengers may run in shadow. Never count overlapping forecasts as independent, lower forward-proof thresholds, reset paper history, raise heavy concurrency, stretch data freshness, change source behavior or cherry-pick thresholds merely to accelerate results.

Blind RSI/MACD/EMA parameter permutations without a diagnosed resolved-error mechanism are deprioritized. Redundant ensemble members, repeated falsified hypotheses without materially new evidence, repeated ACC-002 investigation while failures are purely `InsufficientHistory`, and worker-count expansion without measured information-value benefit are also deprioritized.

Relevant external research ideas for later falsifiable challengers include scale-invariant order-flow/microstructure representations, regime-conditioned order-flow imbalance, and cross-sectional ranking/anchoring/reversal effects. They are hypotheses only. Require timestamp-safe available data, predeclared design, realistic costs, chronological validation and multiple-testing protection.

## CURRENT OPEN DEVELOPMENT
PRs #214, #215, #216, #217, #218 and #219 are integrated and must not be re-applied.
PRs #34, #33 and #13 remain stale against current main and must not be merged as-is without a fresh compatibility/relevance review.
PR #212 is superseded by #214. PR #205 is superseded by #207. PR #206 was branch reconciliation. PR #180 is stale state-only work. PR #166 and #140 are superseded.

Persistent specialist priorities live in `orchestration/specialist_coordination.json`. The accuracy/profitability roadmap lives in `orchestration/accuracy_profitability_roadmap.json`.

## EXACT NEXT STEP
1. Verify PR #219 reaches `live` on both Render production and coordinator services. No rollback unless canary or operational evidence indicates a real regression.
2. After the next natural adaptive/FFriZz collection cycle, query `prediction_ledger` read-only for `FFRIZZ_SECONDARY_V1`. If eligible SHADOW_BUY/SHADOW_SELL signals occurred, confirm their `scan_id` values are persisted UUIDs, bucket identity is non-overlapping and deadlines are exact. If there are still no rows, distinguish legitimate all-WAIT output from a technical persistence failure before changing anything.
3. Let the first prospective FFriZz rows resolve naturally. Analyze false positives/false negatives by horizon, direction, regime/proxy context, family availability and after-cost outcome without changing thresholds from the same evidence slice.
4. Prioritize the next challenger by expected information gain and after-cost signal-quality impact. Regime-conditioned microstructure/order-flow and cross-sectional rank/anchoring/reversal ideas are worth predeclared tests only when point-in-time data availability is defensible.
5. Continue accumulating genuine non-overlapping forward evidence separately for every production horizon. New horizons remain WAIT/LEARNING until all canonical gates pass.
6. Keep ACC-002 fail-closed while the blocker remains natural history. Do not weaken coverage, chronology, point-in-time universe or untouched-OOS requirements.
7. Keep `live_promotions.json` empty, broker disconnected, signing keys unused, paper baseline immutable, heavy concurrency bounded and recurring infrastructure within USD 30/month until genuine governed evidence plus explicit approval justifies any change.
