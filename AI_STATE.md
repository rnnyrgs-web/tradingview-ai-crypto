# AI DEVELOPMENT STATE
Last updated: 2026-09-10

## PURPOSE
Authoritative continuation state for `rnnyrgs-web/tradingview-ai-crypto`. Read this file from current `main` in full before development. Never infer project state only from ChatGPT memory. Update this file after each completed integration cycle.

## CURRENT MAIN / ARCHITECTURE
Current tested integration baseline after PR #199: `2c1c5dc08749a2114a1d1f609020a78dc2e3b0d5`. This includes PR #198 paper-only 7d LONG shadow holdings and PR #199 Kraken visible-depth USD-bridge entries on top of the prior A+ meta-signal trust, timestamp-safe consensus, shadow-direction research eligibility, economic-calibration/meta-WAIT and evidence-value scheduling work.

Production: GitHub -> Render -> Python/FastAPI V3 -> Supabase. Production scans run about every 15 minutes and produce separate 24h/7d Top-20 rankings. Continuous research/backtesting runs on the existing Render coordinator with bounded heavy concurrency under the USD 30/month recurring-infrastructure ceiling.

Primary production Render service: `srv-dadliegu01pc73bc7t50` (`tradingview-ai-crypto`).
Continuous research coordinator: `srv-dafgtead0e5s73cc7ekg`.
Supabase project used by production/research persistence: `dxgksvzibucwuzmppoqy`.
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed.

The always-on research architecture includes:
- bounded Python workers;
- autonomous research-director coordination;
- deterministic quant-science experiment factory;
- fail-closed heavy-experiment admission firewall;
- adaptive-accuracy lane sharing the existing heavy accuracy slot;
- 256 active token-free logical specialists per refresh from a much larger deterministic virtual namespace;
- durable research memory in Supabase;
- live read-only adaptive evidence observability including the durable conclusive-trial counter;
- research-only economic meta-WAIT diagnostics over independent non-overlapping full-horizon outcomes, kept horizon-specific rather than pooled;
- research-only resolved-forward regime×strategy diagnostics that reuse the learning worker's single ledger read, split each horizon chronologically 60/20/20, score development and validation only, and keep untouched OOS sealed;
- research-only economic calibration using probability-weighted win/loss payoffs net of conservative execution costs, with predeclared 1x/1.5x/2x/3x cost stress, chronological development/validation and sealed untouched OOS;
- research-only cross-sectional/residual diagnostics that use only already-persisted point-in-time fields and explicitly refuse historical feature backfill;
- prospective microstructure-veto diagnostics that use only timestamped persisted order-book evidence and never reconstruct unavailable history;
- ensemble-diversity diagnostics that measure matched strategy error agreement so redundant mechanisms are not treated as independent confirmation;
- resolved-error attribution that converts observed failures into falsifiable research buckets without fabricating explanations;
- selective-WAIT fusion that ranks restrictive abstention experiments from the above diagnostics but cannot itself alter production or open untouched OOS;
- an evidence-value research scheduler that prioritizes scarce experiment capacity by expected signal impact, information/falsification value, actionable-evidence probability, sample readiness, compute cost and redundancy risk while keeping blocked work visible but unclaimable;
- research-only A+ meta-signal trust diagnostics using predeclared high-confidence shadow-direction profiles plus timestamp-safe future-only multi-source market consensus, fixed cost stress, chronological development/validation and sealed untouched OOS;
- explicit separation between research eligibility and production action: immutable LONG/SHORT shadow forecasts may be studied even while `action_at_forecast` is WAIT, but research can never mutate that WAIT or grant trade/promotion/live-label authority;
- paper-only 7d LONG shadow eligibility for source-WAIT forecasts with rank <=5 and evidence >=80, while persisted production actions remain unchanged;
- paper forward execution that prefers direct Kraken books and may use a fully visible two-leg Kraken quote->USD->base route for USDT/USDC LONG entries when the direct book is absent, only if both public books, sufficient depth, both-leg fees and observable slippage are available;
- a governed accuracy/profitability roadmap that prioritizes selective WAIT, regime×strategy routing, cross-sectional/residual signals, economic calibration, prospective microstructure vetoes and ensemble diversity while explicitly deprioritizing duplicate or low-information research.

Logical scale must never be confused with physical compute scale. Heavy experiment concurrency remains capped at one admitted heavy experiment at a time unless a separately reviewed change explicitly proves a safe/cost-valid reason to alter it.

## SAFETY INVARIANTS
No AI opinion, ranking score, evidence score, current order-book snapshot, paper P&L, ensemble weight, single OOS result, historical promotion, observability metric, diagnostic, research-memory lesson, experiment priority, market-consensus provenance, microstructure snapshot, residual-momentum result, adaptive-accuracy result, meta-WAIT diagnostic, regime-strategy diagnostic, economic-calibration diagnostic, cross-sectional diagnostic, ensemble-diversity diagnostic, error-attribution diagnostic, selective-WAIT fusion result, meta-signal-trust result, shadow execution result, virtual-specialist result, or paper result by itself may authorize live BUY/SELL.

Mandatory chain:
RESEARCH -> BACKTEST -> VALIDATION -> UNTOUCHED OOS -> ROBUSTNESS/STABILITY -> MULTIPLE-TESTING FIREWALL -> POINT-IN-TIME UNIVERSE SAFETY -> STRATEGY-REGISTRY APPROVAL -> PRODUCTION-RISK APPROVAL -> GENUINE FORWARD PROOF -> GLOBAL/EXECUTION RISK CLEAR -> LIVE BUY/SELL.

Every later stage is restrictive-only. Missing, stale, contradictory, deteriorating, malformed, overlapping-only, insufficient, illiquid, execution-unsafe, portfolio-unsafe, statistically weak, survivorship-unsafe, identity-incomplete, persistence-unsafe, label-unsafe, chronology-unsafe, or system-unsafe evidence means `WAIT / NO TRADE / RESEARCH_ONLY`.

`live_promotions.json` remains empty. Signing keys remain unused. Broker remains disconnected. Do not add credentials or real-order capability without explicit user approval plus all canonical evidence gates.

Authentic paper account baseline remains exactly `$100,000` from `2026-09-08T01:17:49Z`. Never reset, rewrite, replace, or manufacture its history. Paper performance is evidence only.

## SCIENTIFIC RESEARCH DISCIPLINE
Chronological validation remains train/development -> validation -> untouched holdout/OOS. Robustness includes deterministic bootstrap/Monte Carlo resampling, parameter perturbation, regime stability, conservative execution-cost stress, search-breadth protection, and genuine forward confirmation. Forward proof counts only non-overlapping full-horizon resolved forecasts for the exact immutable strategy fingerprint.

Core invariants:
- no lookahead or leakage;
- no threshold/parameter mining against untouched OOS;
- no OOS reuse as fresh confirmation;
- no pooling historical/OOS evidence with genuine-forward evidence to inflate confidence;
- no survivorship substitution for missing point-in-time universe evidence;
- no backfilling prospective order-book/consensus features;
- realistic fees, spread, slippage and execution assumptions remain mandatory;
- repeated/disproven hypotheses receive a research-memory penalty rather than blind recycling;
- idea generation is not evidence;
- missing durable research memory must fail the adaptive lane closed rather than reset prior trials;
- overlapping forecasts must never be treated as independent observations;
- malformed, missing, or delayed outcome chronology must fail closed instead of fabricating labels or sample independence;
- economic meta-label discovery may only use defensible resolved independent evidence and cannot itself open untouched OOS or mutate production;
- meta-WAIT evidence must stay separated by horizon so 24h and 7d economics are not pooled into artificial support;
- regime×strategy discovery may score development/validation evidence only; its untouched OOS partition stays sealed and candidate status creates no production authority;
- economic calibration may nominate positive or restrictive research candidates from development/validation only, while untouched OOS stays sealed; apparent edge that survives only base-cost assumptions is not robust evidence;
- missing cross-sectional, microstructure, leadership, breadth, sector or residual fields must remain missing; do not reconstruct or backfill unavailable point-in-time evidence;
- ensemble model count is not independent evidence; redundant matched error behavior must be treated as potential duplication, not confidence amplification;
- error attribution proposes falsifiable research questions only; ambiguous errors remain unexplained rather than receiving invented causes;
- selective-WAIT fusion is hypothesis prioritization only and cannot bypass fresh validation, untouched OOS, multiple-testing, robustness or genuine-forward proof;
- research scheduling must prefer falsifiable, actionable, evidence-efficient experiments and penalize blocked/redundant/expensive low-information work without weakening any scientific gate;
- A+ meta-signal trust uses immutable shadow LONG/SHORT direction as research eligibility and may evaluate rows whose production action remains WAIT; this is research-only and cannot mutate `action_at_forecast`, authorize a live trade, open sealed OOS, or bypass the canonical chain;
- future-only consensus is eligible only when its captured provenance is timestamp-safe and sufficiently multi-source; unavailable historical consensus must stay missing rather than be reconstructed;
- paper-only 7d shadow eligibility must never mutate persisted production WAIT, strategy fingerprints, promotion state or live authority;
- paper USD-bridge entries require current Kraken public books on both legs, sufficient visible depth, explicit two-leg fees and observable slippage; unavailable or unsupported routes fail closed;
- hourly self-improvement review must not force paid model calls, bypass the 12-hour successful-run cooldown, exceed the $1/day API budget, increase physical concurrency, or change production authority.

PR #149 introduced `UNIVERSAL_SIGNAL_DEVELOPMENT_V1`, the canonical machine-readable objective: optimize genuine forward 24h/7d BUY/SELL/WAIT quality and positive after-cost expectancy, not headline historical accuracy.
PR #155 added the deterministic quant-science factory with predeclared methods/endpoints, minimum effects, one-search budgets, no-parameter-mining/no-OOS-reuse rules, and bounded per-method breadth.
PR #158 added the adaptive research evaluator: hypotheses originate on development evidence, are frozen before validation, and untouched OOS remains sealed unless the predeclared validation gate passes.
PR #160 added the autonomous 24/7 research-director coordination layer. It coordinates missions and scarce compute but has no production-promotion authority.
PR #163 bridges safe logical-specialist diagnoses into the quant experiment factory so useful resolved-error hypotheses can enter the same governed scientific queue.
PR #164 hardened massive virtual research with a fail-closed firewall. Every admitted quant-science design must remain research-only and satisfy one predeclared search, one candidate mutation, no parameter mining, no untouched-OOS reuse, no OOS/forward pooling, mandatory multiple-testing protection, independent replication, genuine-forward replication, duplicate-hypothesis penalties, no paid-compute escalation by default, and no trade/promotion/strategy-mutation authority. Heavy concurrency remains one.
PR #165 scales token-free logical research to 256 active deterministic specialists per refresh while retaining one shared immutable-ledger read and zero normal-operation AI calls.
PR #167 surfaces adaptive-accuracy evidence through read-only research observability.
PR #168 enforces durable sequential multiple-testing before adaptive OOS admission using a monotonic conclusive-trial count and sequential alpha spending. Production research memory is persisted in the existing Supabase project and fails closed if the configured persistent store is unavailable.
PR #170 increases cloud-specialist eligibility checks from every three hours to hourly while preserving the 12-hour successful-run cooldown, one concurrent/model run, the $1/day runner API budget, the $30/month recurring-infrastructure ceiling, review-only Lead behavior, no automatic merge, and no trade authority.
PR #172 exposes the durable adaptive `conclusive_trial_count` in live read-only research evidence. It does not change research thresholds, OOS gates, costs, or authority.
PR #173 fixes logical specialists to consume the actual live prediction-ledger vocabulary: production LONG/SHORT directions, live regime labels, and WAIT from `action_at_forecast`, while retaining legacy compatibility and stable specialist identities.
PR #175 fixes live calibration independence: calibration readiness, Wilson confidence, and deterioration checks now use deterministic full-horizon non-overlapping forecasts reconstructed from immutable `due_at - horizon`; missing/malformed chronology does not count as evidence.
PR #176 fixes genuine forward-proof chronology for the production ledger: origin is reconstructed from immutable `due_at - horizon`, `resolved_at >= due_at` is required, and overlapping full-horizon windows are deterministically de-overlapped without outcome-based selection.
PR #177 applies the same full-horizon non-overlap discipline to shadow-readiness evidence and fails closed when immutable due chronology is unavailable.
PR #178 applies exact matched, full-horizon, non-overlapping windows to champion/challenger shadow competition, matching strategies only on exact due endpoints rather than calendar buckets.
PR #179 hardens prediction-outcome label integrity. The prediction evaluator now accepts the first 1H candle at/after the forecast deadline only within an explicit 2-hour maximum lag; a stale delayed candle leaves the prediction unresolved instead of creating a contaminated outcome label. This changes no strategy, calibration threshold, OOS gate, trade authority, or promotion authority.
PR #181 fixes a live paper-cycle reliability defect found after the PR #179 deployment. `paper_signal_decisions` writes now declare `on_conflict=signal_key` together with `resolution=ignore-duplicates`, so re-processing an already-recorded paper decision is idempotent instead of aborting the cycle with a Supabase 409 unique-key error. This does not rewrite the authentic paper ledger, change account values, alter strategy logic, or add trade/promotion authority.
PR #183 adds research-only economic meta-WAIT diagnostics that use non-overlapping full-horizon resolved rows and a fixed 12 bps research round-trip cost, exposes those diagnostics in the learning worker, adds a governed research roadmap for regime routing/cross-sectional/economic-calibration/microstructure/diversity work, and makes hourly eligibility reviews explicitly ask what should be added, removed, simplified, combined or deprioritized. It preserves the 12-hour successful model cooldown, $1/day API budget, $30/month ceiling, one heavy experiment slot, no automatic merge, broker-disconnected posture and zero production authority.
PR #185 adds resolved-forward regime×strategy routing diagnostics to the existing learning worker. It uses only non-overlapping full-horizon resolved rows, creates deterministic 60/20/20 chronological partitions separately for 24h and 7d, scores development and validation only, leaves untouched OOS outcomes sealed, and classifies sufficiently supported pairs only as prospective shadow-router or restrictive-WAIT research candidates. It adds no worker, market-data call, paid service, AI call, production threshold, strategy fingerprint, trade authority, promotion authority, or paper-ledger mutation.
PR #186 fixes three recurring operational stalls without weakening research/trading gates: impossible low-price/high-ATR risk geometry fails closed for the affected symbol/horizon instead of aborting a scan; cross-exchange spot data defaults to Binance's public market-data-only host; and the read-only production AI observer interval is six hours so quota/rate-limit failures do not hammer the API while deterministic research continues.
PR #188 adds the requested research-only accuracy/profitability stack: economic calibration, cross-sectional/residual diagnostics, prospective microstructure veto diagnostics, ensemble-diversity diagnostics, resolved-error attribution, and selective-WAIT fusion. All reuse existing resolved-ledger evidence and the learning worker; no worker count, paid service, physical heavy concurrency, production threshold, strategy fingerprint, promotion authority, broker capability, or paper history changed.
PR #190 hardens economic calibration with predeclared 1x/1.5x/2x/3x execution-cost stress, prevents base-cost-only positive edge from being treated as robust, separates meta-WAIT evidence by 24h/7d horizon, and keeps selective-WAIT hypotheses horizon-specific. It changes no production threshold, strategy fingerprint, worker count, paid service, broker connectivity, paper history, or live authority.
PR #191 upgrades the research-director scheduler from additive headline scoring to evidence-value scheduling. It prioritizes expected signal impact, information/falsification value, actionable-evidence probability, sample readiness and compute efficiency, penalizes redundancy, and keeps natural-history-blocked missions visible but unable to consume scarce experiment capacity. It adds no workers, paid services, concurrency, trade authority or production behavior.
PR #194 adds a research-only A+ meta-signal trust layer with fixed predeclared high-confidence and high-confidence-plus-consensus profiles, chronological 60/20/20 development/validation/sealed-OOS structure, >=2 percentage-point development and validation precision-lift requirement, and positive expectancy through 3x fixed cost stress. Candidate status is research-only and cannot authorize production.
PR #195 exposes only timestamp-safe future-only market-consensus provenance already captured inside immutable prediction-ledger calibration to the learning worker. It requires reliable-at-forecast status, source-count sufficiency and observation timestamps no later than capture time; unavailable history remains missing and is never backfilled.
PR #196 fixes a circular research-design defect discovered from live resolved-ledger evidence: production was correctly WAIT on every resolved 24h row, so action-gated A+ research received zero samples. The trust layer now uses immutable LONG/SHORT shadow direction for research eligibility while production WAIT stays unchanged. Rows without LONG/SHORT shadow direction remain ineligible. The change adds no production authority, no OOS access, no threshold change and no paper mutation.
PR #198 adds a paper-only 7d LONG shadow lane for source-WAIT forecasts with rank <=5 and evidence >=80. Eligible rows are copied for paper eligibility only; persisted production rows/actions, promotion gates, broker state, signing keys and live authority are unchanged. Existing paper freshness, sizing, global risk, visible-depth execution, stop/target and 168h time-exit rules remain mandatory.
PR #199 fixes the execution-venue mismatch exposed by PR #198 by extending the existing Kraken public-depth USD bridge to LONG paper entries for USDT/USDC quote markets when direct BASE/stable books are unavailable. Both books, sufficient visible depth, both-leg fees and observed slippage are mandatory; unsupported or unavailable routes fail closed. This is paper execution realism only and grants no live authority.

No accuracy or profitability improvement is claimed merely because these infrastructure/scientific changes exist. Any such claim still requires independent evidence through the canonical chain.

## ACCURACY / RESEARCH PROGRAM
- ACC-001 MARKET / EXECUTION REALISM — COMPLETE.
- ACC-002 CROSS-ASSET RANK RESEARCH — FAIL-CLOSED before untouched OOS because the second predeclared liquidity subset is not yet defensibly supported.
- ACC-003 through ACC-014 safety/validation layers — COMPLETE, including regime gating, champion/challenger, provenance, deterioration, robustness, genuine forward proof, portfolio/execution risk, size-aware execution, point-in-time universe safety, multiple-testing firewall, shadow comparison and chaos/failure gates.
- SELECTIVE PRECISION — research-only; independent non-overlapping full-horizon evidence required.
- ECONOMIC META-WAIT — research-only diagnostic active; horizon-specific and based on independent non-overlapping outcomes after conservative research cost. It cannot change production and still requires fresh governed validation/OOS/forward proof.
- REGIME × STRATEGY ROUTER — research-only resolved-forward diagnostic active. It reuses the learning-worker ledger read, separately evaluates 24h/7d development and validation evidence, keeps untouched OOS sealed, and can only nominate shadow-router or restrictive-WAIT candidates for later canonical testing.
- ECONOMIC CALIBRATION — research-only diagnostic active. It evaluates probability-weighted payoff after costs in fixed confidence bands using chronological development/validation evidence and predeclared multi-level cost stress; untouched OOS remains sealed.
- SELECTIVE-WAIT FUSION — research-only diagnostic active. It combines restrictive meta-WAIT, regime×strategy, economic-calibration, prospective microstructure and error-attribution hypotheses only to prioritize fresh abstention experiments, horizon-specifically where required.
- A+ META-SIGNAL TRUST — research-only diagnostic active. It evaluates fixed shadow-direction confidence/consensus profiles using independent non-overlapping resolved outcomes, timestamp-safe future-only consensus, chronological development/validation, sealed untouched OOS and 3x cost stress. Production WAIT rows may be studied but never changed by this layer.
- CROSS-SECTIONAL / RESIDUAL SIGNAL SCIENCE — research-only diagnostics active for persisted point-in-time rank, residual momentum, relative strength, breadth, beta and leadership/sector fields. Missing fields are reported rather than backfilled. Existing beta-neutral residual momentum remains a challenger.
- MICROSTRUCTURE VETO — research-only prospective diagnostic active using timestamped persisted spread, visible depth and imbalance evidence only; no historical order-book reconstruction.
- ENSEMBLE DIVERSITY — research-only diagnostic active. Matched strategy error agreement may nominate redundant-mechanism research candidates; redundant model count is not independent evidence.
- RESOLVED ERROR ATTRIBUTION — research-only diagnostic active; classifies defensible observed failure modes into falsifiable next-test buckets while leaving ambiguous errors unexplained.
- FUTURE-ONLY AGREEMENT EVIDENCE — accumulating naturally; no backfill or precision claim.
- KRAKEN PUBLIC-BOOK MICROSTRUCTURE — prospective research-only measurement; stale/future/crossed/one-sided/malformed books fail closed; no historical reconstruction or hidden-liquidity inference.
- BETA-NEUTRAL RESIDUAL MOMENTUM — challenger only; cannot bypass canonical validation gates.
- UNIVERSAL SIGNAL-DEVELOPMENT / LEARNING LOOP — active; research-only and information-gain aware.
- QUANT-SCIENCE RESEARCH FACTORY — active; predeclared science, bounded executable breadth and blocker-aware scheduling.
- EVIDENCE-VALUE RESEARCH SCHEDULER — active; scarce experiment capacity is ranked by falsifiability, actionable evidence probability, expected signal impact, sample readiness, compute cost and redundancy risk while blocked work remains fail-closed.
- ADAPTIVE ACCURACY EXPERIMENT LANE — active; protected by durable trial memory and sequential multiple-testing-adjusted OOS admission.
- TOKEN-FREE SPECIALIST FACTORY — 256 active deterministic logical specialists per refresh, zero normal-operation AI calls, research-only. Do not increase specialist count without measured information-value evidence.

### ACC-002 genuine bounded evidence
The blocker remains natural history, not a strategy pass/fail result. Do not lower `minimum_subset_coverage=0.80`, remove the two-supported-subset requirement, substitute lower-ranked assets, shorten required history merely to pass, fabricate/backfill history, or repeatedly spend scarce cycles re-diagnosing pure `InsufficientHistory` outcomes.

Live coordinator observability immediately before PR #196 showed only the Top-15 subset defensibly supported. The 24h worker resolved 29/30 symbols with 1 pure `InsufficientHistory` failure; the 7d worker resolved 16/30 with 14 pure `InsufficientHistory` failures. Both remained `insufficient_supported_liquidity_subsets`, untouched OOS stayed closed, and trade/promotion/signal authority remained false. These counts are operational snapshots and will change naturally; use live observability for current values.

Pure ACC-002 `InsufficientHistory` outcomes use the bounded recheck delay so the shared accuracy lane can spend more time on falsifiable adaptive research. Mixed request/source/software failures must not receive that exemption.

## OPERATIONS / RELIABILITY
Prediction-ledger persistence, observer rate-limit backoff, conservative Kraken paper execution, stable-quote USD bridge marking, queue-state supervision, deployment canary, aggregate failure classification and worker-supervisor protections remain active.

PR #165 exact head `1067e7c79443fbe532fa36e7e922529d83d5eafb` passed Security and Reliability #1238 before merge as `581121bd2585e4bfdee82b9b7685b74320e44afd`.
PR #167 exact head `0813b9e352b071a3cb882828a2faeb1867df8ebe` passed Security and Reliability #1246 before merge as `6058aed4f62dd5519d81965ead2bad26503ac820`.
PR #168 exact final head `ca3181193fb2c1f0f0ef1be6d661f9e0bfe5aea2` passed Security and Reliability #1260 before squash merge as `c73f93ca90dc70e6ecb4810f0ed591994a7d434b`.
PR #170 exact head `bc7d49c3d94839b45e79a42e5b1895d43079efb4` passed Security and Reliability #1277 before squash merge as `0fbd13643c01ca9dfd63fcfbd0b60ec5300c2fe6`.
PR #179 exact head `9755aea5e44b5becf9af81c616cf79e4147ca818` passed Security and Reliability #1317 before squash merge as `946c6f7ec5e41ab5c364aa7f5e93f0bc56a32de9`.
PR #181 exact head `7e26f6ae6fe9de5afb075c5fb58a32ea4e172048` passed Security and Reliability #1326 before squash merge as `15d40568a250b3d6ac5d71e19bc1a1bf25e91c20`.
PR #183 exact final head `2aeeb099be9be2006982cff0bf490477c68ac8f8` passed Security and Reliability #1346 before squash merge as `8db0bbd6a1601f0bcfc00dbefb3fdf0490c87f25`. The prior candidate failed one regression because canonical ACC-002 wording had been removed; the wording was restored without weakening the guard and the new exact head passed all checks.
PR #185 exact head `7daca2531b5e74edd102a6147a9d26c04ca9c76c` passed Security and Reliability #1361 before squash merge as `8dde2417d8f0dbf0c4782bb71047afedd8403adb`.
PR #186 exact head `9b400265a505798649f8ac0cf8e808a6d726370c` passed Security and Reliability #1364 before merge as `f0d6681294a13c7d26a2ab7a0962407c0fab7366`.
PR #187 state synchronization passed Security and Reliability #1371 before merge as `956c22a616f95d4eab8b77d8768677c3fe6e5130`.
PR #188 exact head `7e22f805fe0159fd017d2c0f47355f163c984770` passed Security and Reliability #1383 before squash merge as `3fa7d2ae3e134c6823a7c9577e37d468854a3de9`.
PR #190 exact head `7c0188d740acdb3233f10e74e8d8a21f2107f5ef` passed Security and Reliability #1396 before squash merge as `d88fd9bc40b94fbe66e9c8d64eeb7b4ed828ce7d`.
PR #191 exact final head `b3aaa4cac1fd0fa5a5113498cff51b41d43ee0af` passed Security and Reliability #1404 before squash merge as `c9fb1980cfb0319645a7ec2cbaa6f8a55e16f04a`. An earlier #191 candidate exposed a regression in blocked-mission observability; the regression was fixed without weakening the natural-history guard before the final exact head passed.
PR #194 exact head `e126ce806c6b16c1d1b9c76fdad9675f0782071d` passed its exact-head Security and Reliability run before merge.
PR #195 exact head `a91f1a044c0ec651ce060b74f4a08180600efe61` passed its exact-head Security and Reliability run before merge as `a265182bfae4853325ea191c282aa5c1097762dd`.
PR #196 exact head `c04ad1b2df835ad3c1c9e1fab05e7603043845dc` passed Security and Reliability #1429 before squash merge as `85c6eb91f4fcd29a63988a130f2fbc15eead59a9`.
PR #198 exact head `0673ff298b8244a6c6532f2ce3c108f4b7b3779f` passed Security and Reliability #1438 before squash merge as `e6c8c3be5d7259b350e0d461178c260a244773c5`.
PR #199 first candidate exposed an obsolete long-entry bridge policy regression and was not merged. Corrected exact head `aca4289d032928393f3cac2ddd75e9034b238a53` passed Security and Reliability #1445 before squash merge as `2c1c5dc08749a2114a1d1f609020a78dc2e3b0d5`.

Immediately after PR #199 deployed, the authentic paper engine opened four 7d LONG positions using `visible_depth_v2` two-source Kraken execution: MINA-USDT, KAT-USDT, ZEC-USDT and NEAR-USDT. IOST-USDT remained fail-closed because the required bridge market evidence was unavailable. The global paper concentration gate then blocked further directional additions with `correlated_directional_concentration`. This is operational execution evidence only, not evidence of predictive accuracy or profitability.

The paper account baseline remained exactly $100,000. Immediately after those entries, the account reported cash about $84,195.75, equity about $103,332.39 and realized P&L about $3,780.06; these are authentic ledger snapshots that must never be reset or interpreted as proof of future profitability.

A read-only Supabase audit during the PR #196 cycle found 1,920 resolved 24h prediction-ledger rows and zero production-actionable rows: every resolved row had `action_at_forecast=WAIT` while retaining an immutable LONG or SHORT shadow direction. The raw overlapping rows were 1,460 LONG and 460 SHORT. These counts exposed the A+ research-eligibility defect fixed by PR #196. They are not independent samples, must not be used as a profitability claim, and must be de-overlapped by the existing full-horizon independence logic before any research inference.

Observed shared-history cache hit rate in the same live window remained low (about 7.5%) while history network fetches were failure-free but relatively expensive (roughly 6.5s median in coordinator observability). Treat this as a research-throughput optimization candidate only: do not stretch TTLs, alter completed-candle semantics, weaken provenance identity, or reuse stale snapshots merely to improve cache metrics. First identify whether misses are legitimate request diversity versus safely reusable identical history requests.

The prior live paper-cycle defect was a repeated decision write hitting Supabase unique constraint `paper_signal_decisions_signal_key_key`. PR #181 changed those writes to explicit idempotent conflict handling. No recurrence was observed in the checked post-#181 windows; continue monitoring without rewriting paper history.

Supabase security hardening from PR #168 remains required: `research_learning_state` has RLS enabled; anon/authenticated table access is revoked; service role has required access; the atomic append RPC is service-role-only among application roles; and the pre-existing paper append-only function has a fixed `search_path=public`.

GitHub currently reports `main` branch protection disabled. Workflow exact-head/manual-review controls remain mandatory. Enable branch/ruleset protection when repository-admin access is available; do not weaken current controls meanwhile.

Cross-exchange/public-data collection may be unavailable at times. Never manufacture consensus, microstructure, history, agreement data, outcome labels, cross-sectional fields or error causes when source evidence is unavailable or temporally invalid.

## COST / SPEED POLICY
Hard recurring infrastructure ceiling: USD 30/month unless explicitly changed. Prefer existing shared Render compute, deterministic Python, free/public defensible data, caching/reuse, early rejection and bounded concurrency. No paid feed/service/compute without explicit approval.

The current logical-worker scale does not raise physical heavy concurrency. The token-free specialist factory uses zero normal-operation AI calls. Heavy experiment admission remains capped at one. API/model spending remains separately budget-gated.

Hourly autonomous eligibility checks carry the explicit self-improvement question from PR #183, but the 12-hour successful-run cooldown, $1/day API budget and cost gates remain authoritative. An hourly check is not an hourly paid model call.

The shared historical cache is provenance/integrity checked and bounded by freshness. Do not stretch TTLs or reuse stale snapshots merely to improve a cache metric. Any cache improvement must preserve exact request identity, point-in-time safety, chronology, completed-candle semantics and authoritative-source fallback.

Preserve exact strategy fingerprints while genuine forward observations accumulate. Challengers may run in shadow. Never count overlapping forecasts as independent, lower forward-proof thresholds, reset paper history, raise heavy concurrency, stretch data freshness beyond safe semantics, change source behavior, or cherry-pick thresholds merely to accelerate results.

Blind RSI/MACD/EMA or similar parameter permutations without a diagnosed resolved-error mechanism are explicitly deprioritized. Redundant ensemble members, repeated falsified hypotheses without materially new evidence, repeated ACC-002 investigation while failures are purely `InsufficientHistory`, and worker-count expansion without demonstrated information-value benefit are also deprioritized. Features whose apparent edge disappears after realistic costs should be retired or deprioritized rather than optimized to historical noise.

## CURRENT OPEN DEVELOPMENT
PRs #160/#163/#164/#165/#167/#168/#170/#172/#173/#175/#176/#177/#178/#179/#181/#183/#185/#186/#187/#188/#190/#191/#194/#195/#196/#198/#199 are integrated and must not be re-applied. PR #180 was a state-only sync branch superseded by later current-main syncs and must not be merged. PR #166 is stale/superseded and must not be merged as-is. PR #140 was closed as superseded by integrated PR #170. Older PRs #34, #33 and #13 are stale against current main and must not be merged as-is without a fresh compatibility/relevance review.

Persistent specialist priorities live in `orchestration/specialist_coordination.json`. The accuracy/profitability add/remove roadmap lives in `orchestration/accuracy_profitability_roadmap.json`. Specialists may create isolated candidate work only and may not bypass the canonical evidence gates or recurring-cost ceiling.

## EXACT NEXT STEP
1. Keep the four new 7d paper holdings under authentic forward observation. Do not force additional positions while `correlated_directional_concentration` is active; treat the concentration gate as restrictive-only.
2. Compare the eventual non-overlapping 7d outcomes and after-cost paper exits for the paper-shadow cohort against comparable source-WAIT 7d forecasts that were not entered. Do not treat paper P&L alone as strategy evidence or relax canonical validation.
3. Inspect future 7d paper-entry rejections by exact reason. Unsupported Kraken direct/bridge markets, insufficient visible depth, stale signals or risk blocks must remain fail-closed rather than receiving synthetic fills.
4. Inspect naturally completed post-#196 A+ meta-signal-trust reports. Confirm nonzero independent shadow-direction development/validation samples while production-WAIT rows remain explicitly research-only and unmodified.
5. Never treat raw overlapping prediction-ledger rows as independent evidence. Meta-signal trust and all forward inference must continue deterministic full-horizon non-overlap and keep sealed OOS untouched until its predeclared gate passes.
6. Measure timestamp-safe consensus coverage within independent shadow-direction evidence. If consensus coverage is insufficient, wait for natural future-only accumulation; never reconstruct or backfill historical consensus.
7. Continue natural 7d outcome accumulation and preserve the ACC-002 natural-history blocker while aggregate failures remain `InsufficientHistory`; never weaken the 80% coverage, two-supported-subset, Top-N ordering or untouched-OOS rules.
8. Investigate the low shared-history cache hit rate only as a throughput question: determine whether misses reflect legitimate request diversity or exact repeated immutable history requests that can safely reuse provenance-identical completed-candle snapshots. Make no TTL/freshness change without exact-identity and chronology proof.
9. Audit prediction-ledger outcomes for temporal integrity after PR #179 and continue monitoring the authentic append-only paper ledger. Invalid/stale labels stay unresolved; paper history is never rewritten.
10. Keep `live_promotions.json` empty, broker disconnected, signing keys unused, paper baseline immutable, heavy concurrency bounded, and recurring infrastructure within USD 30/month until genuine governed evidence justifies any separately approved change. Keep exact-head Security and Reliability plus current-main compatibility review mandatory for every integration.