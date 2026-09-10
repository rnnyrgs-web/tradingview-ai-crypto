# AI DEVELOPMENT STATE
Last updated: 2026-09-10

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file from current `main` in full before development. Never infer project state only from ChatGPT memory. Update this file after each completed integration cycle.

## CURRENT MAIN / ARCHITECTURE
Current tested functional integration baseline after PR #242: `f1d451cd02cb5a4a04ba80d313cb4539e1ec24d7`. PR #242 exact head `1abd76a6319ed7b495c9785e5006773cf6409a31` passed Security and Reliability #1732 before squash merge after a clean current-main compatibility review. It closes the post-#236 live V2 observability gap by carrying only re-allowlisted count-only 6h/12h/24h FFriZz V2 feature-availability diagnostics through the final private coordinator log boundary. It does not alter V1/V2 scoring, thresholds, persistence, paper/production behavior, broker/promotion authority, worker concurrency, or recurring cost. The prior PR #239 calibration-freshness behavior remains intact and was observed in a scheduled workflow with `Evaluate previous signals` executing before `Run production market scan`.

Production is GitHub -> Render -> Python/FastAPI V3 -> Supabase. The governed opportunity stream supports 6h, 12h, 24h, 48h, 72h and 7d. New horizons remain WAIT/LEARNING unless all canonical gates are independently satisfied. Production scans run about every 15 minutes. Continuous research/backtesting uses the existing Render coordinator with bounded concurrency.

Primary production service: `srv-dadliegu01pc73bc7t50` (`tradingview-ai-crypto`).
Continuous research coordinator: `srv-dafgtead0e5s73cc7ekg`.
Supabase project: `dxgksvzibucwuzmppoqy`.
Recurring infrastructure ceiling: USD 30/month unless explicitly approved otherwise.

Important integrated sequence:
- #210/#211/#213: governed persisted multi-horizon opportunity generation, exact-horizon deadlines, horizon-specific calibration/genuine-forward chronology and all-horizon dashboard reads.
- #214/#216: FFriZz-inspired six-horizon secondary family and prospective collection, strictly research/shadow only.
- #217: FFriZz pooled cross-symbol diagnostics are descriptive/non-independent; OHLC-only historical diagnostics do not match the prospective OI-capable fingerprint; feature-family agreement is not assumed independent.
- #219: deterministic UUIDv5 scan identity by system+horizon+full-horizon bucket.
- #221: canonical FFriZz action remains WAIT; source SHADOW_BUY/SHADOW_SELL is research metadata; immutable direction remains LONG/SHORT.
- #223: persisted score uses nonnegative absolute shadow strength while signed raw score remains research metadata.
- #225: bounded read-only `ffrizz_forward` coordinator observability.
- #227: eligible FFriZz collection fails closed as `PredictionLedgerNotConfigured` if canonical ledger persistence is unavailable; zero-eligible/all-WAIT cycles remain legitimate success because no write is required.
- #229 exact head `9bb0f83c07ef0b6de82fdce824ac702887215e0b` passed Security and Reliability #1648 before squash merge as `ff355d411698aafb9a086026d43dfb72fdadcd7c`. It adds fixed-gate abstention diagnostics without changing thresholds or decisions.
- #231 exact head `e938ddd60c31f4ba74496178f1310c8d5172bc77` passed Security and Reliability #1658 before squash merge as `70c75e943febb89658a47e2bda9d9450229abd80`. It carries only sanitized count-level abstention evidence through the existing adaptive/coordinator observability path. Raw ledger rows, arbitrary reason strings and error details remain excluded.
- #232 exact head `606800f7fe9042333626d719ccce97d4cfdae81c` passed Security and Reliability #1662 before state-only merge as `e43e6a3a18ea16eddaeae7aa33fac949b5dc0dac`.
- #233 state-only merge `92cf9c808a5ac626cfe46f85bfa8e7f11136f94a` recorded the first reconciled post-#231 live abstention diagnostic. It changed no runtime behavior or authority.
- #234 state-only merge `d456a3579cdb36946581ad299f4aa5fc960e2b21` recorded the canonical FFriZz ledger-configuration blocker and the V1 OI timestamp-semantics risk.
- #235 merge `28b8200e4189667e5d1aef6037e647b768791e16` added the separately fingerprinted research-only `FFRIZZ_SECONDARY_V2_OI_CLOSE_END` challenger. It matches completed 1H candle-close endpoints exactly to Binance OI period-end endpoints with no interpolation/backfill and preserves V1 unchanged. Its exact PR head `ac66313dc37be9414b5839639e20941a718f5790` passed Security and Reliability #1691. Review after merge found its registration test validated only the orchestration descriptor and did not prove runtime invocation.
- #236 exact head `332f868d48b9a489ad42f25937a3c25c945585a0` passed Security and Reliability #1700 before squash merge as `1a1200cd30575469f7ac9525546f017a0a2c507d`. It closes that runtime-registration gap: the V2 scorer now runs only for the predeclared 6h/12h/24h 1H research horizons inside the existing FFriZz pass, reusing the same already-fetched candles and OI cache. Only bounded count-level V2 feature-availability diagnostics are carried into adaptive research evidence. V2 forecasts are not persisted; V1 persistence semantics and all production/paper/promotion/broker authority remain unchanged.
- #237 state-only merge `0c6d098b733639008320e57a93c4e69a4bc7df54` synchronized authoritative state through #236.
- #239 exact head `8305cb81e083709d37567783c7470f1c840a7592` passed Security and Reliability #1716 before squash merge as `46dd83e6e9e8b2ab0a69a43c7de1fdf5f3f8e0a2`. It reorders the production workflow from scan-then-evaluate to evaluate-then-scan. This removes a one-scan stale-calibration lag without changing evaluation rules, calibration minimums, signal thresholds or production authority.
- #240 state-only merge `8edba9ba0a5568dfad6f07a0e29052ddc9dae85b` synchronized authoritative state through #239.
- #238 exact head `36a9d403c650ef2b838b5c7b5873fd9088cd54ff` passed Security and Reliability #1712 before squash merge as `088ce41ce21c4229bab93c47342821304761ad9a`. It adds bounded actionability diagnostics to persisted calibration metadata and enriches generic paper `not_actionable` audit reasons from the same immutable signal key using a bounded in-process cache. It is observability-only: no TRADE/WAIT decision path, threshold, risk gate, execution-failure semantics, broker authority, paper sizing/fill logic, schema, or recurring cost changed.
- #241 state-only merge `685ad64149fb5019824c3974b9974f37d82f69ed` synchronized authoritative state through #238 and preserved the observed #239 evaluate-before-scan ordering.
- #242 exact head `1abd76a6319ed7b495c9785e5006773cf6409a31` passed Security and Reliability #1732 before squash merge as `f1d451cd02cb5a4a04ba80d313cb4539e1ec24d7`. A first exact-head attempt (#1730) failed unit tests because the new optional V2 log field changed an existing strict dictionary contract; that was corrected on the same isolated branch before the successful exact-head gate. The final implementation re-allowlists only predeclared horizons/family-count keys at the final coordinator log boundary, rejects malformed/non-integer counts, suppresses arbitrary horizons/families/symbol/raw detail, and hard-codes research-only/no-authority semantics. Both Render services reached live on the merged functional commit.

The always-on research architecture includes bounded Python workers, autonomous research-director coordination, deterministic quant-science experiment factory, fail-closed heavy-experiment admission, adaptive-accuracy research, 256 token-free logical specialists per refresh, durable research memory, economic calibration/meta-WAIT, regime×strategy diagnostics, cross-sectional/residual diagnostics, prospective microstructure vetoes, ensemble-diversity/error-attribution diagnostics, selective-WAIT fusion and evidence-value scheduling. Logical specialist scale is not physical compute scale. Heavy experiment concurrency remains capped at one admitted heavy experiment at a time unless separately reviewed and cost-approved.

## SAFETY INVARIANTS
No AI opinion, ranking/evidence score, dashboard value, paper P&L, model count, ensemble weight, order-book snapshot, historical diagnostic, research-memory lesson, experiment priority, FFriZz signal/abstention count, prospective row, V2 feature-availability count, paper rejection diagnostic, or single OOS/forward result may authorize live BUY/SELL by itself.

Mandatory chain:
RESEARCH -> BACKTEST -> VALIDATION -> UNTOUCHED OOS -> ROBUSTNESS/STABILITY -> MULTIPLE-TESTING FIREWALL -> POINT-IN-TIME UNIVERSE SAFETY -> STRATEGY-REGISTRY APPROVAL -> PRODUCTION-RISK APPROVAL -> GENUINE FORWARD PROOF -> GLOBAL/EXECUTION RISK CLEAR -> LIVE BUY/SELL.

Every later stage is restrictive-only. Missing, stale, contradictory, malformed, overlapping-only, insufficient, illiquid, execution-unsafe, portfolio-unsafe, statistically weak, survivorship-unsafe, persistence-unsafe, label-unsafe, chronology-unsafe or system-unsafe evidence means `WAIT / NO TRADE / RESEARCH_ONLY`.

`live_promotions.json` remains empty. Signing keys remain unused. Broker remains disconnected. Do not add credentials or real-order capability without explicit user approval plus all canonical gates.

Authentic paper account baseline remains exactly `$100,000` from `2026-09-08T01:17:49Z`. Never reset, rewrite, replace or manufacture its history. Paper performance is evidence only.

## SCIENTIFIC RESEARCH DISCIPLINE
Chronological validation remains development -> validation -> untouched holdout/OOS. Genuine forward proof counts only non-overlapping full-horizon resolved forecasts for the exact immutable strategy fingerprint. Robustness requires deterministic resampling, parameter perturbation, regime stability, conservative execution-cost stress, search-breadth protection and genuine forward confirmation.

Core invariants:
- no lookahead/leakage, threshold mining, OOS reuse, survivorship substitution or fabricated evidence;
- never pool historical/OOS with genuine forward evidence to inflate confidence;
- never backfill unavailable timestamp-sensitive order-book, consensus, cross-sectional, leadership, funding, OI or other prospective fields;
- overlapping forecasts are not independent; simultaneous cross-symbol crypto outcomes are not automatically independent; model/family count is not independence;
- realistic fees, spread, slippage, funding/carry and execution assumptions remain mandatory;
- untouched OOS remains sealed until predeclared validation admission passes;
- repeated/disproven hypotheses receive research-memory penalties instead of blind recycling;
- malformed/missing/delayed outcome chronology fails closed;
- research scheduling prioritizes falsifiable, actionable, high-information experiments by expected after-cost impact, sample readiness, compute cost and redundancy/overfit risk;
- production WAIT may be studied through immutable research direction but research never mutates production action;
- FFriZz historical OHLC-only diagnostics are descriptive and do not validate the prospective OI-capable fingerprint;
- FFriZz abstention diagnostics explain fixed existing gates only; they may not tune thresholds from unresolved observations or turn WAIT into a forecast;
- FFriZz V1 and V2 are separate research fingerprints and their evidence may not be pooled; V2 currently has diagnostic-only runtime feature-availability measurement and no forward-ledger persistence;
- `unexpected_wait_state` is a rule-drift/integrity alarm, never permission to reinterpret the scorer;
- bounded observability must not expose raw ledger rows, secrets, arbitrary error detail or unbounded payloads;
- paper technical/data failures remain retryable and may never become fabricated fills;
- paper rejection/actionability diagnostics are explanatory only and may not mutate TRADE/WAIT decisions, thresholds, risk gates, execution semantics, fills, sizing, or authority;
- no hourly self-improvement cycle may force paid model calls, bypass cooldown/budget controls, raise physical concurrency or create production authority.

## ACCURACY / RESEARCH PROGRAM
- ACC-001 market/execution realism: complete.
- ACC-002 cross-asset rank research: fail-closed before untouched OOS because historical coverage remains insufficient. Never lower `minimum_subset_coverage=0.80`, the two-supported-subset requirement, Top-N ordering, required history, or untouched-OOS rules merely to pass.
- ACC-003 through ACC-014 safety/validation layers: complete.
- Selective precision, economic meta-WAIT, regime×strategy, economic calibration, selective-WAIT fusion, A+ meta-signal trust, cross-sectional/residual, microstructure veto, ensemble diversity and error attribution remain governed research-only diagnostics.
- FFriZz secondary family remains research/shadow only. Prospective immutable forward evidence is the only route toward governed validation; no pooled history, unresolved row or abstention count is promotion evidence.
- FFriZz V2 OI-close-end challenger remains diagnostic-only until its prospective feature availability and chronology are observed cleanly; no V2 forward rows or promotion evidence exist from #242.
- New-horizon forward sample sufficiency remains restrictive-only: 6h/12h >=30 independent samples, 48h >=20, 72h >=16, with every later canonical gate still required.

## CURRENT LIVE EVIDENCE / OPERATIONS
Read-only Supabase audit during the #229 cycle found zero FFriZz rows in `prediction_ledger`. Repeated post-#227 live cycles were `collection_ok=true`, `error_type=None`, `eligible_shadow_forecasts=0`; therefore those sampled zeros were genuine abstention, not persistence failure.

The first complete live post-#231 abstention diagnostic at generated time `2026-09-10T12:55:55.364213+00:00` scored 72 FFriZz symbol/horizon observations. Action counts were exactly WAIT=72, SHADOW_BUY=0, SHADOW_SELL=0. Fixed-gate attribution reconciled exactly: 57 WAITs had insufficient directional agreement and 15 had enough agreement but score below the predeclared threshold. `unexpected_wait_state=0`. Available-family-count distribution was 0 families for 6 observations and 3 families for 66 observations. Diagnostics explicitly reported `thresholds_unchanged=true`, `backfill_used=false`, and no trade/promotion authority. This is evidence about why the current FFriZz family abstains; it is not evidence that thresholds should be lowered or that the family is profitable/unprofitable.

A later natural live cycle at approximately `2026-09-10T13:04Z` materially changed the persistence diagnosis: the FFriZz scorer produced three eligible SHADOW_SELL forecasts while `ffrizz_forward.collection_ok=false` with `error_type=PredictionLedgerNotConfigured`. The same cycle scored 72 observations with WAIT=69, SHADOW_SELL=3, SHADOW_BUY=0 and `unexpected_wait_state=0`. This proves the coordinator cannot currently persist an otherwise eligible prospective FFriZz forecast. The failure is correctly fail-closed and does not create production or paper authority, but prospective FFriZz evidence accumulation is blocked until the coordinator has a complete canonical Supabase ledger configuration. Later zero-eligible cycles returned `collection_ok=true`, which is expected because no write was required; those later successes do not clear the eligible-write blocker.

Configuration code requires both `SUPABASE_URL` and `SUPABASE_SECRET_KEY` for canonical ledger persistence. Do not commit either credential, substitute a publishable/anonymous key for privileged research persistence, weaken RLS, or create an unauthenticated persistence bypass. The missing secret/configuration must be supplied through the existing Render service environment by an authorized operator; until then, eligible FFriZz V1 collection remains fail-closed. V2 diagnostic availability measurement does not require or bypass this persistence gate.

The feature-availability investigation found a timestamp-semantics risk in the FFriZz V1 OI feature. The runner requests Binance hourly open-interest history, while V1 `_oi_vote` matches each OI point to `candle["ts"]` by exact timestamp. Binance documents the open-interest-history `timestamp` as the END time of the requested period, whereas normalized OHLC candles are keyed by candle OPEN time. Therefore exact equality can systematically reject otherwise same-period hourly OI/price observations. This remains a V1 research-fingerprint limitation and was not silently patched.

PR #235 predeclared `FFRIZZ_SECONDARY_V2_OI_CLOSE_END` as a separate challenger whose only intended feature change is to align each completed 1H candle CLOSE endpoint exactly to the Binance OI period END endpoint. It rejects unsupported bars, ambiguous duplicate endpoints and insufficient exact overlap, and uses no interpolation/backfill. Post-merge inspection found #235 did not actually invoke that challenger from the live FFriZz runtime despite its orchestration descriptor. PR #236 corrected that integration defect and regression-tested the runtime invocation. V2 now runs only for 6h/12h/24h using the same cached 1H candles/OI already used by the V1 pass, and its result is reduced to bounded count-only feature-availability evidence.

During the #242 cycle, source inspection proved that the V2 result already reached `research_adaptive_accuracy_runner._ffrizz_forward_collection()` under `v2_oi_alignment_feature_availability`, but `continuous_coordinator.observability_log_payload().compact_ffrizz()` dropped it before private Render logging. This was a real evidence-observability defect: it prevented the exact post-#236 live V2 verification required by this state, but it did not affect scoring or trading. PR #242 fixed only that final transport boundary with a second strict allowlist. Its first exact-head run #1730 correctly failed because an existing strict observability dictionary test had not been updated for the new optional field; after the regression contract was updated, exact-head Security and Reliability #1732 passed. The coordinator deployment reached live on `f1d451cd02cb5a4a04ba80d313cb4539e1ec24d7`; startup observability showed the new V2 field as `None` before a fresh adaptive cycle completed. Therefore no V2 availability conclusion is yet justified from that startup sample. The next natural completed adaptive cycle must provide the first real post-#242 V2 horizon/family counts.

The runner requests V1 OI only for horizons whose feature bar is `1H`; its 48h/72h/7d 4H profiles deliberately pass no OI history. Thus three-family availability is expected for those 4H profiles under V1, while persistent three-family availability in 1H V1 profiles is consistent with the timestamp-alignment limitation. Do not infer feature usefulness from availability alone, and do not compare V1/V2 signal quality until genuine separately fingerprinted evidence is available.

Post-#242 deployment health remained operationally safe in the initial sample: worker failures=0, worker timeouts=0, supervisor healthy, no stale/crashed workers or task restarts, deployment canary not recommending rollback, and specialist factory normal-operation AI calls remained zero. ACC-002 remained fail-closed under pure `InsufficientHistory`; untouched OOS stayed closed. The latest inherited FFriZz evidence was still 72 WAIT / 0 BUY / 0 SELL with `unexpected_wait_state=0`; because it predated the fresh post-#242 adaptive run, it is not V2 verification and does not clear the known V1 eligible-write blocker.

PR #239 corrected a separate calibration-freshness defect in `.github/workflows/crypto_scan.yml`: due forecasts are now evaluated before the new production scan. Before #239, the new opportunity snapshot could be calculated from ledger state that was one scan cycle stale because `/evaluate` ran afterward. This was an evidence-timing defect, not a signal-threshold defect. The exact-head tests enforce evaluate-before-scan ordering while preserving all calibration sample-sufficiency and independence rules. Both Render services reached live on the later state-sync commit `8edba9ba0a5568dfad6f07a0e29052ddc9dae85b`, and scheduled run #552 on that commit showed `Evaluate previous signals` actively executing as step 4 while `Run production market scan` remained pending as step 5, confirming the intended runtime ordering.

History-network work remains a measurable throughput cost, not a confirmed defect. Cache hit rates in sampled windows have been modest while history failures remained zero and network calls often took seconds. #236 deliberately reuses the existing FFriZz candle and OI cache rather than adding duplicate external fetches. Any further cache/reuse improvement must preserve exact request identity, freshness, completed-candle semantics, chronology, provenance and authoritative-source fallback.

GitHub `main` branch protection remains disabled. Exact-head Security and Reliability, expected-head merge protection, isolated branches and current-main compatibility review are mandatory operational controls.

## COST / SPEED POLICY
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed. Prefer existing shared Render compute, deterministic Python, free/public defensible data, caching/reuse, early rejection and bounded concurrency. No paid feed/service/compute without explicit approval.

The token-free specialist factory uses zero normal-operation AI calls. Heavy experiment admission remains capped at one. Do not expand workers merely for appearance; require measured information-value benefit.

Blind RSI/MACD/EMA permutations, duplicate ensemble members, repeated falsified hypotheses without materially new evidence, repeated pure-InsufficientHistory ACC-002 investigation and worker-count expansion without demonstrated information value remain deprioritized.

## CURRENT OPEN DEVELOPMENT
#235/#236/#238/#239/#242 and older FFriZz PRs #214/#216/#217/#219/#221/#223/#225/#227/#229/#231 are integrated and must not be re-applied. #230/#232/#233/#234/#237/#240/#241 are state-only/reconciliation work. Stale PRs #34, #33 and #13 remain incompatible with current main and must not be merged as-is without fresh relevance/compatibility review.

Persistent specialist priorities live in `orchestration/specialist_coordination.json`. The accuracy/profitability roadmap lives in `orchestration/accuracy_profitability_roadmap.json`.

## EXACT NEXT STEP
1. Observe post-#238 production/paper cycles and use the structured rejection diagnostics to quantify whether WAIT/rejections are dominated by strategy evidence, market/liquidity, technical/data infrastructure, or portfolio risk. Treat the diagnostics as explanatory only; do not tune thresholds from unresolved outcomes.
2. Restore the coordinator's canonical prediction-ledger configuration before treating FFriZz V1 prospective evidence accumulation as operational. An eligible live cycle has proven `PredictionLedgerNotConfigured`; do not hide this behind later all-WAIT cycles and do not weaken database security to bypass it.
3. Preserve the current FFriZz V1 fingerprint and thresholds. Do not reinterpret abstention splits or the earlier three SELLs as evidence for threshold tuning.
4. Observe the first fresh completed post-#242 adaptive cycle and inspect the now-exposed V2-specific count-only diagnostics for 6h/12h/24h. Verify `price_oi_correlation_v2` availability by horizon, that only allowlisted aggregate counts are exposed, and that V2 uses no interpolation/backfill or authority. If OI remains unavailable, diagnose exact endpoint/cadence/data-source provenance rather than loosening matching.
5. Keep V2 separate from V1. Do not persist V2 forecasts or compare precision/expectancy until the V2 fingerprint's timestamp semantics and feature availability are prospectively verified and a separately reviewed forward-ledger design passes canonical safety requirements.
6. After V1 ledger configuration is restored, verify the first eligible persisted rows read-only: deterministic UUID scan identity, LONG/SHORT direction, canonical WAIT action, score 0..100, signed `calibration.raw_score`, preserved `shadow_action`, exact `due_at`, and full-horizon bucket identity.
7. Let valid prospective rows resolve naturally before any precision/expectancy comparison. Use exact fingerprint, non-overlapping full-horizon evidence and realistic costs. No unresolved-row tuning or production promotion.
8. Continue using resolved primary-system errors, calibration, regime behavior, cross-sectional information, microstructure, execution realism, paper rejection attribution and research-memory outcomes to prioritize falsifiable high-information experiments.
9. Treat cache/network optimization as throughput research only; never stretch freshness/TTL, merge distinct request identities or weaken provenance/completed-candle semantics.
10. Keep ACC-002 blocked while failures remain pure `InsufficientHistory`.
11. Keep `live_promotions.json` empty, broker disconnected, signing keys unused, authentic paper baseline/history immutable, heavy concurrency bounded and recurring infrastructure <= USD 30/month.
12. Every integration remains isolated branch -> regression tests -> exact-head Security and Reliability -> current-main compatibility -> expected-head merge -> AI_STATE.md synchronization -> post-deploy health verification.
