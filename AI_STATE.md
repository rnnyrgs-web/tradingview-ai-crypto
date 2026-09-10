# AI DEVELOPMENT STATE
Last updated: 2026-09-10

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file from current `main` in full before development. Never infer project state only from ChatGPT memory. Update this file after each completed integration cycle.

## CURRENT MAIN / ARCHITECTURE
Current tested functional baseline after PR #248: `2b520237c410edb1d9d7907b2eb5f01c653dbec7`. PR #248 exact head `080de5685b9388d54bd99fd73dad895799ec0bf7` passed Security and Reliability #1766 before expected-head squash merge from the then-current main. It runtime-wires the separately fingerprinted FFriZz V3 causal-as-of OI challenger only as bounded 6h/12h/24h research diagnostics, reusing the existing 1H candle/OI cache and exposing only allowlisted aggregate availability/integrity counts through adaptive research and coordinator observability. It adds no persistence, production/paper/promotion/broker authority, signal threshold change, extra worker, extra market-data fetch, paid service, or recurring cost.

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
- #246: paper loss-streak risk gate no longer forms a permanent latch. Four consecutive authentic paper losses still trigger the gate, but eligibility can recover only after a 24-hour cooldown from the last closed paper trade; absent/malformed close chronology remains blocked. Exact head `b132193fa62f4beb4d96aba14672430deb4588eb` passed Security and Reliability #1753 before merge as `a38d09429a711c20234b235a2bc38b58217c44e3`.
- #248: V3 is now invoked only inside the existing bounded FFriZz 6h/12h/24h 1H research pass and reuses the exact already-fetched candle/OI objects. Only count-level family availability and allowlisted V3 OI-unavailability reasons cross adaptive/coordinator observability boundaries; symbols/raw rows/arbitrary keys remain excluded. The first exact-head CI exposed one strict observability-shape regression and failed closed; the contract was updated, and replacement exact head `080de5685b9388d54bd99fd73dad895799ec0bf7` passed all Security and Reliability #1766 checks before merge as `2b520237c410edb1d9d7907b2eb5f01c653dbec7`.

The always-on research architecture includes bounded Python workers, autonomous research-director coordination, deterministic quant-science experiment factory, fail-closed heavy-experiment admission, adaptive-accuracy research, 256 token-free logical specialists per refresh, durable research memory, economic calibration/meta-WAIT, regime×strategy diagnostics, cross-sectional/residual diagnostics, prospective microstructure vetoes, ensemble-diversity/error-attribution diagnostics, selective-WAIT fusion, and evidence-value scheduling. Logical specialist scale is not physical compute scale. Heavy experiment concurrency remains capped at one admitted heavy experiment at a time unless separately reviewed and cost-approved.

## SAFETY INVARIANTS
No AI opinion, ranking/evidence score, dashboard value, paper P&L, model count, ensemble weight, order-book snapshot, historical diagnostic, research-memory lesson, experiment priority, FFriZz signal/abstention count, prospective row, V2/V3 feature-availability result, paper rejection diagnostic, or single OOS/forward result may authorize live BUY/SELL by itself.

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
- FFriZz V3 causal-as-of challenger is now runtime-wired only as bounded 6h/12h/24h diagnostics as of #248. It has no forward-ledger persistence or trading authority. Its first post-deploy prospective availability/integrity result must be observed before any signal-quality comparison or further design.
- New-horizon forward sample sufficiency remains restrictive-only: 6h/12h >=30 independent samples, 48h >=20, 72h >=16, with every later canonical gate still required.

## CURRENT LIVE EVIDENCE / OPERATIONS
A read-only Supabase audit during the #229 cycle found zero FFriZz rows in `prediction_ledger`. Repeated post-#227 live cycles with zero eligible shadow forecasts were genuine abstention, not persistence failure.

The first complete post-#231 abstention diagnostic scored 72 FFriZz symbol/horizon observations: WAIT=72, SHADOW_BUY=0, SHADOW_SELL=0. Attribution reconciled exactly: 57 insufficient directional agreement, 15 enough agreement but score below the predeclared threshold, `unexpected_wait_state=0`. This explains abstention only; it does not support threshold reduction.

A later natural live cycle produced three eligible SHADOW_SELL forecasts while `ffrizz_forward.collection_ok=false` with `error_type=PredictionLedgerNotConfigured`; the same cycle scored WAIT=69, SHADOW_SELL=3, SHADOW_BUY=0 with `unexpected_wait_state=0`. This proves eligible FFriZz V1 prospective persistence is blocked until the coordinator has the complete canonical Supabase ledger configuration. Later all-WAIT cycles do not clear that blocker because no write is attempted.

Canonical persistence requires both `SUPABASE_URL` and `SUPABASE_SECRET_KEY`. Do not commit credentials, substitute a publishable/anonymous key for privileged research persistence, weaken RLS, or create an unauthenticated persistence bypass. The missing configuration must be supplied through the existing Render environment by an authorized operator.

V1 OI timestamp semantics remain limited: V1 exact-matches Binance hourly OI `timestamp` to normalized OHLC candle OPEN timestamp. Binance defines OI `timestamp` as the period end, so V1 can systematically lose OI availability.

V2 tested a cleaner exact hypothesis: completed 1H candle endpoint exactly equals Binance OI period-end timestamp. After #242 made V2-specific observability visible, multiple live coordinator samples showed `price_oi_correlation_v2` unavailable for all 12 symbols at 6h, 12h, and 24h. The V2 scorer was running and other health indicators were normal, so this is not evidence of a missing runtime invocation. Binance's current public Open Interest Statistics documentation calls the field the period end but shows an example timestamp that is not constrained to a canonical hourly wall-clock boundary. Therefore exact endpoint equality is not a valid general source assumption. This is now a durable negative research result.

PR #244 responds without loosening V2. `FFRIZZ_SECONDARY_V3_OI_CAUSAL_ASOF` is separately fingerprinted. For each OI observation it selects only the latest already-completed 1H price endpoint at or before that OI timestamp, with staleness strictly below one hour. It rejects duplicate OI timestamps and ambiguous reuse of a price endpoint, forbids future price, nearest-neighbour, and interpolation semantics, retains fixed signal thresholds, and has no persistence/trading authority. Regression tests explicitly exercise non-boundary OI timestamps, no-future chronology, ambiguous reused endpoints, and no-authority metadata.

Immediately before #248 integration, live coordinator observability remained healthy with 1,035 completed worker samples, 0 failures, 0 timeouts, healthy supervisor/canary, no stale/crashed workers or restart pressure, 256 token-free specialists, and zero normal-operation AI calls. ACC-002 remained blocked only by `InsufficientHistory`. FFriZz V1 remained all-WAIT in the sampled cycle with `unexpected_wait_state=0`, while V2 continued to show zero OI-family availability at 6h/12h/24h.

PR #248 now makes V3 prospective runtime evidence observable without increasing network requests or compute concurrency. No post-#248 natural adaptive FFriZz cycle had been interpreted at integration time; availability alone will not be treated as alpha evidence.

PR #239's calibration-freshness ordering has been observed in an actual scheduled workflow: `Evaluate previous signals` executes before `Run production market scan`.

PR #246 repairs a confirmed paper-risk liveness defect without weakening the loss-streak trigger: after four consecutive authentic losses, the paper portfolio remains blocked for 24 hours from the latest authentic `closed_at`; absent/malformed chronology remains fail-closed. Cooldown completion only removes the permanent-latch condition and does not override any other risk or signal gate.

History-network cost remains a throughput research topic rather than a confirmed correctness defect. Any cache/reuse change must preserve exact request identity, freshness, completed-candle semantics, chronology, provenance, and authoritative-source fallback.

GitHub `main` branch protection remains disabled. Exact-head Security and Reliability, expected-head merge protection, isolated branches, and current-main compatibility review are mandatory operational controls.

## COST / SPEED POLICY
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed. Prefer existing shared Render compute, deterministic Python, free/public defensible data, caching/reuse, early rejection, and bounded concurrency. No paid feed/service/compute without explicit approval.

The token-free specialist factory uses zero normal-operation AI calls. Heavy experiment admission remains capped at one. Do not expand workers merely for appearance; require measured information-value benefit.

Blind RSI/MACD/EMA permutations, duplicate ensemble members, repeated falsified hypotheses without materially new evidence, repeated pure-InsufficientHistory ACC-002 investigation, and worker-count expansion without demonstrated information value remain deprioritized.

## CURRENT OPEN DEVELOPMENT
PR #248 is integrated and must not be re-applied. PR #246 is integrated and must not be re-applied. PR #244 is integrated and must not be re-applied. #235/#236/#238/#239/#242 and older FFriZz PRs #214/#216/#217/#219/#221/#223/#225/#227/#229/#231 are integrated. #230/#232/#233/#234/#237/#240/#241/#243/#245/#247 are state-only/reconciliation work. Stale PRs #34, #33, and #13 remain incompatible with current main and must not be merged as-is without fresh relevance/compatibility review.

Persistent specialist priorities live in `orchestration/specialist_coordination.json`. The accuracy/profitability roadmap lives in `orchestration/accuracy_profitability_roadmap.json`. The V2 negative result and V3 experiment contract are preserved in `docs/FFRIZZ_V3_OI_CAUSAL_ASOF.md` and `orchestration/ffrizz_v3_oi_causal_asof.json`.

## EXACT NEXT STEP
1. Verify both Render services deploy #248 successfully, then inspect the first natural post-#248 adaptive FFriZz cycle. Read only the bounded V3 6h/12h/24h feature availability and allowlisted OI-unavailability reason counts; do not infer alpha from availability.
2. If V3 restores OI-family availability prospectively, verify chronology/provenance and integrity behavior before any forward-ledger design. Keep the `<1H` staleness rule, no-future rule, no nearest-neighbour/interpolation, and ambiguous endpoint-reuse rejection unchanged.
3. Keep V1/V2/V3 evidence separate. V2's exact-match hypothesis remains a durable negative result and must not be loosened to improve coverage.
4. Restore the coordinator's canonical prediction-ledger configuration before treating FFriZz V1 prospective evidence accumulation as operational. The proven `PredictionLedgerNotConfigured` eligible-write failure remains open.
5. After V1 ledger configuration is restored, verify the first eligible persisted rows read-only: deterministic UUID scan identity, LONG/SHORT direction, canonical WAIT action, score 0..100, signed `calibration.raw_score`, preserved `shadow_action`, exact `due_at`, and full-horizon bucket identity.
6. Let valid prospective rows resolve naturally before any precision/expectancy comparison. Use exact fingerprint, non-overlapping full-horizon evidence, realistic costs, multiple-testing controls, and untouched OOS. No unresolved-row tuning or production promotion.
7. Continue using resolved primary-system errors, calibration, regime behavior, cross-sectional information, market microstructure, execution realism, paper rejection attribution, and research-memory outcomes to rank falsifiable experiments by expected information gain and after-cost impact.
8. Observe post-#238 paper/production rejection diagnostics and quantify whether WAIT/rejections are dominated by strategy evidence, market/liquidity, technical/data infrastructure, or portfolio risk. Treat the result as explanatory only.
9. Treat cache/network optimization as throughput research only; never stretch freshness/TTL, merge distinct request identities, or weaken provenance/completed-candle semantics.
10. Keep ACC-002 blocked while failures remain pure `InsufficientHistory`.
11. Keep `live_promotions.json` empty, broker disconnected, signing keys unused, authentic paper baseline/history immutable, heavy concurrency bounded, and recurring infrastructure <= USD 30/month.
12. Every integration remains isolated branch -> regression tests -> exact-head Security and Reliability -> current-main compatibility -> expected-head merge -> AI_STATE.md synchronization -> post-deploy health verification when runtime code changes.
