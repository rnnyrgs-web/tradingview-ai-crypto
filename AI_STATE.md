# AI DEVELOPMENT STATE
Last updated: 2026-09-11

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file from current `main` in full before development. Never infer project state only from ChatGPT memory. Update this file after each completed integration cycle.

## CURRENT MAIN / ARCHITECTURE
Current tested functional baseline after PR #260: `e7c5a063f33afbc98aabaa72efee270eac3508df`. PR #260 exact head `9fdb05c94d223063e297d9b47b90196da9a2893c` passed Security and Reliability #1830 before expected-head merge. It responds to repeated natural post-#257 evidence that every sampled Binance historical-OI request from the current deployment returns the allowlisted `http_451` bucket. After the first confirmed `http_451` in a FFriZz run, the runner now stops repeating the same blocked Binance OI source request for remaining bases in that run and supplies empty OI fail-closed. A new natural run probes the source again once, so recovery remains detectable. Other failures such as timeout/network/429 do not trip this circuit. No alternate venue is substituted and no signal, threshold, chronology, V1/V2/V3 fingerprint, persistence, paper, promotion, broker, concurrency, paid-service, or recurring-cost semantics changed.

Production is GitHub -> Render -> Python/FastAPI V3 -> Supabase. Governed horizons are 6h, 12h, 24h, 48h, 72h and 7d. New horizons remain WAIT/LEARNING unless every canonical gate is independently satisfied. Production scans run about every 15 minutes. Continuous research/backtesting uses the existing Render coordinator with bounded concurrency.

Primary production service: `srv-dadliegu01pc73bc7t50` (`tradingview-ai-crypto`).
Continuous research coordinator: `srv-dafgtead0e5s73cc7ekg`.
Supabase project: `dxgksvzibucwuzmppoqy`.
Recurring infrastructure ceiling: USD 30/month unless explicitly approved otherwise.

Important integrated sequence:
- #210/#211/#213: governed persisted multi-horizon opportunity generation, exact-horizon deadlines, horizon-specific calibration/genuine-forward chronology, all-horizon dashboard reads.
- #214/#216: FFriZz-inspired six-horizon secondary family and prospective collection, strictly research/shadow only.
- #217: FFriZz pooled cross-symbol diagnostics are descriptive/non-independent; OHLC-only historical diagnostics do not match the prospective OI-capable fingerprint; feature-family agreement is not assumed independent.
- #219: deterministic UUIDv5 scan identity by system+horizon+full-horizon bucket.
- #221: canonical FFriZz action remains WAIT; source SHADOW_BUY/SHADOW_SELL stays research metadata; immutable direction remains LONG/SHORT.
- #223: persisted ledger score uses nonnegative absolute shadow strength while signed raw score remains research metadata.
- #225: bounded read-only `ffrizz_forward` coordinator observability.
- #227: eligible FFriZz collection fails closed as `PredictionLedgerNotConfigured` if canonical ledger persistence is unavailable; zero-eligible/all-WAIT cycles remain legitimate because no write is required.
- #229/#231: fixed-gate FFriZz abstention diagnostics and bounded sanitized coordinator observability; no thresholds or authority changed.
- #234: authoritative state recorded the canonical FFriZz ledger-configuration blocker and V1 OI timestamp-semantics risk.
- #235: separately fingerprinted research-only `FFRIZZ_SECONDARY_V2_OI_CLOSE_END` challenger added with exact completed-candle-close endpoint = Binance OI period-end matching, no interpolation/backfill; registration review found runtime invocation was initially missing.
- #236: V2 runtime invocation added only for 6h/12h/24h 1H research horizons, reusing existing candles/OI cache; no V2 persistence or authority.
- #238: bounded paper WAIT/rejection actionability diagnostics; no decision, risk, fill, sizing, broker, schema, or cost change.
- #239: production workflow reordered to evaluate due predictions before the next scan, eliminating a one-scan calibration lag without changing evaluation/threshold rules.
- #242: final V2 count-only observability gap fixed; exact head `1abd76a6319ed7b495c9785e5006773cf6409a31` passed Security and Reliability #1732 and merged as `f1d451cd02cb5a4a04ba80d313cb4539e1ec24d7`; both Render services reached live.
- #243: state synchronization through #242 merged as `2796586937dce6a761f054dd69d65e6ef84b4dfe`.
- #244: live post-#242 V2 evidence was reconciled with Binance timestamp semantics. The exact-match hypothesis is now treated as disproven rather than loosened. A separately fingerprinted V3 causal-as-of challenger plus chronology regression tests and a durable research memo were added. Exact head `67646605e20af3c363ea69a39bc7e958b5f5b62c` passed Security and Reliability #1743 before expected-head squash merge as `99b5e1eb0639022a8d14ef728341517ba8d9cde4`.
- #246: paper loss-streak risk gate no longer forms a permanent latch. Four consecutive authentic paper losses still trigger the gate, but eligibility can recover only after a 24-hour cooldown from the last closed paper trade; absent/malformed chronology remains blocked. Exact head `b132193fa62f4beb4d96aba14672430deb4588eb` passed Security and Reliability #1753 before merge as `a38d09429a711c20234b235a2bc38b58217c44e3`.
- #248: V3 is now invoked only inside the existing bounded FFriZz 6h/12h/24h 1H research pass and reuses the exact already-fetched candle/OI objects. Only count-level family availability and allowlisted V3 OI-unavailability reasons cross adaptive/coordinator observability boundaries; symbols/raw rows/arbitrary keys remain excluded. The first exact-head CI exposed one strict observability-shape regression and failed closed; the contract was updated, and replacement exact head `080de5685b9388d54bd99fd73dad895799ec0bf7` passed all Security and Reliability #1766 checks before merge as `2b520237c410edb1d9d7907b2eb5f01c653dbec7`.
- #250: the existing FFriZz OI fetch no longer collapses every upstream acquisition outcome into an indistinguishable empty list. It carries one internal list-compatible bounded source status, aggregates only fixed counts (`available`, `valid_empty`, `http_error`, `timeout`, `network_error`, `invalid_payload`, `source_error`, `unclassified`), makes no additional requests, and exposes no symbol/raw error/URL/payload data. Exact head `2c924b2f41ac52e02b04225abe14ef45e9dc4c7f` passed Security and Reliability #1777 before merge as `218a0aeda581504160eed720191d7841ae212745`.
- #251: those already-bounded OI source counts are re-allowlisted at the final coordinator log boundary. Initial exact head failed closed on the strict complete-shape observability test; after updating that contract, exact head `0e1ac116b3670559b0c9f8992a47f849165a64b5` passed Security and Reliability #1784 and merged as `aafb06c0f78cc1d2c5ef5100988f3881f3720162`.
- #253: repeated natural post-#251 cycles showed all 12 Binance OI-history acquisitions in `http_error` while coordinator health remained normal. Exact response status had been discarded upstream, so a bounded status classifier was added only on that existing exception path. Exact head `41c497a2f5f9d98073212ab65196d09ee7194089` passed Security and Reliability #1794 and merged as `ac6d1cbcc6c4ab3ac1879dfd0a86c9b8d9e58c40`; both Render services reached live.
- #255: autonomous cloud failure accounting is robust to the `openai-agents` top-level `agents` package shadow. Exact head `a15eb231c3baf2ccc347d37bc655201b0d2f1e59` passed Security and Reliability #1803 before expected-head squash merge as `64c9a03856d8f0d9a585de24aed3beceb4481784`. The spend ceiling remains unchanged and model-budget exhaustion remains fail-closed.
- #257: confirmed the remaining post-#253 generic-HTTP behavior was a two-boundary propagation defect rather than evidence about Binance itself. Exact head `3565444f8ae07774b076b17f31110c5a72c50dc1` passed Security and Reliability #1813 before expected-head squash merge as `5e154a6b0fb7b736528a78329691ecadcb1566d0`. Only the five predeclared HTTP buckets can propagate through FFriZz and the adaptive coordinator boundary; absent/unrecognized values remain generic and arbitrary symbol/URL/status detail is not exposed.
- #259: fixed the final coordinator projection so the already-allowlisted HTTP status buckets survive end-to-end observability rather than collapsing back to generic HTTP. Subsequent natural cycles consistently identified Binance historical-OI acquisition as `http_451` across the sampled universe.
- #260: repeated 451 requests are now circuit-broken within one FFriZz run after the first confirmed 451. Remaining bases fail closed with empty OI; the next natural run probes once again. The first exact-head CI #1828 correctly failed on an overreaching V3 test fixture; the fixture was corrected without weakening the assertion. Replacement exact head `9fdb05c94d223063e297d9b47b90196da9a2893c` passed all Security and Reliability #1830 checks before expected-head merge as `e7c5a063f33afbc98aabaa72efee270eac3508df`.

The always-on research architecture includes bounded Python workers, autonomous research-director coordination, deterministic quant-science experiment factory, fail-closed heavy-experiment admission, adaptive-accuracy research, 256 token-free logical specialists per refresh, durable research memory, economic calibration/meta-WAIT, regime×strategy diagnostics, cross-sectional/residual diagnostics, prospective microstructure vetoes, ensemble-diversity/error-attribution diagnostics, selective-WAIT fusion, and evidence-value scheduling. Logical specialist scale is not physical compute scale. Heavy experiment concurrency remains capped at one admitted heavy experiment at a time unless separately reviewed and cost-approved.

## SAFETY INVARIANTS
No AI opinion, ranking/evidence score, dashboard value, paper P&L, model count, ensemble weight, order-book snapshot, historical diagnostic, research-memory lesson, experiment priority, FFriZz signal/abstention count, prospective row, V2/V3 feature-availability result, OI acquisition-status count, paper rejection diagnostic, or single OOS/forward result may authorize live BUY/SELL by itself.

Mandatory chain:
RESEARCH -> BACKTEST -> VALIDATION -> UNTOUCHED OOS -> ROBUSTNESS/STABILITY -> MULTIPLE-TESTING FIREWALL -> POINT-IN-TIME UNIVERSE SAFETY -> STRATEGY-REGISTRY APPROVAL -> PRODUCTION-RISK APPROVAL -> GENUINE FORWARD PROOF -> GLOBAL/EXECUTION RISK CLEAR -> LIVE BUY/SELL.

Every later stage is restrictive-only. Missing, stale, contradictory, malformed, overlapping-only, insufficient, illiquid, execution-unsafe, portfolio-unsafe, statistically weak, survivorship-unsafe, persistence-unsafe, label-unsafe, chronology-unsafe, or system-unsafe evidence means `WAIT / NO TRADE / RESEARCH_ONLY`.

`live_promotions.json` remains empty. Signing keys remain unused. Broker remains disconnected. Do not add credentials or real-order capability without explicit user approval plus all canonical gates.

Authentic paper account baseline remains exactly `$100,000` from `2026-09-08T01:17:49Z`. Never reset, rewrite, replace, or manufacture its history. Paper performance is evidence only.

## SCIENTIFIC RESEARCH DISCIPLINE
Chronological validation remains development -> validation -> untouched holdout/OOS. Genuine forward proof counts only non-overlapping full-horizon resolved forecasts for the exact immutable strategy fingerprint. Robustness requires deterministic resampling, parameter perturbation, regime stability, conservative execution-cost stress, search-breadth protection, and genuine forward confirmation.

Core invariants:
- no lookahead/leakage, threshold mining, OOS reuse, survivorship substitution, or fabricated evidence;
- never pool historical/OOS with genuine forward evidence to inflate confidence;
- never backfill unavailable timestamp-sensitive order-book, consensus, cross-sectional, leadership, funding, OI, or other prospective fields merely to improve coverage;
- overlapping forecasts are not independent; simultaneous cross-symbol crypto outcomes are not automatically independent; model/family count is not independence;
- realistic fees, spread, slippage, funding/carry, and execution assumptions remain mandatory;
- untouched OOS remains sealed until predeclared validation admission passes;
- repeated/disproven hypotheses receive research-memory penalties instead of blind recycling;
- malformed/missing/delayed outcome chronology fails closed;
- research scheduling prioritizes falsifiable, actionable, high-information experiments by expected after-cost impact, sample readiness, compute cost, and redundancy/overfit risk;
- production WAIT may be studied through immutable research direction but research never mutates production action;
- FFriZz historical OHLC-only diagnostics are descriptive and do not validate a prospective OI-capable fingerprint;
- FFriZz abstention diagnostics explain fixed existing gates only; they may not tune thresholds from unresolved observations or turn WAIT into a forecast;
- FFriZz V1, V2, and V3 are separate research fingerprints and their evidence may not be pooled;
- V2's exact endpoint equality hypothesis is now a recorded negative result. Do not retry it unless source timestamp semantics materially change;
- V3 causal as-of alignment is a new data-semantics hypothesis, not an alpha claim. Its `<1H` staleness rule is predeclared, future price is forbidden, duplicate price-endpoint reuse is rejected, and no production/persistence authority exists;
- OI source diagnostics are acquisition observability only. They may identify why OI is unavailable but may not be used to weaken timestamp alignment, backfill missing OI, tune thresholds, or infer predictive edge;
- bounded OI HTTP diagnostics may expose only fixed status buckets from the existing request. Never log raw response bodies, request URLs, symbols, arbitrary status text, or use status information to bypass exchange restrictions;
- a confirmed source-level 451 may suppress redundant requests only within the current run; the next run must probe again so recovery can be detected without creating a permanent availability assumption;
- `unexpected_wait_state` is a rule-drift/integrity alarm, never permission to reinterpret the scorer;
- bounded observability must not expose raw ledger rows, secrets, arbitrary error detail, or unbounded payloads;
- paper technical/data failures remain retryable and may never become fabricated fills;
- paper rejection/actionability diagnostics are explanatory only and may not mutate TRADE/WAIT decisions, thresholds, risk gates, execution semantics, fills, sizing, or authority;
- a paper loss-streak cooldown may recover only from authentic closed-trade chronology. Missing or malformed chronology must fail closed, and cooldown completion does not bypass any independent strategy, drawdown, concentration, liquidity, execution, or validation gate;
- no hourly self-improvement cycle may force paid model calls, bypass cooldown/budget controls, raise physical concurrency, or create production authority.

## ACCURACY / RESEARCH PROGRAM
- ACC-001 market/execution realism: complete.
- ACC-002 cross-asset rank research: fail-closed before untouched OOS because historical coverage remains insufficient. Never lower `minimum_subset_coverage=0.80`, the two-supported-subset requirement, Top-N ordering, required history, or untouched-OOS rules merely to pass.
- ACC-003 through ACC-014 safety/validation layers: complete.
- Selective precision, economic meta-WAIT, regime×strategy, economic calibration, selective-WAIT fusion, A+ meta-signal trust, cross-sectional/residual, microstructure veto, ensemble diversity, and error attribution remain governed research-only diagnostics.
- FFriZz V1 remains research/shadow only. Prospective immutable forward evidence is the only route toward governed validation; no pooled history, unresolved row, or abstention count is promotion evidence.
- FFriZz V2 exact-close-end challenger is a negative timestamp-coverage result: first live post-#242 observation had zero `price_oi_correlation_v2` availability across all 12 sampled symbols at 6h/12h/24h. Do not loosen exact matching and do not use this as profitability evidence.
- FFriZz V3 causal-as-of challenger is runtime-wired only as bounded 6h/12h/24h diagnostics. It remains unavailable while the current Binance OI route is geographically blocked by confirmed HTTP 451. That source restriction does not falsify V3 alignment and must not be worked around by silently changing venue or timestamp semantics. V3 has no forward-ledger persistence or trading authority.
- New-horizon forward sample sufficiency remains restrictive-only: 6h/12h >=30 independent samples, 48h >=20, 72h >=16, with every later canonical gate still required.

## CURRENT LIVE EVIDENCE / OPERATIONS
A read-only Supabase audit during the #229 cycle found zero FFriZz rows in `prediction_ledger`. Repeated post-#227 live cycles with zero eligible shadow forecasts were genuine abstention, not persistence failure.

The first complete post-#231 abstention diagnostic scored 72 FFriZz symbol/horizon observations: WAIT=72, SHADOW_BUY=0, SHADOW_SELL=0. Attribution reconciled exactly: 57 insufficient directional agreement, 15 enough agreement but score below the predeclared threshold, `unexpected_wait_state=0`. This explains abstention only; it does not support threshold reduction.

A later natural live cycle produced three eligible SHADOW_SELL forecasts while `ffrizz_forward.collection_ok=false` with `error_type=PredictionLedgerNotConfigured`; the same cycle scored WAIT=69, SHADOW_SELL=3, SHADOW_BUY=0 with `unexpected_wait_state=0`. This proves eligible FFriZz V1 prospective persistence is blocked until the coordinator has the complete canonical Supabase ledger configuration. Later all-WAIT cycles do not clear that blocker because no write is attempted.

Canonical persistence requires both `SUPABASE_URL` and `SUPABASE_SECRET_KEY`. Do not commit credentials, substitute a publishable/anonymous key for privileged research persistence, weaken RLS, or create an unauthenticated persistence bypass. The missing configuration must be supplied through the existing Render environment by an authorized operator.

V1 OI timestamp semantics remain limited: V1 exact-matches Binance hourly OI `timestamp` to normalized OHLC candle OPEN timestamp. Binance defines OI `timestamp` as the period end, so V1 can systematically lose OI availability.

V2 tested a cleaner exact hypothesis: completed 1H candle endpoint exactly equals Binance OI period-end timestamp. After #242 made V2-specific observability visible, multiple live coordinator samples showed `price_oi_correlation_v2` unavailable for all 12 symbols at 6h, 12h, and 24h. The V2 scorer was running and other health indicators were normal, so this is not evidence of a missing runtime invocation. Binance's current public Open Interest Statistics documentation calls the field the period end but shows an example timestamp that is not constrained to a canonical hourly wall-clock boundary. Therefore exact endpoint equality is not a valid general source assumption. This is now a durable negative research result.

PR #244 responds without loosening V2. `FFRIZZ_SECONDARY_V3_OI_CAUSAL_ASOF` is separately fingerprinted. For each OI observation it selects only the latest already-completed 1H price endpoint at or before that OI timestamp, with staleness strictly below one hour. It rejects duplicate OI timestamps and ambiguous reuse of a price endpoint, forbids future price, nearest-neighbour, and interpolation semantics, retains fixed signal thresholds, and has no persistence/trading authority. Regression tests explicitly exercise non-boundary OI timestamps, no-future chronology, ambiguous reused endpoints, and no-authority metadata.

Multiple natural post-#248 coordinator cycles remained healthy with zero worker failures/timeouts and showed V3 `price_oi_correlation_v3:unavailable` for all 12 sampled symbols at 6h/12h/24h with `oi_unavailable_reason_counts={'oi_unavailable': 12}` at each horizon. V2 remained unavailable across the same horizons. FFriZz remained all-WAIT in the sampled cycles with `unexpected_wait_state=0`. Because the V3 scorer was receiving no OI points, this is an upstream-data availability question rather than evidence against V3's causal-as-of timestamp rule.

PR #250 added bounded acquisition provenance using the already-returned `get_derivatives_history()` error metadata and the exact existing fetch. PR #251 made those counts visible at the final coordinator log boundary. Repeated natural post-#251 cycles then established a stable operational fact: all 12 Binance OI-history acquisition attempts were `http_error` while the coordinator itself remained healthy with zero worker failures/timeouts.

PR #253 safely narrowed that uncertainty at the acquisition layer. PR #257 and #259 then fixed the two downstream propagation boundaries. Multiple clean natural post-#259 live cycles consistently showed `http_451` for all 12 Binance OI-history acquisitions while the coordinator remained healthy. This is genuine operational evidence that the current Binance historical-OI route is unavailable from the present deployment; do not reinterpret it as alpha evidence or bypass the restriction.

PR #260 reduces that known-useless repeated work without changing data semantics: after one actual `http_451` acquisition in a run, remaining bases receive missing OI fail-closed and no further Binance historical-OI request is issued in that run. The next natural run probes again. At state-sync time, post-deployment runtime confirmation of `acquisition_attempts=1` is still pending; do not claim it until observed live.

The Cost-Bounded Autonomous Cloud Specialist run on current main failed at the provider spend/usage ceiling and then exposed a deterministic local reliability bug: after installing `openai-agents`, `python agents/autonomous_cloud_state.py mark-failure` could not import `agents.autonomous_cloud_runner` because the installed regular `agents` package shadowed the repository namespace directory. PR #255 fixes only that failure-accounting import path. It does not raise or bypass the USD 30/month ceiling, and paid model execution remains fail-closed when provider budget is unavailable.

PR #239's calibration-freshness ordering has been observed in an actual scheduled workflow: `Evaluate previous signals` executes before `Run production market scan`.

PR #246 repairs a confirmed paper-risk liveness defect without weakening the loss-streak trigger: after four consecutive authentic losses, the paper portfolio remains blocked for 24 hours from the latest authentic `closed_at`; absent/malformed chronology remains fail-closed. Cooldown completion only removes the permanent-latch condition and does not override any other risk or signal gate.

History-network cost remains a throughput research topic rather than a confirmed correctness defect. Any cache/reuse change must preserve exact request identity, freshness, completed-candle semantics, chronology, provenance, and authoritative-source fallback.

GitHub `main` branch protection remains disabled. Exact-head Security and Reliability, expected-head merge protection, isolated branches, and current-main compatibility review are mandatory operational controls.

## COST / SPEED POLICY
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed. Prefer existing shared Render compute, deterministic Python, free/public defensible data, caching/reuse, early rejection, and bounded concurrency. No paid feed/service/compute without explicit approval.

The token-free specialist factory uses zero normal-operation AI calls. Heavy experiment admission remains capped at one. Do not expand workers merely for appearance; require measured information-value benefit.

Blind RSI/MACD/EMA permutations, duplicate ensemble members, repeated falsified hypotheses without materially new evidence, repeated pure-InsufficientHistory ACC-002 investigation, and worker-count expansion without demonstrated information value remain deprioritized.

## CURRENT OPEN DEVELOPMENT
PR #260 is integrated and must not be re-applied. PR #259/#257/#255/#253 are integrated and must not be re-applied. PR #251 and PR #250 are integrated and must not be re-applied. PR #248 is integrated and must not be re-applied. PR #246 is integrated and must not be re-applied. PR #244 is integrated and must not be re-applied. #235/#236/#238/#239/#242 and older FFriZz PRs #214/#216/#217/#219/#221/#223/#225/#227/#229/#231 are integrated. #230/#232/#233/#234/#237/#240/#241/#243/#245/#247/#249/#252/#254/#256/#258 are state-only/reconciliation work. Stale PRs #34, #33, and #13 remain incompatible with current main and must not be merged as-is without fresh relevance/compatibility review.

Persistent specialist priorities live in `orchestration/specialist_coordination.json`. The accuracy/profitability roadmap lives in `orchestration/accuracy_profitability_roadmap.json`. The V2 negative result and V3 experiment contract are preserved in `docs/FFRIZZ_V3_OI_CAUSAL_ASOF.md` and `orchestration/ffrizz_v3_oi_causal_asof.json`.

## EXACT NEXT STEP
1. Verify the first natural post-#260 coordinator cycle. Under persistent Binance 451, `oi_source_diagnostics.acquisition_attempts` should be 1 with `status_counts={'http_451': 1}` while V1/V2/V3 OI remains unavailable and the coordinator stays healthy. If that shape is not observed, diagnose before further data-source work.
2. Keep Binance historical OI fail-closed from the current deployment. Do not proxy around, spoof location, or otherwise bypass the confirmed source restriction.
3. Evaluate a compliant free/public alternative only as a separately fingerprinted challenger. Bybit historical open-interest is a candidate for a research-only V4 source-availability experiment; first test accessibility and timestamp/provenance semantics from the existing environment, then predeclare the V4 fingerprint before any predictive comparison. Never silently substitute it into V1/V2/V3 or pool venue evidence.
4. Do not change V3 timestamp alignment until genuine OI becomes available. Preserve `<1H` staleness, no-future selection, no nearest-neighbour/interpolation, duplicate OI rejection, and ambiguous price-endpoint reuse rejection. Availability alone is not predictive usefulness and must not trigger threshold tuning.
5. Restore the coordinator's canonical prediction-ledger configuration before treating FFriZz V1 prospective evidence accumulation as operational. The proven `PredictionLedgerNotConfigured` eligible-write failure remains open.
6. After V1 ledger configuration is restored, verify the first eligible persisted rows read-only: deterministic UUID scan identity, LONG/SHORT direction, canonical WAIT action, score 0..100, signed `calibration.raw_score`, preserved `shadow_action`, exact `due_at`, and full-horizon bucket identity.
7. Let valid prospective rows resolve naturally before any precision/expectancy comparison. Use exact fingerprint, non-overlapping full-horizon evidence, realistic costs, multiple-testing controls, and untouched OOS. No unresolved-row tuning or production promotion.
8. Continue using resolved primary-system errors, calibration, regime behavior, cross-sectional information, market microstructure, execution realism, paper rejection attribution, and research-memory outcomes to rank falsifiable experiments by expected information gain and after-cost impact. Any clock-phase/order-flow hypothesis remains hypothesis-generating until tested with defensible timestamped data, purged chronological validation, realistic costs, and multiple-testing protection.
9. Observe paper/production rejection diagnostics and quantify whether WAIT/rejections are dominated by strategy evidence, market/liquidity, technical/data infrastructure, or portfolio risk. Treat the result as explanatory only.
10. Treat cache/network optimization as throughput research only; never stretch freshness/TTL, merge distinct request identities, or weaken provenance/completed-candle semantics.
11. Keep ACC-002 blocked while failures remain pure `InsufficientHistory`.
12. Keep provider-budget failures fail-closed. No self-improvement cycle may increase the user-approved recurring ceiling or force paid calls.
13. Keep `live_promotions.json` empty, broker disconnected, signing keys unused, authentic paper baseline/history immutable, heavy concurrency bounded, and recurring infrastructure <= USD 30/month.
14. Every integration remains isolated branch -> regression tests -> exact-head Security and Reliability -> current-main compatibility -> expected-head merge -> AI_STATE.md synchronization -> post-deploy health verification when runtime code changes.
