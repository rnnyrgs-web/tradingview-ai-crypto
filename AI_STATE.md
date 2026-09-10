# AI DEVELOPMENT STATE
Last updated: 2026-09-10

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file from current `main` in full before development. Never infer project state only from ChatGPT memory. Update this file after each completed integration cycle.

## CURRENT MAIN / ARCHITECTURE
Current tested functional integration baseline after PR #227: `6fc6f9ad16bd4e89ec93aa3ce93d12e9ec085a54`.

Recent integrated sequence relevant to current architecture:
- #210/#211/#213 established governed persisted 6h/12h/24h/48h/72h/7d opportunity generation, exact-horizon deadlines, horizon-specific calibration/genuine-forward chronology, and all-horizon dashboard reads while new horizons remain WAIT/LEARNING.
- #214 added the FFriZz-inspired secondary six-horizon family as research/shadow only, with zero production, paper, broker, or promotion authority.
- #216 added prospective FFriZz SHADOW_BUY/SHADOW_SELL collection inside the existing bounded adaptive-accuracy lane, using full-horizon bucket identity and exact deadlines.
- #217 hardened FFriZz scientific semantics: cross-symbol pooled diagnostics are descriptive/non-independent, OHLC-only historical diagnostics do not match the prospective OI-capable fingerprint, and feature-family agreement is not treated as proven independence.
- #219 fixed FFriZz `scan_id` persistence to deterministic UUIDv5 keyed by system+horizon+full-horizon bucket.
- #221 fixed the canonical action contract: FFriZz shadow action remains research metadata, immutable direction remains LONG/SHORT, and `action_at_forecast` remains WAIT.
- #223 maps the persisted FFriZz ledger score to nonnegative absolute shadow strength because `prediction_ledger.score` is constrained to 0..100; signed raw score remains immutable research metadata.
- #225 added bounded read-only `ffrizz_forward` coordinator observability so all-WAIT source output can be distinguished from collection failure without exposing raw rows or changing authority.
- #227 exact head `0f25610245cdd3baa0dd0f5871b9e2931ef905ef` passed Security and Reliability #1639 before squash merge as `6fc6f9ad16bd4e89ec93aa3ce93d12e9ec085a54`. Live evidence had shown repeated FFriZz cycles reporting `collection_ok=true` with 3-6 eligible forecasts while the canonical ledger contained zero FFriZz rows. Because `db.insert_prediction_ledger()` intentionally no-ops when Supabase is unconfigured, the adaptive lane could falsely report successful collection. #227 now reports `PredictionLedgerNotConfigured` and `ok=false` whenever an eligible FFriZz cycle lacks the canonical ledger connection. Zero-eligible/all-WAIT cycles remain successful because no write is required. This is observability/research-integrity hardening only.

Production: GitHub -> Render -> Python/FastAPI V3 -> Supabase. Production scans run about every 15 minutes. The governed opportunity stream supports 6h, 12h, 24h, 48h, 72h and 7d. Continuous research/backtesting runs on the existing Render coordinator with bounded heavy concurrency under the USD 30/month recurring-infrastructure ceiling.

Primary production Render service: `srv-dadliegu01pc73bc7t50` (`tradingview-ai-crypto`).
Continuous research coordinator: `srv-dafgtead0e5s73cc7ekg`.
Supabase project: `dxgksvzibucwuzmppoqy`.
Hard recurring infrastructure ceiling: USD 30/month unless explicitly approved otherwise.

The always-on research architecture includes bounded Python workers, an autonomous research director, deterministic quant-science experiment factory, fail-closed heavy-experiment admission, adaptive-accuracy lane, 256 token-free logical specialists per refresh, durable research-memory support, economic calibration/meta-WAIT, regime×strategy diagnostics, cross-sectional/residual diagnostics, prospective microstructure vetoes, ensemble-diversity/error-attribution diagnostics, selective-WAIT fusion, and evidence-value scheduling. Logical specialist scale is not physical compute scale. Heavy experiment concurrency remains capped at one admitted heavy experiment at a time unless separately reviewed and cost-approved.

## SAFETY INVARIANTS
No AI opinion, ranking score, evidence score, dashboard value, paper P&L, model count, ensemble weight, current order-book snapshot, historical diagnostic, research-memory lesson, experiment priority, FFriZz shadow signal, prospective FFriZz row, or single OOS/forward result may authorize live BUY/SELL by itself.

Mandatory chain:
RESEARCH -> BACKTEST -> VALIDATION -> UNTOUCHED OOS -> ROBUSTNESS/STABILITY -> MULTIPLE-TESTING FIREWALL -> POINT-IN-TIME UNIVERSE SAFETY -> STRATEGY-REGISTRY APPROVAL -> PRODUCTION-RISK APPROVAL -> GENUINE FORWARD PROOF -> GLOBAL/EXECUTION RISK CLEAR -> LIVE BUY/SELL.

Every later stage is restrictive-only. Missing, stale, contradictory, malformed, overlapping-only, insufficient, illiquid, execution-unsafe, portfolio-unsafe, statistically weak, survivorship-unsafe, persistence-unsafe, label-unsafe, chronology-unsafe, or system-unsafe evidence means `WAIT / NO TRADE / RESEARCH_ONLY`.

`live_promotions.json` remains empty. Signing keys remain unused. Broker remains disconnected. Do not add credentials or real-order capability without explicit user approval plus all canonical evidence gates.

Authentic paper account baseline remains exactly `$100,000` from `2026-09-08T01:17:49Z`. Never reset, rewrite, replace, or manufacture its history. Paper performance is evidence only.

## SCIENTIFIC RESEARCH DISCIPLINE
Chronological validation remains development -> validation -> untouched holdout/OOS. Robustness includes deterministic resampling, parameter perturbation, regime stability, conservative execution-cost stress, search-breadth protection, and genuine forward confirmation. Genuine forward proof counts only non-overlapping full-horizon resolved forecasts for the exact immutable strategy fingerprint.

Core invariants:
- no lookahead or leakage;
- no threshold or parameter mining against untouched OOS;
- no OOS reuse as fresh confirmation;
- no pooling historical/OOS evidence with genuine-forward evidence to inflate confidence;
- no survivorship substitution for missing point-in-time universe evidence;
- no historical backfill of prospective order-book, consensus, cross-sectional, leadership, funding, OI, or other timestamp-sensitive fields;
- realistic fees, spread, slippage, funding/carry and execution assumptions remain mandatory;
- repeated/disproven hypotheses receive a research-memory penalty rather than blind recycling;
- idea generation is not evidence;
- overlapping forecasts are never independent observations;
- simultaneous cross-symbol crypto outcomes are not automatically independent;
- feature-family agreement is not statistical independence unless demonstrated;
- malformed, missing or delayed outcome chronology fails closed rather than fabricating labels;
- research scheduling must prefer falsifiable, actionable, evidence-efficient experiments and penalize blocked/redundant/expensive low-information work;
- untouched OOS remains sealed until predeclared validation admission passes;
- production WAIT rows may be studied through immutable shadow direction but research may not mutate production action;
- FFriZz historical OHLC-only diagnostics are descriptive because historical OI is unavailable; they do not match the prospective OI-capable fingerprint and cannot be counted as validation evidence for that fingerprint;
- FFriZz prospective source action remains research metadata, canonical `action_at_forecast` remains WAIT, direction remains LONG/SHORT, and ledger score is nonnegative strength while signed raw score remains separately preserved;
- FFriZz eligible collection is not successful evidence collection unless the canonical prediction-ledger persistence path is configured and the write can be attempted; absent persistence must report fail-closed rather than false success;
- paper technical/data failures remain retryable and must never become fabricated fills;
- hourly self-improvement review must not force paid model calls, bypass successful-run cooldowns/budgets, raise physical concurrency, or change production authority.

## ACCURACY / RESEARCH PROGRAM
- ACC-001 MARKET / EXECUTION REALISM — COMPLETE.
- ACC-002 CROSS-ASSET RANK RESEARCH — FAIL-CLOSED before untouched OOS because required historical coverage remains insufficient. Do not lower `minimum_subset_coverage=0.80`, remove the two-supported-subset requirement, substitute lower-ranked assets, shorten required history merely to pass, fabricate/backfill history, or repeatedly spend scarce cycles re-diagnosing pure `InsufficientHistory` outcomes.
- ACC-003 through ACC-014 safety/validation layers — COMPLETE.
- SELECTIVE PRECISION / ECONOMIC META-WAIT / REGIME×STRATEGY / ECONOMIC CALIBRATION / SELECTIVE-WAIT FUSION / A+ META-SIGNAL TRUST / CROSS-SECTIONAL-RESIDUAL / MICROSTRUCTURE VETO / ENSEMBLE DIVERSITY / ERROR ATTRIBUTION — research-only governed diagnostics. None creates production authority.
- FFriZz secondary family — research/shadow only. Historical diagnostics are descriptive; prospective immutable forward evidence is the only route toward later governed validation. No tuning, promotion, or accuracy claim may be made from unresolved rows or pooled descriptive history.
- New-horizon genuine-forward sample sufficiency remains restrictive-only. Existing thresholds are not lowered; 6h/12h require at least 30 independent forward samples, 48h requires at least 20, and 72h requires at least 16 before sample sufficiency, with all later gates still mandatory.

## CURRENT LIVE EVIDENCE / OPERATIONS
Immediately before #227, the coordinator repeatedly completed FFriZz cycles with worker exit 0, `collection_ok=true`, 3-6 eligible source shadow forecasts, full-horizon non-overlap enabled, WAIT rows not persisted, historical OI backfill disabled, and zero worker failures/timeouts. A direct read-only Supabase audit nevertheless found zero FFriZz rows in `prediction_ledger`. This contradiction is a material persistence/configuration issue, not signal-performance evidence. #227 makes the next natural cycle report the missing-ledger configuration explicitly instead of false success when that is the cause.

Current ACC-002 samples remain naturally blocked by `InsufficientHistory`; untouched OOS stays closed. Do not convert this into a software failure unless failure types change.

The coordinator has otherwise remained healthy, with zero observed worker failures/timeouts in the sampled window and no reason to increase worker count or heavy concurrency. Network history latency can vary; optimize only from measured bottlenecks without stretching freshness/provenance semantics.

GitHub `main` branch protection has previously been reported disabled. Exact-head Security and Reliability, expected-head merge protection, isolated branches and current-main compatibility review remain mandatory operational controls.

Cross-exchange/public-data collection may be unavailable at times. Never manufacture consensus, microstructure, history, agreement data, outcome labels, cross-sectional fields, funding, perpetual contract metadata, OI, or error causes when source evidence is unavailable or temporally invalid.

## COST / SPEED POLICY
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed by the user. Prefer existing shared Render compute, deterministic Python, free/public defensible data, caching/reuse, early rejection and bounded concurrency. No paid feed/service/compute without explicit approval.

The token-free specialist factory uses zero normal-operation AI calls. Heavy experiment admission remains capped at one. API/model spending remains separately budget-gated. Do not increase logical workers merely for appearance; require measured information-value benefit.

Preserve exact strategy fingerprints while genuine forward observations accumulate. Challengers may run in shadow. Blind RSI/MACD/EMA parameter permutations, duplicate ensemble members, repeated falsified hypotheses without materially new evidence, repeated pure-InsufficientHistory ACC-002 cycles, and worker-count expansion without demonstrated information value are deprioritized.

## CURRENT OPEN DEVELOPMENT
PR #227 is integrated and must not be re-applied. Older FFriZz PRs #214/#216/#217/#219/#221/#223/#225 are integrated. Stale PRs #34, #33 and #13 remain incompatible with current main and must not be merged as-is without fresh relevance/compatibility review. Superseded historical branches/PRs remain superseded unless current evidence independently justifies rebuilding them on current main.

Persistent specialist priorities live in `orchestration/specialist_coordination.json`. The accuracy/profitability roadmap lives in `orchestration/accuracy_profitability_roadmap.json`.

## EXACT NEXT STEP
1. Wait for the first natural adaptive/FFriZz cycle after #227 deployment and inspect bounded `ffrizz_forward` observability.
2. If eligible forecasts >0 and `error_type=PredictionLedgerNotConfigured`, treat the missing coordinator prediction-ledger configuration as confirmed. Do not weaken the code. Restoring the required Supabase connection requires the existing correct service credentials; never invent, expose, or copy secrets through chat. If credentials cannot be safely reused through the authorized service configuration, request explicit user action/approval rather than bypass persistence.
3. If collection reports `ok=true` with eligible forecasts >0, immediately query `prediction_ledger` read-only and verify actual rows exist. Validate UUID scan identity, LONG/SHORT direction, canonical WAIT action, score within 0..100, signed `calibration.raw_score`, preserved `shadow_action`, exact due_at, and full-horizon bucket identity.
4. If collection reports `ok=true` with eligible=0, treat it as legitimate source abstention; do not loosen FFriZz thresholds to create activity.
5. Let valid prospective rows resolve naturally before any precision/expectancy comparison. Use only exact fingerprint, non-overlapping full-horizon evidence and realistic costs. No unresolved-row tuning or production promotion.
6. Continue using resolved primary-system errors, calibration, regime behavior, cross-sectional information, microstructure, execution realism and research-memory outcomes to prioritize falsifiable high-information experiments. Prefer evidence generation over cosmetic changes.
7. Keep ACC-002 blocked while failures remain pure `InsufficientHistory`; do not weaken history or coverage rules.
8. Keep `live_promotions.json` empty, broker disconnected, signing keys unused, authentic paper baseline/history immutable, heavy concurrency bounded, and recurring infrastructure <= USD 30/month.
9. For every future integration: isolated branch -> regression tests for confirmed defects -> exact-head Security and Reliability -> current-main compatibility -> expected-head merge -> AI_STATE.md synchronization -> post-deploy production/coordinator health verification.
