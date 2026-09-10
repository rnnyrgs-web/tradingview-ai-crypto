# AI DEVELOPMENT STATE
Last updated: 2026-09-10

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file from current `main` in full before development. Never infer project state only from ChatGPT memory. Update this file after each completed integration cycle.

## CURRENT MAIN / ARCHITECTURE
Current tested functional integration baseline after PR #223: `14318165650e2c9ca46146347c40dec2a252506c`.

Recent integrated sequence relevant to current architecture:
- #210/#211/#213 established governed persisted 6h/12h/24h/48h/72h/7d opportunity generation, exact-horizon deadlines, horizon-specific calibration/genuine-forward chronology, and all-horizon dashboard reads while new horizons remain WAIT/LEARNING.
- #214 added the FFriZz-inspired secondary six-horizon family as research/shadow only, with zero production, paper, broker, or promotion authority.
- #216 added prospective FFriZz SHADOW_BUY/SHADOW_SELL collection inside the existing bounded adaptive-accuracy lane, using full-horizon bucket identity and exact deadlines.
- #217 hardened FFriZz scientific semantics: cross-symbol pooled diagnostics are descriptive/non-independent, OHLC-only historical diagnostics do not match the prospective OI-capable fingerprint, and feature-family agreement is not treated as proven independence.
- #219 fixed FFriZz `scan_id` persistence to deterministic UUIDv5 keyed by system+horizon+full-horizon bucket.
- #221 fixed the canonical action contract: FFriZz shadow action remains research metadata, immutable direction remains LONG/SHORT, and `action_at_forecast` remains WAIT.
- #223 exact head `d5b3c353ff54d73a8673c1026cbc522a5d0ebc40` passed Security and Reliability #1619 and merged as `14318165650e2c9ca46146347c40dec2a252506c`. A live Supabase schema audit showed `prediction_ledger.score` is constrained to 0..100 while FFriZz raw scores are signed. Eligible SHORT rows therefore carried negative ledger scores and could reject the entire insert batch. #223 maps only the persisted ledger score to absolute shadow strength, preserves the original signed raw score in calibration metadata, and adds regression coverage. Direction, thresholds, strategy identity, canonical WAIT action, trade/paper/broker/promotion authority, paper history, worker count, and cost policy are unchanged.

Production: GitHub -> Render -> Python/FastAPI V3 -> Supabase. Production scans run about every 15 minutes. The governed opportunity stream supports 6h, 12h, 24h, 48h, 72h and 7d. Continuous research/backtesting runs on the existing Render coordinator with bounded heavy concurrency under the USD 30/month recurring-infrastructure ceiling.

Primary production Render service: `srv-dadliegu01pc73bc7t50` (`tradingview-ai-crypto`).
Continuous research coordinator: `srv-dafgtead0e5s73cc7ekg`.
Supabase project: `dxgksvzibucwuzmppoqy`.
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed.

Always-on research architecture includes bounded Python workers, autonomous research-director coordination, deterministic quant-science experiment factory, fail-closed heavy-experiment admission firewall, adaptive-accuracy lane sharing the existing heavy slot, 256 active token-free logical specialists per refresh, durable research memory in Supabase, non-overlapping full-horizon calibration/forward-proof logic, research-only meta-WAIT/regime×strategy/economic-calibration/cross-sectional/residual/prospective-microstructure/ensemble-diversity/error-attribution/selective-WAIT/A+ meta-signal diagnostics, exact-key single-flight historical-data coordination without freshness relaxation, authentic paper LONG and paper-only Kraken perpetual SHORT execution with conservative visible-depth/fee/slippage/funding assumptions, retryable `TECHNICAL_BLOCKED` incidents, and FFriZz prospective shadow evidence collection inside existing bounded compute only.

Logical scale must never be confused with physical compute scale. Heavy experiment concurrency remains capped at one admitted heavy experiment at a time unless a separately reviewed change proves a safe/cost-valid reason to alter it.

## SAFETY INVARIANTS
No AI opinion, ranking score, evidence score, order-book snapshot, paper P&L, ensemble weight, historical diagnostic, single OOS result, research-memory lesson, experiment priority, market-consensus provenance, microstructure snapshot, FFriZz diagnostic, FFriZz forward row, or paper result by itself may authorize live BUY/SELL.

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
- FFriZz direction is encoded in immutable LONG/SHORT. The ledger `score` is a nonnegative 0..100 strength field; the signed FFriZz research score must remain preserved separately as `calibration.raw_score` and must never be inferred back from ledger score sign;
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
- FFRIZZ SECONDARY V1 — prospective research/shadow challenger only. Historical pooled diagnostics are descriptive and ineligible as validation evidence. #219, #221, and #223 fixed the UUID, action-enum, and score-range persistence contracts respectively. No edge is claimed until genuine resolved non-overlapping evidence accumulates.

### ACC-002 bounded evidence policy
Recent live coordinator evidence remains dominated by `InsufficientHistory`; untouched OOS stays closed. Do not lower `minimum_subset_coverage=0.80`, remove the two-supported-subset requirement, substitute lower-ranked assets, shorten required history, fabricate/backfill history, or repeatedly spend scarce cycles re-diagnosing pure `InsufficientHistory` outcomes. Natural history accumulation is the blocker unless live evidence materially changes.

## LIVE OPERATIONAL EVIDENCE
PR #223 exact-head Security and Reliability #1619 completed successfully, including unit tests, dependency vulnerability audit, static security scan, and committed-secret checks. `main` had not moved while the PR was tested, so #223 was merged only after exact-head compatibility was confirmed.

Both production and the research coordinator successfully reached `live` on merge commit `14318165650e2c9ca46146347c40dec2a252506c`.

Read-only Supabase schema inspection during the #223 cycle confirmed:
- `prediction_ledger.scan_id` is UUID;
- `action_at_forecast` accepts only TRADE or WAIT;
- direction accepts LONG or SHORT;
- all six canonical horizons are accepted;
- `score` is constrained to 0..100;
- uniqueness remains `(scan_id, symbol, horizon)`.

Immediately before #223, read-only queries still showed zero `FFRIZZ_SECONDARY_V1` prediction rows. This does not prove another defect by itself because the bounded adaptive collector must naturally run and produce a genuine source SHADOW_BUY/SHADOW_SELL. However, the live schema plus signed FFriZz scorer proved that any eligible SHORT would have violated the ledger score constraint and a mixed insert batch could fail. #223 corrects that contract without changing signal semantics.

The latest sampled persisted production opportunity sets contained all six horizons and remained production WAIT-only. Production abstention therefore remained intact.

Authentic paper account remained based on exactly $100,000. During the #223 audit the paper account showed approximately $101,971 equity and about $2,670 realized P&L, with 3 open and 11 closed paper trades. These are paper operational observations only, not evidence of live profitability or strategy proof.

Coordinator evidence showed healthy bounded research execution with no worker failures/timeouts in the sampled logs, 256 logical specialists, zero normal-operation AI calls, no observed history-fetch failure in the sampled cycle, and ACC-002 still fail-closed on insufficient supported liquidity subsets.

Recent raw overlapping production prediction rows must not be treated as independent accuracy evidence. Only canonical de-overlapped diagnostics may support inference.

## COST / SPEED POLICY
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed. Prefer existing shared Render compute, deterministic Python, free/public defensible data, caching/reuse, early rejection, and bounded concurrency. No paid feed/service/compute without explicit approval.

The token-free specialist factory uses zero normal-operation AI calls. Heavy experiment admission remains capped at one. API/model spending remains separately budget-gated.

Preserve exact strategy fingerprints while genuine forward observations accumulate. Challengers may run in shadow. Never count overlapping forecasts as independent, lower forward-proof thresholds, reset paper history, raise heavy concurrency, stretch data freshness, change source behavior, or cherry-pick thresholds merely to accelerate results.

Blind RSI/MACD/EMA parameter permutations without a diagnosed resolved-error mechanism are deprioritized. Redundant ensemble members, repeated falsified hypotheses without materially new evidence, repeated ACC-002 investigation while failures are purely `InsufficientHistory`, and worker-count expansion without measured information-value benefit are also deprioritized.

## CURRENT OPEN DEVELOPMENT
PR #223 is integrated and must not be re-applied. PRs #214/#216/#217/#219/#221 are also integrated functional prerequisites. State-only sync PRs through #222 are integrated.
PRs #34, #33 and #13 remain stale against current main and must not be merged as-is without a fresh compatibility/relevance review. #212 is superseded by #214; #205 by #207; #206 was branch reconciliation; #180 is stale state-only work; #166 and #140 are superseded.

Persistent specialist priorities live in `orchestration/specialist_coordination.json`. The accuracy/profitability roadmap lives in `orchestration/accuracy_profitability_roadmap.json`.

## EXACT NEXT STEP
1. After the next natural adaptive/FFriZz collection cycle, query `prediction_ledger` read-only for `FFRIZZ_SECONDARY_V1`.
2. If a source SHADOW_BUY/SHADOW_SELL occurred, validate that each row has deterministic UUID `scan_id`, immutable LONG/SHORT direction, canonical WAIT action, nonnegative bounded ledger strength, signed `calibration.raw_score`, preserved `shadow_action`, exact due_at, and non-overlapping full-horizon bucket identity.
3. If FFriZz rows remain zero, distinguish legitimate all-WAIT source output from persistence failure using persisted worker evidence/logs; never synthesize a forecast to force a row.
4. Let first valid FFriZz rows resolve naturally. Do not promote or tune from unresolved, overlapping, fingerprint-mismatched, or historically backfilled evidence.
5. Continue normal resolved-error diagnostics, selective-WAIT, regime×strategy, economic calibration, cross-sectional/residual, prospective microstructure, and ensemble-diversity research using evidence-value scheduling.
6. Preserve ACC-002 natural-history fail-closed behavior while failures remain pure `InsufficientHistory`.
7. Keep `live_promotions.json` empty, broker disconnected, signing keys unused, authentic paper history immutable, heavy concurrency bounded, and recurring infrastructure under USD 30/month.
8. Every future integration still requires an isolated branch, confirmed-defect regression tests where applicable, exact-head Security and Reliability, current-main compatibility review, and post-deploy health verification. No profitability or accuracy claim is justified by #223 itself.
