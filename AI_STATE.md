# AI DEVELOPMENT STATE
Last updated: 2026-09-10

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file from current `main` in full before development. Never infer project state only from ChatGPT memory. Update this file after each completed integration cycle.

## CURRENT MAIN / ARCHITECTURE
Current tested functional integration baseline after PR #231: `70c75e943febb89658a47e2bda9d9450229abd80`. State-only PRs #232 and #233 subsequently synchronized this file and recorded the first live FFriZz abstention evidence without runtime or authority changes.

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

The always-on research architecture includes bounded Python workers, autonomous research-director coordination, deterministic quant-science experiment factory, fail-closed heavy-experiment admission, adaptive-accuracy research, 256 token-free logical specialists per refresh, durable research memory, economic calibration/meta-WAIT, regime×strategy diagnostics, cross-sectional/residual diagnostics, prospective microstructure vetoes, ensemble-diversity/error-attribution diagnostics, selective-WAIT fusion and evidence-value scheduling. Logical specialist scale is not physical compute scale. Heavy experiment concurrency remains capped at one admitted heavy experiment at a time unless separately reviewed and cost-approved.

## SAFETY INVARIANTS
No AI opinion, ranking/evidence score, dashboard value, paper P&L, model count, ensemble weight, order-book snapshot, historical diagnostic, research-memory lesson, experiment priority, FFriZz signal/abstention count, prospective row, or single OOS/forward result may authorize live BUY/SELL by itself.

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
- `unexpected_wait_state` is a rule-drift/integrity alarm, never permission to reinterpret the scorer;
- bounded observability must not expose raw ledger rows, secrets, arbitrary error detail or unbounded payloads;
- paper technical/data failures remain retryable and may never become fabricated fills;
- no hourly self-improvement cycle may force paid model calls, bypass cooldown/budget controls, raise physical concurrency or create production authority.

## ACCURACY / RESEARCH PROGRAM
- ACC-001 market/execution realism: complete.
- ACC-002 cross-asset rank research: fail-closed before untouched OOS because historical coverage remains insufficient. Never lower `minimum_subset_coverage=0.80`, the two-supported-subset requirement, Top-N ordering, required history, or untouched-OOS rules merely to pass.
- ACC-003 through ACC-014 safety/validation layers: complete.
- Selective precision, economic meta-WAIT, regime×strategy, economic calibration, selective-WAIT fusion, A+ meta-signal trust, cross-sectional/residual, microstructure veto, ensemble diversity and error attribution remain governed research-only diagnostics.
- FFriZz secondary family remains research/shadow only. Prospective immutable forward evidence is the only route toward governed validation; no pooled history, unresolved row or abstention count is promotion evidence.
- New-horizon forward sample sufficiency remains restrictive-only: 6h/12h >=30 independent samples, 48h >=20, 72h >=16, with every later canonical gate still required.

## CURRENT LIVE EVIDENCE / OPERATIONS
Read-only Supabase audit during the #229 cycle found zero FFriZz rows in `prediction_ledger`. Repeated post-#227 live cycles were `collection_ok=true`, `error_type=None`, `eligible_shadow_forecasts=0`; therefore those sampled zeros were genuine abstention, not persistence failure.

The first complete live post-#231 abstention diagnostic at generated time `2026-09-10T12:55:55.364213+00:00` scored 72 FFriZz symbol/horizon observations. Action counts were exactly WAIT=72, SHADOW_BUY=0, SHADOW_SELL=0. Fixed-gate attribution reconciled exactly: 57 WAITs had insufficient directional agreement and 15 had enough agreement but score below the predeclared threshold. `unexpected_wait_state=0`. Available-family-count distribution was 0 families for 6 observations and 3 families for 66 observations. Diagnostics explicitly reported `thresholds_unchanged=true`, `backfill_used=false`, and no trade/promotion authority. This is evidence about why the current FFriZz family abstains; it is not evidence that thresholds should be lowered or that the family is profitable/unprofitable.

A later natural live cycle at approximately `2026-09-10T13:04Z` materially changed the persistence diagnosis: the FFriZz scorer produced three eligible SHADOW_SELL forecasts while `ffrizz_forward.collection_ok=false` with `error_type=PredictionLedgerNotConfigured`. The same cycle scored 72 observations with WAIT=69, SHADOW_SELL=3, SHADOW_BUY=0 and `unexpected_wait_state=0`. This proves the coordinator cannot currently persist an otherwise eligible prospective FFriZz forecast. The failure is correctly fail-closed and does not create production or paper authority, but prospective FFriZz evidence accumulation is blocked until the coordinator has a complete canonical Supabase ledger configuration. Later zero-eligible cycles returned `collection_ok=true`, which is expected because no write was required; those later successes do not clear the eligible-write blocker.

Configuration code requires both `SUPABASE_URL` and `SUPABASE_SECRET_KEY` for canonical ledger persistence. Do not commit either credential, substitute a publishable/anonymous key for privileged research persistence, weaken RLS, or create an unauthenticated persistence bypass. The missing secret/configuration must be supplied through the existing Render service environment by an authorized operator; until then, eligible FFriZz collection remains fail-closed.

The feature-availability investigation also found a timestamp-semantics risk in the current FFriZz V1 OI feature. The runner requests Binance hourly open-interest history, while `_oi_vote` currently matches each OI point to `candle["ts"]` by exact timestamp. Binance documents the open-interest-history `timestamp` as the END time of the requested period, whereas normalized OHLC candles are keyed by candle OPEN time. Therefore exact equality can systematically reject otherwise same-period hourly OI/price observations. This is consistent with the live 3-family pattern and must be treated as a V1 research-fingerprint limitation, not silently patched in place. No historical interpolation/backfill is authorized. Any correction must be predeclared as a new challenger/fingerprint and align completed candle close time to OI period end without using future data.

The runner currently requests OI only for horizons whose feature bar is `1H`; its 48h/72h/7d 4H profiles deliberately pass no OI history. Thus three-family availability is expected for those 4H profiles under V1, while persistent three-family availability in the 1H profiles requires the timestamp-alignment issue above to be resolved or otherwise diagnosed prospectively. Do not infer feature usefulness from availability alone.

The same live coordinator otherwise remained healthy: worker failures=0, worker timeouts=0, supervisor healthy, no stale/crashed workers and no task restarts in the sampled window. ACC-002 remained naturally blocked: a recent 24h sample resolved 26/30 with four pure `InsufficientHistory` failures and only the Top-15 subset supported; a recent 7d sample resolved 11/30 with nineteen pure `InsufficientHistory` failures. Untouched OOS stayed closed.

History-network work remains a measurable throughput cost, not a confirmed defect. Cache hit rates in sampled windows have been modest while history failures remained zero and network calls often took seconds. Any cache/reuse improvement must preserve exact request identity, freshness, completed-candle semantics, chronology, provenance and authoritative-source fallback.

GitHub `main` branch protection remains disabled. Exact-head Security and Reliability, expected-head merge protection, isolated branches and current-main compatibility review are mandatory operational controls.

## COST / SPEED POLICY
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed. Prefer existing shared Render compute, deterministic Python, free/public defensible data, caching/reuse, early rejection and bounded concurrency. No paid feed/service/compute without explicit approval.

The token-free specialist factory uses zero normal-operation AI calls. Heavy experiment admission remains capped at one. Do not expand workers merely for appearance; require measured information-value benefit.

Blind RSI/MACD/EMA permutations, duplicate ensemble members, repeated falsified hypotheses without materially new evidence, repeated pure-InsufficientHistory ACC-002 investigation and worker-count expansion without demonstrated information value remain deprioritized.

## CURRENT OPEN DEVELOPMENT
#229/#231 and older FFriZz PRs #214/#216/#217/#219/#221/#223/#225/#227 are integrated and must not be re-applied. #230/#232/#233 are state-only synchronizations. Stale PRs #34, #33 and #13 remain incompatible with current main and must not be merged as-is without fresh relevance/compatibility review.

Persistent specialist priorities live in `orchestration/specialist_coordination.json`. The accuracy/profitability roadmap lives in `orchestration/accuracy_profitability_roadmap.json`.

## EXACT NEXT STEP
1. Restore the coordinator's canonical prediction-ledger configuration before treating FFriZz prospective evidence accumulation as operational. An eligible live cycle has now proven `PredictionLedgerNotConfigured`; do not hide this behind later all-WAIT cycles and do not weaken database security to bypass it.
2. Preserve the current FFriZz V1 fingerprint and thresholds. Do not reinterpret the 57/15 abstention split or the later three SELLs as evidence for threshold tuning.
3. Predeclare a separate FFriZz OI-alignment challenger/fingerprint before changing timestamp handling. The candidate method should match each completed candle CLOSE endpoint to the Binance OI period END endpoint for the same interval, reject ambiguous/missing cadence, use no interpolation or future data, and begin with research/shadow-only prospective evidence. V1 evidence must remain identifiable and must not be pooled with the challenger.
4. Add bounded horizon-specific feature-availability diagnostics so 1H versus 4H OI availability can be measured directly without exposing raw symbols/rows or arbitrary error details.
5. After ledger configuration is restored, verify the first eligible persisted rows read-only: deterministic UUID scan identity, LONG/SHORT direction, canonical WAIT action, score 0..100, signed `calibration.raw_score`, preserved `shadow_action`, exact `due_at`, and full-horizon bucket identity.
6. Let valid prospective rows resolve naturally before any precision/expectancy comparison. Use exact fingerprint, non-overlapping full-horizon evidence and realistic costs. No unresolved-row tuning or production promotion.
7. Continue using resolved primary-system errors, calibration, regime behavior, cross-sectional information, microstructure, execution realism and research-memory outcomes to prioritize falsifiable high-information experiments.
8. Treat cache/network optimization as throughput research only; never stretch freshness/TTL, merge distinct request identities or weaken provenance/completed-candle semantics.
9. Keep ACC-002 blocked while failures remain pure `InsufficientHistory`.
10. Keep `live_promotions.json` empty, broker disconnected, signing keys unused, authentic paper baseline/history immutable, heavy concurrency bounded and recurring infrastructure <= USD 30/month.
11. Every integration remains isolated branch -> regression tests -> exact-head Security and Reliability -> current-main compatibility -> expected-head merge -> AI_STATE.md synchronization -> post-deploy health verification.
